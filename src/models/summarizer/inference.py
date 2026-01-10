"""Summarizer inference module."""

import time
from typing import Dict, Any, List, Optional
from pathlib import Path

import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from loguru import logger

from .config import SummarizerConfig
from .strategies import SummaryStrategy, StrategyFactory, SummaryOutput
from ...utils.mlflow_utils import MLflowManager, SUMMARIZER_MODEL_NAME
from ...utils.summary_utils import estimate_read_time, extract_key_takeaways


class SummarizerInference:
    """Inference engine for article summarization."""
    
    def __init__(
        self,
        model_path: Optional[str] = None,
        config: Optional[SummarizerConfig] = None,
        use_mlflow: bool = False,
        stage: str = "Production",
        device: Optional[str] = None,
    ):
        """
        Initialize the summarizer for inference.
        
        Args:
            model_path: Local path to model
            config: Summarizer configuration
            use_mlflow: Whether to load model from MLflow registry
            stage: MLflow model stage to load
            device: Device to run inference on
        """
        self.config = config or SummarizerConfig()
        self.device = device or self._get_device()
        self.model = None
        self.tokenizer = None
        self.model_version = None
        
        if model_path:
            self._load_local(model_path)
        elif use_mlflow:
            self._load_from_mlflow(stage)
        else:
            # Load default model from Hugging Face
            self._load_default()
        
        logger.info(f"Summarizer loaded on device: {self.device}")
    
    def _get_device(self) -> str:
        """Determine the best available device."""
        if torch.cuda.is_available():
            return "cuda"
        elif torch.backends.mps.is_available():
            return "mps"
        return "cpu"
    
    def _load_local(self, model_path: str):
        """Load model from local path."""
        logger.info(f"Loading summarizer from: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_path)
        self.model.to(self.device)
        self.model.eval()
        self.model_version = "local"
    
    def _load_default(self):
        """Load default model from Hugging Face."""
        logger.info(f"Loading default summarizer: {self.config.model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(self.config.model_name)
        self.model.to(self.device)
        self.model.eval()
        self.model_version = "default"
    
    def _load_from_mlflow(self, stage: str = "Production"):
        """Load model from MLflow registry."""
        logger.info(f"Loading summarizer from MLflow ({stage})")
        
        try:
            mlflow_manager = MLflowManager()
            version = mlflow_manager.get_latest_version(SUMMARIZER_MODEL_NAME, stages=[stage])
            
            if version is None:
                logger.warning(f"No {stage} summarizer found, loading default")
                self._load_default()
                return
            
            self.model_version = version.version
            
            # Load using MLflow's transformers flavor
            from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
            import mlflow
            
            model_uri = f"models:/{SUMMARIZER_MODEL_NAME}/{stage}"
            loaded_model = mlflow.transformers.load_model(model_uri, return_type="components")
            
            # Extract model and tokenizer
            self.model = loaded_model["model"]
            self.tokenizer = loaded_model["tokenizer"]
            self.model.to(self.device)
            self.model.eval()
            
            logger.info(f"Loaded summarizer version: {self.model_version}")
            
        except Exception as e:
            logger.warning(f"Failed to load from MLflow: {e}, loading default")
            self._load_default()
    
    def summarize(
        self,
        text: str,
        strategy: Optional[SummaryStrategy] = None,
        summary_type: str = "brief",
    ) -> Dict[str, Any]:
        """
        Generate a summary for the given text.
        
        Args:
            text: Input text to summarize
            strategy: Summarization strategy to use
            summary_type: Type of summary if no strategy provided ('brief' or 'detailed')
            
        Returns:
            Dictionary with summary and metadata
        """
        start_time = time.time()
        
        # Get strategy
        if strategy is None:
            strategy = StrategyFactory.get_strategy(summary_type, self.config)
        
        # Tokenize input
        inputs = self.tokenizer(
            text,
            truncation=True,
            max_length=self.config.max_input_length,
            return_tensors="pt",
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        # Get generation parameters from strategy
        gen_params = strategy.get_generation_params()
        
        # Generate summary
        with torch.no_grad():
            summary_ids = self.model.generate(
                inputs["input_ids"],
                attention_mask=inputs.get("attention_mask"),
                **gen_params,
            )
        
        # Decode summary
        summary_text = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
        
        # Post-process with strategy
        output = strategy.post_process(summary_text, text)
        
        latency_ms = (time.time() - start_time) * 1000
        
        return {
            "summary_text": output.summary_text,
            "summary_type": output.summary_type,
            "key_takeaways": output.key_takeaways,
            "latency_ms": latency_ms,
            "model_version": self.model_version,
            "estimated_read_time": estimate_read_time(text),
        }
    
    def summarize_article(
        self,
        article: Dict[str, Any],
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Summarize an article based on its classification label.
        
        Args:
            article: Article dictionary with 'title', 'abstract', 'full_text'
            label: Classification label ('important' or 'worth_learning')
            
        Returns:
            Dictionary with summary and metadata
        """
        # Combine text for summarization
        title = article.get("title", "")
        abstract = article.get("abstract", "") or ""
        full_text = article.get("full_text", "") or ""
        
        # Use full text if available, otherwise abstract
        if full_text:
            text = f"{title}\n\n{full_text}"
        else:
            text = f"{title}\n\n{abstract}"
        
        # Get label from article if not provided
        if label is None:
            label = article.get("predicted_label") or article.get("label", "important")
        
        # Get appropriate strategy
        strategy = StrategyFactory.get_strategy_for_label(label, self.config)
        
        # Generate summary
        result = self.summarize(text, strategy=strategy)
        result["article_id"] = article.get("article_id")
        
        return result
    
    def summarize_batch(
        self,
        articles: List[Dict[str, Any]],
        batch_size: int = 4,
    ) -> List[Dict[str, Any]]:
        """
        Summarize a batch of articles.
        
        Args:
            articles: List of article dictionaries
            batch_size: Batch size for processing
            
        Returns:
            List of summaries
        """
        results = []
        total_start = time.time()
        
        for i, article in enumerate(articles):
            try:
                # Skip garbage articles
                label = article.get("predicted_label") or article.get("label")
                if label == "garbage":
                    continue
                
                result = self.summarize_article(article, label)
                results.append(result)
                
                if (i + 1) % 10 == 0:
                    logger.info(f"Summarized {i + 1}/{len(articles)} articles")
                    
            except Exception as e:
                logger.warning(f"Failed to summarize article {article.get('article_id')}: {e}")
                results.append({
                    "article_id": article.get("article_id"),
                    "error": str(e),
                })
        
        total_time = time.time() - total_start
        logger.info(f"Batch summarization complete: {len(results)} summaries in {total_time:.2f}s")
        
        return results
    
    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        return {
            "model_version": self.model_version,
            "model_name": self.config.model_name,
            "device": self.device,
            "brief_max_length": self.config.brief_max_length,
            "detailed_max_length": self.config.detailed_max_length,
        }
