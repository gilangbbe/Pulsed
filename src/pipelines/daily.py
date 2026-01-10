"""Daily pipeline for data ingestion and processing."""

import subprocess
from datetime import datetime
from typing import Dict, Any, Optional

from loguru import logger

from ..data import DataFetcher
from ..models import ModelOrchestrator
from ..utils.db import get_db
from ..utils.config import config


class DailyPipeline:
    """
    Daily pipeline that orchestrates:
    1. Data fetching from all sources
    2. Classification of new articles
    3. Summarization of important articles
    """
    
    def __init__(self):
        self.db = get_db()
        self.data_fetcher = DataFetcher()
        self.orchestrator = None  # Lazy load
    
    def _get_data_version(self) -> Optional[str]:
        """Get current DVC data version."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                cwd=".",
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except Exception:
            pass
        return None
    
    def run_fetch(self) -> Dict[str, Any]:
        """Run data fetching step."""
        logger.info("Starting data fetch...")
        data_version = self._get_data_version()
        
        stats = self.data_fetcher.fetch_all(
            include_arxiv=True,
            include_reddit=True,
            include_pwc=True,
            include_rss=True,
            days_back=1,
            data_version=data_version,
        )
        
        logger.info(f"Fetch complete: {stats['total_new']} new articles")
        return stats
    
    def run_inference(self) -> Dict[str, Any]:
        """Run classification and summarization."""
        logger.info("Starting inference pipeline...")
        
        # Lazy load orchestrator (models are expensive)
        if self.orchestrator is None:
            self.orchestrator = ModelOrchestrator(use_mlflow=True)
        
        stats = self.orchestrator.process_articles()
        
        logger.info(
            f"Inference complete: {stats['articles_processed']} articles, "
            f"{stats['summaries_generated']} summaries"
        )
        return stats
    
    def run(self) -> Dict[str, Any]:
        """Run the complete daily pipeline."""
        logger.info("=" * 50)
        logger.info("Starting daily pipeline")
        logger.info("=" * 50)
        
        start_time = datetime.utcnow()
        results = {
            "start_time": start_time.isoformat(),
            "fetch": None,
            "inference": None,
            "digest": None,
            "errors": [],
        }
        
        # Step 1: Fetch data
        try:
            results["fetch"] = self.run_fetch()
        except Exception as e:
            logger.error(f"Fetch failed: {e}")
            results["errors"].append(f"Fetch: {str(e)}")
        
        # Step 2: Run inference
        try:
            results["inference"] = self.run_inference()
        except Exception as e:
            logger.error(f"Inference failed: {e}")
            results["errors"].append(f"Inference: {str(e)}")
        
        # Step 3: Send daily digest
        try:
            from .digest import DigestGenerator
            generator = DigestGenerator()
            results["digest"] = generator.send_digest(hours_back=24)
            logger.info(f"Digest sent: {results['digest']}")
        except Exception as e:
            logger.error(f"Digest failed: {e}")
            results["errors"].append(f"Digest: {str(e)}")
        
        end_time = datetime.utcnow()
        results["end_time"] = end_time.isoformat()
        results["duration_seconds"] = (end_time - start_time).total_seconds()
        
        logger.info(f"Daily pipeline complete in {results['duration_seconds']:.2f}s")
        
        return results


def run_hourly():
    """Entry point for hourly cron job (fetch + classify only)."""
    logger.info("Running hourly pipeline...")
    
    pipeline = DailyPipeline()
    
    # Fetch new data
    fetch_stats = pipeline.run_fetch()
    
    # Only run inference if we have new articles
    if fetch_stats.get("total_new", 0) > 0:
        if pipeline.orchestrator is None:
            pipeline.orchestrator = ModelOrchestrator(use_mlflow=True)
        
        inference_stats = pipeline.orchestrator.process_articles()
        return {"fetch": fetch_stats, "inference": inference_stats}
    
    return {"fetch": fetch_stats, "inference": None}


def run_daily():
    """Entry point for daily cron job (full pipeline)."""
    logger.info("Running daily pipeline...")
    
    pipeline = DailyPipeline()
    return pipeline.run()


if __name__ == "__main__":
    from ..utils.config import setup_logging
    setup_logging()
    run_daily()
