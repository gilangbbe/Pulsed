"""Data drift detection using statistical tests."""

from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import numpy as np
from scipy import stats
from loguru import logger

from ..utils.db import get_db


class DriftDetector:
    """
    Detects data drift in article features and model predictions.
    
    Uses statistical tests to identify significant changes in:
    - Input text characteristics (length, vocabulary)
    - Prediction distribution
    - Confidence scores
    """
    
    def __init__(self, threshold: float = 0.05):
        """
        Initialize drift detector.
        
        Args:
            threshold: P-value threshold for detecting significant drift
        """
        self.threshold = threshold
        self.db = get_db()
    
    def ks_test(
        self,
        reference: List[float],
        current: List[float],
    ) -> Dict[str, Any]:
        """
        Perform Kolmogorov-Smirnov test for distribution drift.
        
        Args:
            reference: Reference distribution (baseline)
            current: Current distribution to compare
            
        Returns:
            Dictionary with test results
        """
        if len(reference) < 5 or len(current) < 5:
            return {
                "drift_detected": False,
                "reason": "Insufficient samples",
                "reference_size": len(reference),
                "current_size": len(current),
            }
        
        statistic, p_value = stats.ks_2samp(reference, current)
        
        return {
            "drift_detected": p_value < self.threshold,
            "statistic": statistic,
            "p_value": p_value,
            "threshold": self.threshold,
            "reference_size": len(reference),
            "current_size": len(current),
        }
    
    def chi_square_test(
        self,
        reference_counts: Dict[str, int],
        current_counts: Dict[str, int],
    ) -> Dict[str, Any]:
        """
        Perform Chi-square test for categorical distribution drift.
        
        Args:
            reference_counts: Reference category counts
            current_counts: Current category counts
            
        Returns:
            Dictionary with test results
        """
        categories = set(reference_counts.keys()) | set(current_counts.keys())
        
        ref_values = [reference_counts.get(c, 0) for c in categories]
        cur_values = [current_counts.get(c, 0) for c in categories]
        
        total_ref = sum(ref_values)
        total_cur = sum(cur_values)
        
        if total_ref == 0 or total_cur == 0:
            return {
                "drift_detected": False,
                "reason": "Insufficient data",
            }
        
        # Normalize to proportions
        ref_props = [v / total_ref for v in ref_values]
        cur_props = [v / total_cur for v in cur_values]
        
        # Expected counts based on reference proportions
        expected = [p * total_cur for p in ref_props]
        
        # Chi-square test
        try:
            statistic, p_value = stats.chisquare(cur_values, f_exp=expected)
            
            return {
                "drift_detected": p_value < self.threshold,
                "statistic": statistic,
                "p_value": p_value,
                "threshold": self.threshold,
                "categories": list(categories),
                "reference_distribution": dict(zip(categories, ref_props)),
                "current_distribution": dict(zip(categories, cur_props)),
            }
        except Exception as e:
            return {
                "drift_detected": False,
                "error": str(e),
            }
    
    def detect_prediction_drift(
        self,
        reference_days: int = 7,
        current_days: int = 1,
    ) -> Dict[str, Any]:
        """
        Detect drift in prediction distribution.
        
        Args:
            reference_days: Number of days for reference period
            current_days: Number of days for current period
            
        Returns:
            Drift detection results
        """
        # Get prediction distributions
        ref_dist = self.db.get_prediction_distribution(days=reference_days)
        cur_dist = self.db.get_prediction_distribution(days=current_days)
        
        # Aggregate by label
        ref_counts = {}
        cur_counts = {}
        
        for item in ref_dist:
            label = item["label"]
            ref_counts[label] = ref_counts.get(label, 0) + item["count"]
        
        for item in cur_dist:
            label = item["label"]
            cur_counts[label] = cur_counts.get(label, 0) + item["count"]
        
        return self.chi_square_test(ref_counts, cur_counts)
    
    def detect_text_drift(
        self,
        reference_texts: List[str],
        current_texts: List[str],
    ) -> Dict[str, Any]:
        """
        Detect drift in text characteristics.
        
        Args:
            reference_texts: Reference period texts
            current_texts: Current period texts
            
        Returns:
            Drift detection results for various text features
        """
        results = {}
        
        # Text length drift
        ref_lengths = [len(t.split()) for t in reference_texts if t]
        cur_lengths = [len(t.split()) for t in current_texts if t]
        
        if ref_lengths and cur_lengths:
            results["text_length"] = self.ks_test(ref_lengths, cur_lengths)
            results["text_length"]["ref_mean"] = np.mean(ref_lengths)
            results["text_length"]["cur_mean"] = np.mean(cur_lengths)
        
        # Vocabulary drift (using unique word ratio)
        def unique_word_ratio(texts):
            if not texts:
                return []
            ratios = []
            for t in texts:
                words = t.lower().split()
                if words:
                    ratios.append(len(set(words)) / len(words))
            return ratios
        
        ref_ratios = unique_word_ratio(reference_texts)
        cur_ratios = unique_word_ratio(current_texts)
        
        if ref_ratios and cur_ratios:
            results["vocabulary_diversity"] = self.ks_test(ref_ratios, cur_ratios)
        
        # Overall drift score (average of individual drifts)
        drift_scores = []
        for key, result in results.items():
            if result.get("drift_detected"):
                drift_scores.append(1.0)
            elif "p_value" in result:
                # Use 1 - p_value as a soft drift score
                drift_scores.append(1 - result["p_value"])
        
        results["overall_drift_score"] = np.mean(drift_scores) if drift_scores else 0.0
        results["drift_detected"] = results["overall_drift_score"] > 0.5
        
        return results
    
    def get_drift_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive drift report.
        
        Returns:
            Dictionary with all drift detection results
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "prediction_drift": self.detect_prediction_drift(),
        }
        
        # Add alert level
        if report["prediction_drift"].get("drift_detected"):
            report["alert_level"] = "high"
            report["recommendation"] = "Consider investigating recent data and retraining models"
        elif report["prediction_drift"].get("p_value", 1) < 0.1:
            report["alert_level"] = "medium"
            report["recommendation"] = "Monitor closely, drift may be emerging"
        else:
            report["alert_level"] = "low"
            report["recommendation"] = "No action needed"
        
        return report
