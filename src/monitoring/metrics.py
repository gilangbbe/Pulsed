"""Metrics collection and aggregation."""

from typing import Dict, Any, List, Optional
from datetime import datetime, date
import numpy as np
from loguru import logger

from ..utils.db import get_db


class MetricsCollector:
    """
    Collects and aggregates metrics for monitoring.
    
    Tracks:
    - Classification performance
    - Summarization quality
    - Feedback rates
    - System health
    """
    
    def __init__(self):
        self.db = get_db()
    
    def collect_classification_metrics(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Collect classification metrics over time.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with classification metrics
        """
        distribution = self.db.get_prediction_distribution(days=days)
        
        # Aggregate totals
        totals = {"garbage": 0, "important": 0, "worth_learning": 0}
        by_date = {}
        
        for item in distribution:
            label = item["label"]
            date_str = item["date"]
            count = item["count"]
            
            totals[label] = totals.get(label, 0) + count
            
            if date_str not in by_date:
                by_date[date_str] = {"garbage": 0, "important": 0, "worth_learning": 0}
            by_date[date_str][label] = count
        
        total = sum(totals.values())
        
        return {
            "period_days": days,
            "total_predictions": total,
            "distribution": totals,
            "distribution_pct": {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in totals.items()
            },
            "by_date": by_date,
            "daily_average": round(total / days, 1) if days > 0 else 0,
        }
    
    def collect_summarization_metrics(
        self,
        days: int = 7,
    ) -> Dict[str, Any]:
        """
        Collect summarization metrics.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Dictionary with summarization metrics
        """
        # This would query from summaries table
        # For now, return placeholder structure
        return {
            "period_days": days,
            "total_summaries": 0,
            "avg_rouge_l": 0.0,
            "avg_latency_ms": 0.0,
            "by_type": {
                "brief": {"count": 0, "avg_length": 0},
                "detailed": {"count": 0, "avg_length": 0},
            },
        }
    
    def collect_feedback_metrics(self) -> Dict[str, Any]:
        """
        Collect feedback metrics.
        
        Returns:
            Dictionary with feedback statistics
        """
        stats = self.db.get_feedback_stats()
        
        total_feedback = (
            stats.get("classification_feedback", 0) + 
            stats.get("summary_feedback", 0)
        )
        
        return {
            "classification_feedback": stats.get("classification_feedback", 0),
            "summary_feedback": stats.get("summary_feedback", 0),
            "total_feedback": total_feedback,
            "unused_feedback": stats.get("unused_feedback", 0),
            "feedback_utilization": round(
                (total_feedback - stats.get("unused_feedback", 0)) / 
                max(total_feedback, 1) * 100, 1
            ),
        }
    
    def collect_system_metrics(self) -> Dict[str, Any]:
        """
        Collect system health metrics.
        
        Returns:
            Dictionary with system metrics
        """
        # Count articles by source
        # This would need a new query method
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "database_status": "healthy",
            "model_status": {
                "classifier": "unknown",  # Would check MLflow
                "summarizer": "unknown",
            },
        }
    
    def get_dashboard_data(self, days: int = 7) -> Dict[str, Any]:
        """
        Get all data needed for the monitoring dashboard.
        
        Args:
            days: Number of days to look back
            
        Returns:
            Comprehensive dashboard data
        """
        from .drift import DriftDetector
        
        drift_detector = DriftDetector()
        
        return {
            "generated_at": datetime.utcnow().isoformat(),
            "classification": self.collect_classification_metrics(days),
            "summarization": self.collect_summarization_metrics(days),
            "feedback": self.collect_feedback_metrics(),
            "system": self.collect_system_metrics(),
            "drift": drift_detector.get_drift_report(),
        }
    
    def record_daily_metrics(self) -> Dict[str, Any]:
        """
        Record aggregated metrics for today.
        
        This should be called once per day to create a snapshot.
        
        Returns:
            The recorded metrics
        """
        today = date.today()
        
        classification = self.collect_classification_metrics(days=1)
        summarization = self.collect_summarization_metrics(days=1)
        feedback = self.collect_feedback_metrics()
        
        metrics = {
            "date": today.isoformat(),
            "classifier_version": "unknown",  # Would get from MLflow
            "total_predictions": classification["total_predictions"],
            "avg_confidence": 0.0,  # Would calculate from predictions
            "garbage_pct": classification["distribution_pct"].get("garbage", 0),
            "important_pct": classification["distribution_pct"].get("important", 0),
            "worth_learning_pct": classification["distribution_pct"].get("worth_learning", 0),
            "classification_feedback_count": feedback["classification_feedback"],
            "summarizer_version": "unknown",
            "summaries_generated": summarization["total_summaries"],
            "avg_summary_length_brief": summarization["by_type"]["brief"]["avg_length"],
            "avg_summary_length_detailed": summarization["by_type"]["detailed"]["avg_length"],
            "avg_generation_latency_ms": summarization["avg_latency_ms"],
            "avg_rouge_score": summarization["avg_rouge_l"],
            "summary_feedback_count": feedback["summary_feedback"],
            "good_summary_pct": 0.0,  # Would calculate from feedback
            "data_drift_score": 0.0,  # Would get from drift detector
            "total_articles_fetched": 0,  # Would get from raw_articles
        }
        
        logger.info(f"Recorded daily metrics for {today}")
        
        return metrics
