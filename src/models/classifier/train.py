"""Classifier training module."""

import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path

import torch
import numpy as np
import pandas as pd
from torch.utils.data import Dataset
from transformers import (
    AutoTokenizer,
    AutoModelForSequenceClassification,
    Trainer,
    TrainingArguments,
    EarlyStoppingCallback,
)
from sklearn.model_selection import train_test_split
from sklearn.utils.class_weight import compute_class_weight
import mlflow
from loguru import logger

from .config import ClassifierConfig
from .evaluate import ClassifierEvaluator
from ...utils.config import LABELS, LABEL_TO_ID
from ...utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME


class ArticleDataset(Dataset):
    """Dataset for article classification."""
    
    def __init__(
        self,
        texts: List[str],
        labels: List[int],
        tokenizer,
        max_length: int = 512,
    ):
        self.texts = texts
        self.labels = labels
        self.tokenizer = tokenizer
        self.max_length = max_length
    
    def __len__(self):
        return len(self.texts)
    
    def __getitem__(self, idx):
        text = self.texts[idx]
        label = self.labels[idx]
        
        encoding = self.tokenizer(
            text,
            truncation=True,
            padding="max_length",
            max_length=self.max_length,
            return_tensors="pt",
        )
        
        return {
            "input_ids": encoding["input_ids"].squeeze(),
            "attention_mask": encoding["attention_mask"].squeeze(),
            "labels": torch.tensor(label, dtype=torch.long),
        }


