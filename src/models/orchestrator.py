"""Multi-model pipeline orchestrator."""

from typing import Dict, Any, List, Optional
from datetime import datetime
import time

from loguru import logger

from .classifier import ClassifierInference
from .summarizer import SummarizerInference
from ..utils.db import get_db
from ..utils.mlflow_utils import MLflowManager


class ModelOrchestrator:
    """
    Orchestrates the complete prediction pipeline:
    1. Classification of articles
    2. Summarization of important/worth_learning articles
    3. Storage of results
    """
    
    def __init__(
        self,
        classifier_path: Optional[str] = None,
        summarizer_path: Optional[str] = None,
        use_mlflow: bool = True,
    ):
        """
        Initialize the orchestrator with models.
        
        Args:
            classifier_path: Path to classifier model (optional)
            summarizer_path: Path to summarizer model (optional)
            use_mlflow: Whether to load models from MLflow registry
        """
        self.db = get_db()
        self.mlflow_manager = MLflowManager()
        
        # Initialize classifier
        logger.info("Initializing classifier...")
        self.classifier = ClassifierInference(
            model_path=classifier_path,
            use_mlflow=use_mlflow,
        )
        
        # Initialize summarizer
        logger.info("Initializing summarizer...")
        self.summarizer = SummarizerInference(
            model_path=summarizer_path,
            use_mlflow=use_mlflow,
        )
        
        logger.info("Model orchestrator ready")
    
    def process_articles(
        self,
        articles: Optional[List[Dict[str, Any]]] = None,
        classify_only: bool = False,
        skip_existing_summaries: bool = True,
    ) -> Dict[str, Any]:
        """
        Process articles through the full pipeline.
        
        Args:
            articles: List of articles to process (None = fetch from DB)
            classify_only: If True, skip summarization
            skip_existing_summaries: Skip articles that already have summaries
            
        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        stats = {
            "start_time": datetime.utcnow().isoformat(),
            "articles_processed": 0,
            "classifications": {"garbage": 0, "important": 0, "worth_learning": 0},
            "summaries_generated": 0,
            "errors": [],
        }
        
        # Get unclassified articles if not provided
        if articles is None:
            articles = self.db.get_unclassified_articles()
            logger.info(f"Found {len(articles)} unclassified articles")
        
        if not articles:
            logger.info("No articles to process")
            stats["end_time"] = datetime.utcnow().isoformat()
            return stats
        
        # Step 1: Classification
        logger.info(f"Classifying {len(articles)} articles...")
        classified_articles = self.classifier.predict_articles(articles)
        
        # Store predictions and update stats
        for article in classified_articles:
            try:
                label = article["predicted_label"]
                stats["classifications"][label] = stats["classifications"].get(label, 0) + 1
                
                self.db.insert_prediction(
                    article_id=article["article_id"],
                    classifier_version=article.get("model_version", "unknown"),
                    predicted_label=label,
                    confidence=article.get("confidence", 0),
                    latency_ms=article.get("latency_ms"),
                )
            except Exception as e:
                logger.warning(f"Failed to store prediction: {e}")
                stats["errors"].append(str(e))
        
        stats["articles_processed"] = len(classified_articles)
        
        if classify_only:
            stats["end_time"] = datetime.utcnow().isoformat()
            stats["total_time_seconds"] = time.time() - start_time
            return stats
        
        # Step 2: Summarization (for non-garbage articles)
        articles_to_summarize = [
            a for a in classified_articles
            if a["predicted_label"] in ["important", "worth_learning"]
        ]
        
        if skip_existing_summaries:
            # Filter out articles with existing summaries
            articles_to_summarize = [
                a for a in articles_to_summarize
                if self.db.get_summary(a["article_id"]) is None
            ]
        
        if articles_to_summarize:
            logger.info(f"Summarizing {len(articles_to_summarize)} articles...")
            summaries = self.summarizer.summarize_batch(articles_to_summarize)
            
            # Store summaries
            for summary in summaries:
                if "error" in summary:
                    stats["errors"].append(summary["error"])
                    continue
                
                try:
                    # Calculate ROUGE scores if we have reference text
                    article = next(
                        (a for a in articles_to_summarize if a["article_id"] == summary["article_id"]),
                        None
                    )
                    
                    rouge_scores = None
                    if article:
                        from ..utils.summary_utils import RougeEvaluator
                        evaluator = RougeEvaluator()
                        reference = article.get("abstract") or article.get("full_text", "")
                        if reference:
                            rouge_scores = evaluator.score(reference, summary["summary_text"])
                    
                    self.db.insert_summary(
                        article_id=summary["article_id"],
                        summarizer_version=summary.get("model_version", "unknown"),
                        summary_type=summary["summary_type"],
                        summary_text=summary["summary_text"],
                        key_takeaways=summary.get("key_takeaways"),
                        estimated_read_time=summary.get("estimated_read_time"),
                        latency_ms=summary.get("latency_ms"),
                        rouge_scores=rouge_scores,
                    )
                    stats["summaries_generated"] += 1
                    
                except Exception as e:
                    logger.warning(f"Failed to store summary: {e}")
                    stats["errors"].append(str(e))
        
        stats["end_time"] = datetime.utcnow().isoformat()
        stats["total_time_seconds"] = time.time() - start_time
        
        logger.info(
            f"Pipeline complete: {stats['articles_processed']} classified, "
            f"{stats['summaries_generated']} summarized in {stats['total_time_seconds']:.2f}s"
        )
        
        return stats
    
    def process_single_article(
        self,
        article: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process a single article through the pipeline.
        
        Args:
            article: Article dictionary
            
        Returns:
            Article with classification and summary added
        """
        result = article.copy()
        
        # Classify
        prediction = self.classifier.predict(
            f"{article.get('title', '')}. {article.get('abstract', '')}"
        )
        result.update(prediction)
        
        # Summarize if not garbage
        if prediction["predicted_label"] != "garbage":
            summary = self.summarizer.summarize_article(article, prediction["predicted_label"])
            result["summary"] = summary
        
        return result
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get status of the pipeline and models."""
        return {
            "classifier": self.classifier.get_model_info(),
            "summarizer": self.summarizer.get_model_info(),
            "database": {
                "feedback_stats": self.db.get_feedback_stats(),
            },
        }
    
    def refresh_models(self, stage: str = "Production"):
        """Reload models from MLflow registry."""
        logger.info("Refreshing models from registry...")
        
        self.classifier = ClassifierInference(use_mlflow=True, stage=stage)
        self.summarizer = SummarizerInference(use_mlflow=True, stage=stage)
        
        logger.info("Models refreshed")
