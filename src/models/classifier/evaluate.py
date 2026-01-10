"""Classifier evaluation module."""

from typing import Dict, Any, List, Optional
import numpy as np
from sklearn.metrics import (
    accuracy_score,
    precision_recall_fscore_support,
    confusion_matrix,
    classification_report,
)
from loguru import logger

from ...utils.config import LABELS, ID_TO_LABEL


class ClassifierEvaluator:
    """Evaluator for classification metrics."""
    
    def __init__(self):
        self.labels = LABELS
    
    def compute_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, float]:
        """
        Compute classification metrics.
        
        Args:
            y_true: Ground truth labels (as integers)
            y_pred: Predicted labels (as integers)
            
        Returns:
            Dictionary of metrics
        """
        accuracy = accuracy_score(y_true, y_pred)
        
        precision, recall, f1, _ = precision_recall_fscore_support(
            y_true, y_pred, average="macro", zero_division=0
        )
        
        precision_weighted, recall_weighted, f1_weighted, _ = precision_recall_fscore_support(
            y_true, y_pred, average="weighted", zero_division=0
        )
        
        return {
            "accuracy": accuracy,
            "precision_macro": precision,
            "recall_macro": recall,
            "f1_macro": f1,
            "precision_weighted": precision_weighted,
            "recall_weighted": recall_weighted,
            "f1_weighted": f1_weighted,
        }
    
    def compute_per_class_metrics(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, Dict[str, float]]:
        """
        Compute per-class metrics.
        
        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            
        Returns:
            Dictionary with metrics for each class
        """
        precision, recall, f1, support = precision_recall_fscore_support(
            y_true, y_pred, average=None, zero_division=0
        )
        
        per_class = {}
        for i, label in enumerate(self.labels):
            per_class[label] = {
                "precision": precision[i] if i < len(precision) else 0.0,
                "recall": recall[i] if i < len(recall) else 0.0,
                "f1": f1[i] if i < len(f1) else 0.0,
                "support": int(support[i]) if i < len(support) else 0,
            }
        
        return per_class
    
    def get_confusion_matrix(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> Dict[str, Any]:
        """
        Compute confusion matrix.
        
        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            
        Returns:
            Dictionary with confusion matrix and labels
        """
        cm = confusion_matrix(y_true, y_pred)
        
        return {
            "matrix": cm.tolist(),
            "labels": self.labels,
        }
    
    def get_classification_report(
        self,
        y_true: np.ndarray,
        y_pred: np.ndarray,
    ) -> str:
        """
        Get a formatted classification report.
        
        Args:
            y_true: Ground truth labels
            y_pred: Predicted labels
            
        Returns:
            Formatted classification report string
        """
        return classification_report(
            y_true, y_pred,
            target_names=self.labels,
            zero_division=0,
        )
    
    def evaluate_predictions(
        self,
        predictions: List[Dict[str, Any]],
        ground_truth: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate predictions against ground truth.
        
        Args:
            predictions: List of dicts with 'article_id' and 'predicted_label'
            ground_truth: List of dicts with 'article_id' and 'label'
            
        Returns:
            Complete evaluation results
        """
        # Build lookup for ground truth
        gt_lookup = {g["article_id"]: g["label"] for g in ground_truth}
        
        y_true = []
        y_pred = []
        
        for pred in predictions:
            article_id = pred["article_id"]
            if article_id in gt_lookup:
                true_label = gt_lookup[article_id]
                pred_label = pred["predicted_label"]
                
                if true_label in LABELS and pred_label in LABELS:
                    y_true.append(LABELS.index(true_label))
                    y_pred.append(LABELS.index(pred_label))
        
        if not y_true:
            logger.warning("No matching predictions found for evaluation")
            return {"error": "No matching predictions"}
        
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)
        
        metrics = self.compute_metrics(y_true, y_pred)
        per_class = self.compute_per_class_metrics(y_true, y_pred)
        cm = self.get_confusion_matrix(y_true, y_pred)
        
        return {
            "metrics": metrics,
            "per_class": per_class,
            "confusion_matrix": cm,
            "num_samples": len(y_true),
            "report": self.get_classification_report(y_true, y_pred),
        }
    
    def compare_models(
        self,
        model_a_metrics: Dict[str, float],
        model_b_metrics: Dict[str, float],
        primary_metric: str = "accuracy",
    ) -> Dict[str, Any]:
        """
        Compare two models based on their metrics.
        
        Args:
            model_a_metrics: Metrics from model A
            model_b_metrics: Metrics from model B
            primary_metric: Main metric for comparison
            
        Returns:
            Comparison results
        """
        a_score = model_a_metrics.get(primary_metric, 0)
        b_score = model_b_metrics.get(primary_metric, 0)
        
        improvement = b_score - a_score
        
        return {
            "model_a_score": a_score,
            "model_b_score": b_score,
            "improvement": improvement,
            "improvement_pct": (improvement / a_score * 100) if a_score > 0 else 0,
            "model_b_is_better": improvement > 0,
            "metric": primary_metric,
        }
