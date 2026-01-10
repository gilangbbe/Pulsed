"""Classifier inference module."""

import time
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path

import torch
import numpy as np
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from loguru import logger

from .config import ClassifierConfig
from ...utils.config import LABELS, ID_TO_LABEL
from ...utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME


class ClassifierInference:
    """Inference engine for the article classifier."""
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        use_mlflow: bool = True,
        stage: str = "Production",
        device: Optional[str] = None,
    ):
        """
        Initialize the classifier for inference.
        
        Args:
            model_path: Local path to model (overrides MLflow)
            use_mlflow: Whether to load model from MLflow registry
            stage: MLflow model stage to load
            device: Device to run inference on ('cpu', 'cuda', 'mps')
        """
        self.device = device or self._get_device()
        self.model = None
        self.tokenizer = None
        self.model_version = None
        
        if model_path:
            self._load_local(model_path)
        elif use_mlflow:
            self._load_from_mlflow(stage)
        
        logger.info(f"Classifier loaded on device: {self.device}")
    
    def _get_device(self) -> str:
        """Determine the best available device."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _load_local(self, model_path: str):
        """Load model from local path."""
        logger.info(f"Loading model from: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path)
        self.model.to(self.device)
        self.model.eval()
        self.model_version = "local"
    
    def _load_from_mlflow(self, stage: str = "Production"):
        """Load model from MLflow registry."""
        logger.info(f"Loading model from MLflow ({stage})")
        
        try:
            mlflow_manager = MLflowManager()
            version = mlflow_manager.get_latest_version(CLASSIFIER_MODEL_NAME, stages=[stage])
            
            if version is None:
                raise ValueError(f"No {stage} model found in registry")
            
            self.model_version = version.version
            
            # Load the transformers model from MLflow
            from transformers import AutoTokenizer, AutoModelForSequenceClassification
            import mlflow
            
            # Load using MLflow's transformers flavor
            model_uri = f"models:/{CLASSIFIER_MODEL_NAME}/{stage}"
            loaded_model = mlflow.transformers.load_model(model_uri, return_type="components")
            
            # Extract model and tokenizer
            self.model = loaded_model["model"]
            self.tokenizer = loaded_model["tokenizer"]
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"Loaded model version: {self.model_version}")
            
        except Exception as e:
            logger.error(f"Failed to load from MLflow: {e}")
            raise
    
    def predict(
        self,
        text: str,
        return_confidence: bool = True,
    ) -> Dict[str, Any]:
        """
        Predict the label for a single text.
        
        Args:
            text: Input text (title + abstract)
            return_confidence: Whether to return confidence score
            
        Returns:
            Dictionary with prediction results
        """
        start_time = time.time()
        
        # Tokenize
        inputs = self.tokenizer(
            text,
            truncation=True,
            padding=True,
            max_length=512,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Predict
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            probs = torch.softmax(logits, dim=-1)
            
            predicted_class = torch.argmax(probs, dim=-1).item()
            confidence = probs[0, predicted_class].item()
        
        latency_ms = (time.time() - start_time) * 1000
        
        result = {
            "predicted_label": ID_TO_LABEL[predicted_class],
            "predicted_class": predicted_class,
            "latency_ms": latency_ms,
            "model_version": self.model_version,
        }
        
        if return_confidence:
            result["confidence"] = confidence
            result["probabilities"] = {
                label: probs[0, i].item()
                for i, label in enumerate(LABELS)
            }
        
        return result
    
    def predict_batch(
        self,
        texts: List[str],
        batch_size: int = 32,
        return_confidence: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        Predict labels for a batch of texts.
        
        Args:
            texts: List of input texts
            batch_size: Batch size for inference
            return_confidence: Whether to return confidence scores
            
        Returns:
            List of prediction results
        """
        all_results = []
        total_start = time.time()
        
        for i in range(0, len(texts), batch_size):
            batch_texts = texts[i:i + batch_size]
            batch_start = time.time()
            
            # Tokenize batch
            inputs = self.tokenizer(
                batch_texts,
                truncation=True,
                padding=True,
                max_length=512,
                return_tensors="pt",
            )
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Predict
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits = outputs.logits
                probs = torch.softmax(logits, dim=-1)
                
                predicted_classes = torch.argmax(probs, dim=-1)
            
            batch_latency = (time.time() - batch_start) * 1000
            per_item_latency = batch_latency / len(batch_texts)
            
            # Process results
            for j, (pred_class, prob_row) in enumerate(zip(predicted_classes, probs)):
                pred_class = pred_class.item()
                confidence = prob_row[pred_class].item()
                
                result = {
                    "predicted_label": ID_TO_LABEL[pred_class],
                    "predicted_class": pred_class,
                    "latency_ms": per_item_latency,
                    "model_version": self.model_version,
                }
                
                if return_confidence:
                    result["confidence"] = confidence
                    result["probabilities"] = {
                        label: prob_row[idx].item()
                        for idx, label in enumerate(LABELS)
                    }
                
                all_results.append(result)
        
        total_latency = (time.time() - total_start) * 1000
        logger.info(f"Batch prediction complete: {len(texts)} items in {total_latency:.2f}ms")
        
        return all_results
    
    def predict_articles(
        self,
        articles: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> List[Dict[str, Any]]:
        """
        Predict labels for articles.
        
        Args:
            articles: List of article dictionaries with 'title' and optional 'abstract'
            batch_size: Batch size for inference
            
        Returns:
            List of articles with predictions added
        """
        # Prepare texts
        texts = []
        for article in articles:
            title = article.get("title", "")
            abstract = article.get("abstract", "") or ""
            text = f"{title}. {abstract}".strip()
            texts.append(text)
        
        # Get predictions
        predictions = self.predict_batch(texts, batch_size=batch_size)
        
        # Merge with articles
        results = []
        for article, prediction in zip(articles, predictions):
            result = article.copy()
            result.update(prediction)
            results.append(result)
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_version": self.model_version,
            "device": self.device,
            "num_labels": len(LABELS),
            "labels": LABELS,
            "model_type": type(self.model).__name__,
        }
