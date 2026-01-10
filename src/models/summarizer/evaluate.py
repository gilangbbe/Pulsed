"""Summarizer evaluation module."""

from typing import Dict, Any, List, Optional
import numpy as np
from loguru import logger

from ...utils.summary_utils import RougeEvaluator


class SummarizerEvaluator:
    """Evaluator for summarization quality."""
    
    def __init__(self):
        self.rouge_evaluator = RougeEvaluator()
    
    def evaluate_summary(
        self,
        reference: str,
        generated: str,
    ) -> Dict[str, float]:
        """
        Evaluate a single summary.
        
        Args:
            reference: Reference/source text
            generated: Generated summary
            
        Returns:
            Dictionary of ROUGE scores
        """
        return self.rouge_evaluator.score(reference, generated)
    
    def evaluate_batch(
        self,
        references: List[str],
        generated: List[str],
    ) -> Dict[str, float]:
        """
        Evaluate a batch of summaries.
        
        Args:
            references: List of reference texts
            generated: List of generated summaries
            
        Returns:
            Dictionary of average ROUGE scores
        """
        return self.rouge_evaluator.batch_score(references, generated)
    
    def compute_metrics_with_feedback(
        self,
        summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Compute metrics combining ROUGE and user feedback.
        
        Args:
            summaries: List of summaries with 'rouge_l' and optional 'user_rating'
            
        Returns:
            Dictionary of aggregated metrics
        """
        if not summaries:
            return {"error": "No summaries to evaluate"}
        
        # ROUGE metrics
        rouge_1_scores = [s.get("rouge_1", 0) for s in summaries if s.get("rouge_1")]
        rouge_2_scores = [s.get("rouge_2", 0) for s in summaries if s.get("rouge_2")]
        rouge_l_scores = [s.get("rouge_l", 0) for s in summaries if s.get("rouge_l")]
        
        # User feedback
        ratings = []
        rating_map = {"good": 1.0, "bad": 0.0, "edited": 0.5}
        for s in summaries:
            rating = s.get("user_rating") or s.get("summary_rating")
            if rating and rating in rating_map:
                ratings.append(rating_map[rating])
        
        metrics = {
            "num_summaries": len(summaries),
        }
        
        if rouge_1_scores:
            metrics["avg_rouge_1"] = np.mean(rouge_1_scores)
        if rouge_2_scores:
            metrics["avg_rouge_2"] = np.mean(rouge_2_scores)
        if rouge_l_scores:
            metrics["avg_rouge_l"] = np.mean(rouge_l_scores)
        
        if ratings:
            metrics["avg_user_rating"] = np.mean(ratings)
            metrics["good_pct"] = sum(1 for r in ratings if r == 1.0) / len(ratings)
            metrics["bad_pct"] = sum(1 for r in ratings if r == 0.0) / len(ratings)
            metrics["num_rated"] = len(ratings)
        
        return metrics
    
    def evaluate_length_appropriateness(
        self,
        summaries: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Evaluate if summaries are appropriately sized.
        
        Args:
            summaries: List of summaries with 'summary_text' and 'summary_type'
            
        Returns:
            Dictionary with length analysis
        """
        brief_lengths = []
        detailed_lengths = []
        
        for s in summaries:
            text = s.get("summary_text", "")
            summary_type = s.get("summary_type", "brief")
            word_count = len(text.split())
            
            if summary_type == "brief":
                brief_lengths.append(word_count)
            else:
                detailed_lengths.append(word_count)
        
        results = {}
        
        if brief_lengths:
            results["brief"] = {
                "avg_length": np.mean(brief_lengths),
                "min_length": min(brief_lengths),
                "max_length": max(brief_lengths),
                "count": len(brief_lengths),
                "target_range": "30-100 words",
                "in_range_pct": sum(1 for l in brief_lengths if 30 <= l <= 100) / len(brief_lengths),
            }
        
        if detailed_lengths:
            results["detailed"] = {
                "avg_length": np.mean(detailed_lengths),
                "min_length": min(detailed_lengths),
                "max_length": max(detailed_lengths),
                "count": len(detailed_lengths),
                "target_range": "100-250 words",
                "in_range_pct": sum(1 for l in detailed_lengths if 100 <= l <= 250) / len(detailed_lengths),
            }
        
        return results
    
    def compare_models(
        self,
        model_a_metrics: Dict[str, float],
        model_b_metrics: Dict[str, float],
        primary_metric: str = "avg_rouge_l",
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
        
        # Also check user rating if available
        user_rating_improvement = None
        if "avg_user_rating" in model_a_metrics and "avg_user_rating" in model_b_metrics:
            user_rating_improvement = (
                model_b_metrics["avg_user_rating"] - model_a_metrics["avg_user_rating"]
            )
        
        return {
            "model_a_score": a_score,
            "model_b_score": b_score,
            "improvement": improvement,
            "improvement_pct": (improvement / a_score * 100) if a_score > 0 else 0,
            "model_b_is_better": improvement > 0,
            "metric": primary_metric,
            "user_rating_improvement": user_rating_improvement,
        }
    
    def generate_report(
        self,
        summaries: List[Dict[str, Any]],
    ) -> str:
        """
        Generate a text report of summarization quality.
        
        Args:
            summaries: List of summaries to analyze
            
        Returns:
            Formatted report string
        """
        metrics = self.compute_metrics_with_feedback(summaries)
        length_analysis = self.evaluate_length_appropriateness(summaries)
        
        report = []
        report.append("=" * 50)
        report.append("SUMMARIZATION QUALITY REPORT")
        report.append("=" * 50)
        report.append("")
        report.append(f"Total summaries evaluated: {metrics.get('num_summaries', 0)}")
        report.append("")
        report.append("ROUGE Scores:")
        report.append(f"  ROUGE-1: {metrics.get('avg_rouge_1', 'N/A'):.4f}")
        report.append(f"  ROUGE-2: {metrics.get('avg_rouge_2', 'N/A'):.4f}")
        report.append(f"  ROUGE-L: {metrics.get('avg_rouge_l', 'N/A'):.4f}")
        report.append("")
        
        if "avg_user_rating" in metrics:
            report.append("User Feedback:")
            report.append(f"  Average rating: {metrics['avg_user_rating']:.2f}")
            report.append(f"  Good: {metrics['good_pct']*100:.1f}%")
            report.append(f"  Bad: {metrics['bad_pct']*100:.1f}%")
            report.append(f"  Total rated: {metrics['num_rated']}")
            report.append("")
        
        report.append("Length Analysis:")
        for summary_type, data in length_analysis.items():
            report.append(f"  {summary_type.title()} summaries:")
            report.append(f"    Count: {data['count']}")
            report.append(f"    Avg length: {data['avg_length']:.1f} words")
            report.append(f"    Target: {data['target_range']}")
            report.append(f"    In range: {data['in_range_pct']*100:.1f}%")
        
        report.append("")
        report.append("=" * 50)
        
        return "\n".join(report)
