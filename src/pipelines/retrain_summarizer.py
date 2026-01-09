"""Summarizer retraining pipeline."""

from datetime import datetime
from typing import Dict, Any, Optional, List

from loguru import logger

from ..models.summarizer import SummarizerTrainer, SummarizerEvaluator
from ..utils.db import get_db
from ..utils.config import config
from ..utils.mlflow_utils import MLflowManager, SUMMARIZER_MODEL_NAME
from .promote import ModelPromoter


class SummarizerRetrainPipeline:
    """
    Pipeline for retraining the summarizer based on feedback.
    
    Uses edited summaries and good/bad ratings to fine-tune the model.
    """
    
    def __init__(self):
        self.db = get_db()
        self.mlflow_manager = MLflowManager()
        self.promoter = ModelPromoter()
        self.threshold = config.retrain.summarizer_threshold
        self.improvement_threshold = config.retrain.summarizer_improvement
    
    def check_retrain_needed(self) -> Dict[str, Any]:
        """Check if retraining is needed based on feedback count."""
        feedback = self.db.get_unused_summary_feedback()
        
        # Count edited summaries (most valuable for training)
        edited_count = sum(1 for f in feedback if f.get("summary_edited_text"))
        good_count = sum(1 for f in feedback if f.get("summary_rating") == "good")
        bad_count = sum(1 for f in feedback if f.get("summary_rating") == "bad")
        
        needs_retrain = len(feedback) >= self.threshold
        
        return {
            "needs_retrain": needs_retrain,
            "feedback_count": len(feedback),
            "edited_count": edited_count,
            "good_count": good_count,
            "bad_count": bad_count,
            "threshold": self.threshold,
        }
    
    def _prepare_training_data(self) -> tuple:
        """Prepare training data from feedback."""
        feedback = self.db.get_unused_summary_feedback()
        
        training_data = []
        feedback_ids = []
        
        for item in feedback:
            # Only use edited summaries or good-rated summaries
            if item.get("summary_edited_text"):
                training_data.append({
                    "article_id": item["article_id"],
                    "title": item["title"],
                    "abstract": item.get("abstract", ""),
                    "full_text": item.get("full_text", ""),
                    "summary_edited_text": item["summary_edited_text"],
                })
                feedback_ids.append(item["feedback_id"])
            elif item.get("summary_rating") == "good":
                # Get the original summary for this article
                summary = self.db.get_summary(item["article_id"])
                if summary:
                    training_data.append({
                        "article_id": item["article_id"],
                        "title": item["title"],
                        "abstract": item.get("abstract", ""),
                        "full_text": item.get("full_text", ""),
                        "reference_summary": summary["summary_text"],
                    })
                    feedback_ids.append(item["feedback_id"])
        
        logger.info(f"Prepared {len(training_data)} samples for summarizer training")
        
        return training_data, feedback_ids
    
    def run(self, force: bool = False) -> Dict[str, Any]:
        """
        Run the retraining pipeline.
        
        Args:
            force: Force retraining even if threshold not met
            
        Returns:
            Dictionary with retraining results
        """
        logger.info("=" * 50)
        logger.info("Summarizer Retraining Pipeline")
        logger.info("=" * 50)
        
        results = {
            "start_time": datetime.utcnow().isoformat(),
            "retrained": False,
            "promoted": False,
        }
        
        # Check if retraining is needed
        check = self.check_retrain_needed()
        results["check"] = check
        
        if not check["needs_retrain"] and not force:
            logger.info(
                f"Retraining not needed. "
                f"Feedback: {check['feedback_count']}/{check['threshold']}"
            )
            return results
        
        logger.info(f"Starting retraining with {check['feedback_count']} feedback samples")
        
        try:
            # Prepare training data
            training_data, feedback_ids = self._prepare_training_data()
            
            if len(training_data) < 10:
                logger.warning(f"Only {len(training_data)} samples, may not be enough")
                if len(training_data) == 0:
                    results["error"] = "No usable training data"
                    return results
            
            # Train new model
            trainer = SummarizerTrainer()
            train_results = trainer.train(
                articles=training_data,
                register_model=True,
            )
            
            results["training"] = {
                "run_id": train_results["run_id"],
                "eval_metrics": train_results["eval_metrics"],
            }
            results["retrained"] = True
            
            # For summarizer, we also consider user ratings for promotion
            # Calculate improvement based on ROUGE-L or user satisfaction
            
            # Get current production metrics if available
            current_version = self.mlflow_manager.get_production_model_version(SUMMARIZER_MODEL_NAME)
            
            if current_version:
                current_metrics = self.mlflow_manager.get_run_metrics(
                    self._get_run_id_for_version(current_version)
                )
                
                new_rouge = train_results["eval_metrics"].get("eval_loss", 1.0)
                current_rouge = current_metrics.get("eval_loss", 1.0)
                
                # Lower loss is better
                improvement = current_rouge - new_rouge
                
                results["comparison"] = {
                    "current_version": current_version,
                    "improvement": improvement,
                    "threshold": self.improvement_threshold,
                }
                
                # Consider user feedback trend
                # If mostly positive feedback, be more lenient with promotion
                good_pct = check["good_count"] / max(check["feedback_count"], 1)
                
                if improvement >= self.improvement_threshold or good_pct > 0.7:
                    logger.info(f"Promoting new summarizer (improvement: {improvement:.4f}, good%: {good_pct:.2f})")
                    self.promoter.promote_summarizer(
                        train_results["run_id"],
                        reason=f"Improved loss by {improvement:.4f}, good rating: {good_pct:.2%}",
                    )
                    results["promoted"] = True
                else:
                    logger.info("New model did not meet promotion criteria")
            else:
                # No production model, promote this one
                logger.info("No production model found, promoting new model...")
                self.promoter.promote_summarizer(
                    train_results["run_id"],
                    reason="Initial production model",
                )
                results["promoted"] = True
            
            # Mark feedback as used
            if results["promoted"]:
                self.db.mark_feedback_used(feedback_ids)
                logger.info(f"Marked {len(feedback_ids)} feedback items as used")
            
        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            results["error"] = str(e)
        
        results["end_time"] = datetime.utcnow().isoformat()
        
        return results
    
    def _get_run_id_for_version(self, version: str) -> Optional[str]:
        """Get MLflow run ID for a model version."""
        try:
            versions = self.mlflow_manager.client.search_model_versions(
                f"name='{SUMMARIZER_MODEL_NAME}'"
            )
            for v in versions:
                if v.version == version:
                    return v.run_id
        except Exception:
            pass
        return None


def check_and_retrain():
    """Entry point for cron job."""
    from ..utils.config import setup_logging
    setup_logging()
    
    pipeline = SummarizerRetrainPipeline()
    return pipeline.run()


if __name__ == "__main__":
    check_and_retrain()
