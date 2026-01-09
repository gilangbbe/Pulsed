"""Main data fetcher that aggregates all sources."""

from typing import List, Dict, Any, Optional
from datetime import datetime

from loguru import logger

from .sources import ArxivSource, RedditSource, PapersWithCodeSource, RSSFeedSource
from .preprocess import Preprocessor
from ..utils.db import get_db


class DataFetcher:
    """
    Main data fetcher that aggregates articles from all sources.
    
    This class coordinates fetching from multiple sources,
    deduplication, and storage to the database.
    """
    
    def __init__(self):
        self.arxiv = ArxivSource()
        self.reddit = RedditSource()
        self.pwc = PapersWithCodeSource()
        self.rss = RSSFeedSource()
        self.preprocessor = Preprocessor()
        self.db = get_db()
    
    def fetch_all(
        self,
        include_arxiv: bool = True,
        include_reddit: bool = True,
        include_pwc: bool = True,
        include_rss: bool = True,
        days_back: int = 1,
        data_version: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Fetch articles from all enabled sources.
        
        Args:
            include_arxiv: Whether to fetch from ArXiv
            include_reddit: Whether to fetch from Reddit
            include_pwc: Whether to fetch from Papers With Code
            include_rss: Whether to fetch from RSS feeds
            days_back: Number of days to look back
            data_version: DVC commit hash for versioning
            
        Returns:
            Dictionary with fetch statistics
        """
        logger.info("Starting data fetch from all sources")
        all_articles = []
        stats = {
            "start_time": datetime.utcnow().isoformat(),
            "sources": {},
            "total_fetched": 0,
            "total_new": 0,
            "total_duplicates": 0,
        }
        
        # Fetch from ArXiv
        if include_arxiv:
            try:
                arxiv_articles = self.arxiv.fetch(days_back=days_back)
                all_articles.extend(arxiv_articles)
                stats["sources"]["arxiv"] = len(arxiv_articles)
                logger.info(f"Fetched {len(arxiv_articles)} articles from ArXiv")
            except Exception as e:
                logger.error(f"ArXiv fetch failed: {e}")
                stats["sources"]["arxiv"] = {"error": str(e)}
        
        # Fetch from Reddit
        if include_reddit:
            try:
                reddit_articles = self.reddit.fetch(time_filter="day")
                all_articles.extend(reddit_articles)
                stats["sources"]["reddit"] = len(reddit_articles)
                logger.info(f"Fetched {len(reddit_articles)} articles from Reddit")
            except Exception as e:
                logger.error(f"Reddit fetch failed: {e}")
                stats["sources"]["reddit"] = {"error": str(e)}
        
        # Fetch from Papers With Code
        if include_pwc:
            try:
                pwc_articles = self.pwc.fetch_trending()
                all_articles.extend(pwc_articles)
                stats["sources"]["papers_with_code"] = len(pwc_articles)
                logger.info(f"Fetched {len(pwc_articles)} articles from Papers With Code")
            except Exception as e:
                logger.error(f"Papers With Code fetch failed: {e}")
                stats["sources"]["papers_with_code"] = {"error": str(e)}
        
        # Fetch from RSS feeds
        if include_rss:
            try:
                rss_articles = self.rss.fetch()
                all_articles.extend(rss_articles)
                stats["sources"]["rss"] = len(rss_articles)
                logger.info(f"Fetched {len(rss_articles)} articles from RSS feeds")
            except Exception as e:
                logger.error(f"RSS fetch failed: {e}")
                stats["sources"]["rss"] = {"error": str(e)}
        
        stats["total_fetched"] = len(all_articles)
        
        # Preprocess and deduplicate
        logger.info("Preprocessing and deduplicating articles")
        processed_articles = self.preprocessor.process_batch(all_articles)
        unique_articles = self.preprocessor.deduplicate(processed_articles)
        
        stats["after_dedup"] = len(unique_articles)
        stats["total_duplicates"] = len(processed_articles) - len(unique_articles)
        
        # Store to database
        logger.info("Storing articles to database")
        new_count = 0
        for article in unique_articles:
            try:
                inserted = self.db.insert_article(
                    article_id=article["article_id"],
                    source=article["source"],
                    title=article["title"],
                    url=article["url"],
                    abstract=article.get("abstract"),
                    full_text=article.get("full_text"),
                    published_date=article.get("published_date"),
                    metadata=article.get("metadata"),
                    data_version=data_version,
                )
                if inserted:
                    new_count += 1
            except Exception as e:
                logger.warning(f"Failed to insert article {article['article_id']}: {e}")
        
        stats["total_new"] = new_count
        stats["end_time"] = datetime.utcnow().isoformat()
        
        logger.info(f"Fetch complete: {new_count} new articles stored")
        return stats
    
    def fetch_arxiv_only(
        self,
        categories: Optional[List[str]] = None,
        days_back: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch only from ArXiv."""
        return self.arxiv.fetch(categories=categories, days_back=days_back)
    
    def fetch_reddit_only(
        self,
        subreddits: Optional[List[str]] = None,
        time_filter: str = "day",
    ) -> List[Dict[str, Any]]:
        """Fetch only from Reddit."""
        return self.reddit.fetch(subreddits=subreddits, time_filter=time_filter)
    
    def search(
        self,
        query: str,
        sources: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search across multiple sources.
        
        Args:
            query: Search query
            sources: List of sources to search ('arxiv', 'reddit', 'pwc')
            
        Returns:
            Combined list of search results
        """
        if sources is None:
            sources = ["arxiv", "pwc"]
        
        results = []
        
        if "arxiv" in sources:
            results.extend(self.arxiv.search(query))
        
        if "reddit" in sources:
            results.extend(self.reddit.search(query))
        
        if "pwc" in sources:
            results.extend(self.pwc.search(query))
        
        # Deduplicate results
        return self.preprocessor.deduplicate(results)
