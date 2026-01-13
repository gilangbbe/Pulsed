"""Classifier retraining pipeline."""

from datetime import datetime
from typing import Dict, Any, Optional, List

from loguru import logger

from ..models.classifier import ClassifierTrainer, ClassifierEvaluator, ClassifierInference
from ..utils.db import get_db
from ..utils.config import config
from ..utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME
from .promote import ModelPromoter


class ClassifierRetrainPipeline:
    """
    Pipeline for retraining the classifier based on feedback.
    
    Checks if enough feedback has been collected and retrains
    the model if improvement thresholds are met.
    """
    
    def __init__(self):
        self.db = get_db()
        self.mlflow_manager = MLflowManager()
        self.promoter = ModelPromoter()
        self.threshold = config.retrain.classifier_threshold
        self.improvement_threshold = config.retrain.classifier_improvement
    
    def check_retrain_needed(self) -> Dict[str, Any]:
        """Check if retraining is needed based on feedback count."""
        feedback = self.db.get_unused_classification_feedback()
        
        needs_retrain = len(feedback) >= self.threshold
        
        return {
            "needs_retrain": needs_retrain,
            "feedback_count": len(feedback),
            "threshold": self.threshold,
            "feedback_samples": feedback[:5] if feedback else [],  # Preview
        }
    
    def _prepare_training_data(self) -> List[Dict[str, Any]]:
        """Prepare training data from feedback and existing data."""
        # Get unused feedback
        feedback = self.db.get_unused_classification_feedback()
        
        # Convert to training format
        training_data = []
        for item in feedback:
            training_data.append({
                "article_id": item["article_id"],
                "title": item["title"],
                "abstract": item.get("abstract", ""),
                "full_text": item.get("full_text", ""),
                "label": item["correct_label"],  # Use corrected label
            })
        
        logger.info(f"Prepared {len(training_data)} samples from feedback")
        
        return training_data, [f["feedback_id"] for f in feedback]
    
    def run(self, force: bool = False) -> Dict[str, Any]:
        """
        Run the retraining pipeline.
        
        Args:
            force: Force retraining even if threshold not met
            
        Returns:
            Dictionary with retraining results
        """
        logger.info("=" * 50)
        logger.info("Classifier Retraining Pipeline")
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
            
            if not training_data:
                logger.warning("No training data available")
                results["error"] = "No training data"
                return results
            
            # Train new model
            trainer = ClassifierTrainer()
            train_results = trainer.train(
                articles=training_data,
                register_model=True,
            )
            
            results["training"] = {
                "run_id": train_results["run_id"],
                "test_metrics": train_results["test_metrics"],
            }
            results["retrained"] = True
            
            # Compare with production model
            current_version = self.mlflow_manager.get_production_model_version(CLASSIFIER_MODEL_NAME)
            
            if current_version:
                # Get metrics from current production
                current_metrics = self.mlflow_manager.get_run_metrics(
                    self._get_run_id_for_version(current_version)
                )
                
                new_accuracy = train_results["test_metrics"].get("test_accuracy", 0)
                current_accuracy = current_metrics.get("test_accuracy", 0)
                improvement = new_accuracy - current_accuracy
                
                results["comparison"] = {
                    "current_version": current_version,
                    "current_accuracy": current_accuracy,
                    "new_accuracy": new_accuracy,
                    "improvement": improvement,
                    "threshold": self.improvement_threshold,
                }
                
                # Promote if improved
                if improvement >= self.improvement_threshold:
                    logger.info(f"New model improved by {improvement:.4f}, promoting...")
                    self.promoter.promote_classifier(
                        train_results["run_id"],
                        reason=f"Improved accuracy by {improvement:.4f}",
                    )
                    results["promoted"] = True
                else:
                    logger.info(f"Improvement {improvement:.4f} below threshold {self.improvement_threshold}")
            else:
                # No production model, promote this one
                logger.info("No production model found, promoting new model...")
                self.promoter.promote_classifier(
                    train_results["run_id"],
                    reason="Initial production model",
                )
                results["promoted"] = True
            
            # Mark feedback as used
            if results["promoted"]:
                self.db.mark_feedback_used(feedback_ids, model_type="classifier")
                logger.info(f"Marked {len(feedback_ids)} feedback items as used for classifier")
            
        except Exception as e:
            logger.error(f"Retraining failed: {e}")
            results["error"] = str(e)
        
        results["end_time"] = datetime.utcnow().isoformat()
        
        return results
    
    def _get_run_id_for_version(self, version: str) -> Optional[str]:
        """Get MLflow run ID for a model version."""
        try:
            versions = self.mlflow_manager.client.search_model_versions(
                f"name='{CLASSIFIER_MODEL_NAME}'"
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
    
    pipeline = ClassifierRetrainPipeline()
    return pipeline.run()


if __name__ == "__main__":
    check_and_retrain()