class ClassifierTrainer:
    """Trainer for the article classifier."""
    
    def __init__(self, config: Optional[ClassifierConfig] = None):
        self.config = config or ClassifierConfig()
        self.tokenizer = None
        self.model = None
        self.mlflow_manager = MLflowManager()
    
    def _prepare_data(
        self,
        articles: List[Dict[str, Any]],
        test_size: float = 0.2,
        val_size: float = 0.1,
    ) -> Tuple[ArticleDataset, ArticleDataset, ArticleDataset]:
        """
        Prepare training, validation, and test datasets.
        
        Args:
            articles: List of articles with 'title', 'abstract', and 'label' keys
            test_size: Proportion for test set
            val_size: Proportion for validation set (from remaining after test split)
            
        Returns:
            Tuple of (train_dataset, val_dataset, test_dataset)
        """
        # Combine title and abstract for input
        texts = []
        labels = []
        
        for article in articles:
            title = article.get("title", "")
            abstract = article.get("abstract", "") or ""
            text = f"{title}. {abstract}".strip()
            
            label_str = article.get("label") or article.get("correct_label") or article.get("heuristic_label")
            if label_str and label_str in LABEL_TO_ID:
                texts.append(text)
                labels.append(LABEL_TO_ID[label_str])
        
        if not texts:
            raise ValueError("No valid labeled articles found")
        
        logger.info(f"Prepared {len(texts)} labeled articles for training")
        
        # Check if we have enough samples per class for stratification
        from collections import Counter
        label_counts = Counter(labels)
        min_samples_per_class = min(label_counts.values())
        use_stratify = min_samples_per_class >= 2
        
        if not use_stratify:
            logger.warning(f"Not enough samples per class for stratification. Label distribution: {dict(label_counts)}")
        
        # Split data
        X_temp, X_test, y_temp, y_test = train_test_split(
            texts, labels, test_size=test_size, 
            stratify=labels if use_stratify else None, 
            random_state=self.config.seed
        )
        
        val_ratio = val_size / (1 - test_size)
        # Check again for validation split
        val_label_counts = Counter(y_temp)
        use_stratify_val = min(val_label_counts.values()) >= 2
        
        X_train, X_val, y_train, y_val = train_test_split(
            X_temp, y_temp, test_size=val_ratio, 
            stratify=y_temp if use_stratify_val else None, 
            random_state=self.config.seed
        )
        
        logger.info(f"Train: {len(X_train)}, Val: {len(X_val)}, Test: {len(X_test)}")
        logger.info(f"Train label distribution: {Counter(y_train)}")
        
        # Create datasets
        train_dataset = ArticleDataset(X_train, y_train, self.tokenizer, self.config.max_length)
        val_dataset = ArticleDataset(X_val, y_val, self.tokenizer, self.config.max_length)
        test_dataset = ArticleDataset(X_test, y_test, self.tokenizer, self.config.max_length)
        
        return train_dataset, val_dataset, test_dataset
    
    def _compute_class_weights(self, labels: List[int]) -> torch.Tensor:
        """Compute class weights for imbalanced data."""
        class_weights = compute_class_weight(
            class_weight="balanced",
            classes=np.array([0, 1, 2]),
            y=np.array(labels),
        )
        return torch.tensor(class_weights, dtype=torch.float32)
    
    def train(
        self,
        articles: List[Dict[str, Any]],
        output_dir: Optional[str] = None,
        register_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Train the classifier model.
        
        Args:
            articles: List of labeled articles
            output_dir: Directory to save the model
            register_model: Whether to register model with MLflow
            
        Returns:
            Dictionary with training results and metrics
        """
        output_dir = output_dir or self.config.output_dir
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        # Initialize tokenizer and model
        logger.info(f"Loading model: {self.config.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        
        # Handle different model types - DistilBERT uses different dropout param
        model_name_lower = self.config.model_name.lower()
        if "distilbert" in model_name_lower:
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model_name,
                num_labels=self.config.num_labels,
                seq_classif_dropout=self.config.dropout,
            )
        else:
            self.model = AutoModelForSequenceClassification.from_pretrained(
                self.config.model_name,
                num_labels=self.config.num_labels,
                hidden_dropout_prob=self.config.dropout,
            )
        
        # Prepare data
        train_dataset, val_dataset, test_dataset = self._prepare_data(articles)
        
        # Start MLflow run
        with self.mlflow_manager.start_run(run_name="classifier_training") as run:
            run_id = run.info.run_id
            
            # Log parameters
            self.mlflow_manager.log_params(self.config.to_dict())
            self.mlflow_manager.log_params({
                "train_samples": len(train_dataset),
                "val_samples": len(val_dataset),
                "test_samples": len(test_dataset),
            })
            
            # Training arguments
            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                per_device_eval_batch_size=self.config.eval_batch_size,
                learning_rate=self.config.learning_rate,
                weight_decay=self.config.weight_decay,
                warmup_ratio=self.config.warmup_ratio,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                eval_strategy="steps",
                eval_steps=self.config.eval_steps,
                save_strategy="steps",
                save_steps=self.config.save_steps,
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                fp16=self.config.fp16 and torch.cuda.is_available(),
                logging_steps=50,
                save_total_limit=2,
                seed=self.config.seed,
                report_to="none",  # We're using MLflow directly
            )
            
            # Evaluator for metrics
            evaluator = ClassifierEvaluator()
            
            def compute_metrics(eval_pred):
                logits, labels = eval_pred
                predictions = np.argmax(logits, axis=-1)
                return evaluator.compute_metrics(labels, predictions)
            
            # Callbacks
            callbacks = []
            if self.config.early_stopping_patience > 0:
                callbacks.append(
                    EarlyStoppingCallback(
                        early_stopping_patience=self.config.early_stopping_patience,
                        early_stopping_threshold=self.config.early_stopping_threshold,
                    )
                )
            
            # Create trainer
            trainer = Trainer(
                model=self.model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=val_dataset,
                compute_metrics=compute_metrics,
                callbacks=callbacks,
            )
            
            # Train
            logger.info("Starting training...")
            train_result = trainer.train()
            
            # Log training metrics
            self.mlflow_manager.log_metrics({
                "train_loss": train_result.training_loss,
                "train_runtime": train_result.metrics.get("train_runtime", 0),
                "train_samples_per_second": train_result.metrics.get("train_samples_per_second", 0),
            })
            
            # Evaluate on test set
            logger.info("Evaluating on test set...")
            test_results = trainer.evaluate(test_dataset)
            
            # Log test metrics
            test_metrics = {
                f"test_{k.replace('eval_', '')}": v 
                for k, v in test_results.items()
            }
            self.mlflow_manager.log_metrics(test_metrics)
            
            # Save model
            trainer.save_model(output_dir)
            self.tokenizer.save_pretrained(output_dir)
            
            # Log model to MLflow
            if register_model:
                logger.info("Registering model with MLflow...")
                
                # Log model with transformers flavor using a dictionary
                import mlflow.transformers
                mlflow.transformers.log_model(
                    transformers_model={
                        "model": trainer.model,
                        "tokenizer": self.tokenizer,
                    },
                    artifact_path="model",
                    registered_model_name=CLASSIFIER_MODEL_NAME,
                )
            
            results = {
                "run_id": run_id,
                "train_loss": train_result.training_loss,
                "test_metrics": test_metrics,
                "model_path": output_dir,
            }
            
            logger.info(f"Training complete. Test accuracy: {test_metrics.get('test_accuracy', 'N/A'):.4f}")
            
            return results
    
    def train_from_feedback(
        self,
        feedback_articles: List[Dict[str, Any]],
        existing_model_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fine-tune model on new feedback data.
        
        Args:
            feedback_articles: Articles with corrected labels from feedback
            existing_model_path: Path to existing model to fine-tune
            
        Returns:
            Training results
        """
        # Use fine-tuning config
        from .config import FINE_TUNE_CONFIG
        self.config = FINE_TUNE_CONFIG
        
        if existing_model_path:
            self.config.model_name = existing_model_path
        
        return self.train(
            articles=feedback_articles,
            output_dir=f"{self.config.output_dir}_finetuned",
            register_model=True,
        )
