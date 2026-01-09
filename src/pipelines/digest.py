"""Email digest generation."""

import json
from datetime import datetime
from typing import Dict, Any, List, Optional

from loguru import logger

from ..utils.db import get_db
from ..utils.email_utils import EmailSender
from ..utils.config import config


class DigestGenerator:
    """
    Generates and sends daily email digests.
    
    Collects articles classified as 'important' or 'worth_learning',
    formats them with their summaries, and sends via email.
    """
    
    def __init__(self):
        self.db = get_db()
        self.email_sender = EmailSender()
    
    def get_digest_content(
        self,
        hours_back: int = 24,
    ) -> Dict[str, Any]:
        """
        Get content for the digest.
        
        Args:
            hours_back: Number of hours to look back for articles
            
        Returns:
            Dictionary with articles grouped by category
        """
        articles = self.db.get_digest_articles(since_hours=hours_back)
        
        # Parse JSON fields
        for category in articles:
            for article in articles[category]:
                if isinstance(article.get("key_takeaways"), str):
                    try:
                        article["key_takeaways"] = json.loads(article["key_takeaways"])
                    except:
                        article["key_takeaways"] = None
        
        return articles
    
    def get_digest_stats(self, hours_back: int = 24) -> Dict[str, Any]:
        """Get statistics for the digest."""
        distribution = self.db.get_prediction_distribution(days=1)
        
        total = sum(d["count"] for d in distribution)
        garbage = sum(d["count"] for d in distribution if d["label"] == "garbage")
        
        stats = {
            "total": total,
            "garbage": garbage,
            "garbage_pct": round(garbage / total * 100, 1) if total > 0 else 0,
        }
        
        # Add trend information
        week_dist = self.db.get_prediction_distribution(days=7)
        if week_dist:
            # Calculate week-over-week trends
            this_week = sum(d["count"] for d in week_dist)
            stats["weekly_total"] = this_week
        
        return stats
    
    def generate_digest(
        self,
        hours_back: int = 24,
        feedback_base_url: Optional[str] = None,
    ) -> str:
        """
        Generate the HTML digest content.
        
        Args:
            hours_back: Number of hours to look back
            feedback_base_url: Base URL for feedback links
            
        Returns:
            HTML string of the digest
        """
        articles = self.get_digest_content(hours_back)
        stats = self.get_digest_stats(hours_back)
        
        if feedback_base_url is None:
            feedback_base_url = f"http://localhost:{config.api.port}"
        
        html = self.email_sender.generate_digest_html(
            worth_learning=articles.get("worth_learning", []),
            important=articles.get("important", []),
            stats=stats,
            feedback_base_url=feedback_base_url,
        )
        
        return html
    
    def send_digest(
        self,
        hours_back: int = 24,
        feedback_base_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate and send the digest email.
        
        Args:
            hours_back: Number of hours to look back
            feedback_base_url: Base URL for feedback links
            
        Returns:
            Dictionary with send status and article counts
        """
        logger.info("Generating daily digest...")
        
        articles = self.get_digest_content(hours_back)
        stats = self.get_digest_stats(hours_back)
        
        worth_learning = articles.get("worth_learning", [])
        important = articles.get("important", [])
        
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "worth_learning_count": len(worth_learning),
            "important_count": len(important),
            "stats": stats,
        }
        
        if not worth_learning and not important:
            logger.info("No articles to send in digest")
            result["sent"] = False
            result["reason"] = "No articles"
            return result
        
        if feedback_base_url is None:
            feedback_base_url = f"http://localhost:{config.api.port}"
        
        success = self.email_sender.send_digest(
            worth_learning=worth_learning,
            important=important,
            stats=stats,
            feedback_base_url=feedback_base_url,
        )
        
        result["sent"] = success
        
        if success:
            logger.info(
                f"Digest sent: {len(worth_learning)} worth_learning, "
                f"{len(important)} important"
            )
        else:
            logger.warning("Failed to send digest")
            result["reason"] = "Email send failed"
        
        return result
    
    def preview_digest(self, hours_back: int = 24) -> Dict[str, Any]:
        """
        Preview what would be in the digest without sending.
        
        Args:
            hours_back: Number of hours to look back
            
        Returns:
            Dictionary with digest preview data
        """
        articles = self.get_digest_content(hours_back)
        stats = self.get_digest_stats(hours_back)
        
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "articles": articles,
            "stats": stats,
            "worth_learning_titles": [
                a["title"] for a in articles.get("worth_learning", [])
            ],
            "important_titles": [
                a["title"] for a in articles.get("important", [])
            ],
        }


def send_daily_digest():
    """Entry point for cron job."""
    from ..utils.config import setup_logging
    setup_logging()
    
    generator = DigestGenerator()
    return generator.send_digest()


if __name__ == "__main__":
    send_daily_digest()
