"""RSS feed data source for ML blogs and news."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

import feedparser
from loguru import logger


class RSSFeedSource:
    """Fetch articles from RSS feeds of ML blogs and news sites."""
    
    # Default ML/AI focused RSS feeds (TOS compliant only)
    DEFAULT_FEEDS = {
        "openai": "https://openai.com/blog/rss.xml",
        "google_ai": "https://blog.google/technology/ai/rss/",
        "deepmind": "https://deepmind.com/blog/rss.xml",
        "meta_ai": "https://ai.meta.com/blog/rss/",
        "anthropic": "https://www.anthropic.com/feed.xml",
        "huggingface": "https://huggingface.co/blog/feed.xml",
        "distill": "https://distill.pub/rss.xml",
        "pytorch": "https://pytorch.org/blog/feed.xml",
        "tensorflow": "https://blog.tensorflow.org/feeds/posts/default?alt=rss",
        "mit_news_ai": "https://news.mit.edu/topic/mitartificial-intelligence2-rss.xml",
        # Removed: Towards Data Science (Medium TOS prohibits automated scraping)
    }
    
    def __init__(self, custom_feeds: Optional[Dict[str, str]] = None, verify_ssl: bool = False):
        """
        Initialize RSS feed source.
        
        Args:
            custom_feeds: Additional custom feeds to include {name: url}
            verify_ssl: Whether to verify SSL certificates (disable for local testing)
        """
        self.feeds = self.DEFAULT_FEEDS.copy()
        if custom_feeds:
            self.feeds.update(custom_feeds)
        self.verify_ssl = verify_ssl
        
        # Configure SSL if needed
        if not verify_ssl:
            import ssl
            if hasattr(ssl, '_create_unverified_context'):
                ssl._create_default_https_context = ssl._create_unverified_context
                logger.warning("SSL verification disabled for RSS feeds")
    
    def _generate_article_id(self, entry: Dict, feed_name: str) -> str:
        """Generate a unique article ID from RSS entry."""
        # Use the link or ID from the entry
        identifier = entry.get("id") or entry.get("link") or entry.get("title", "")
        hash_input = f"{feed_name}_{identifier}"
        return f"rss_{hashlib.md5(hash_input.encode()).hexdigest()[:16]}"
    
    def _parse_date(self, entry: Dict) -> Optional[datetime]:
        """Parse publication date from entry."""
        for date_field in ["published_parsed", "updated_parsed", "created_parsed"]:
            date_tuple = entry.get(date_field)
            if date_tuple:
                try:
                    return datetime(*date_tuple[:6])
                except Exception:
                    continue
        
        # Try string parsing as fallback
        for date_field in ["published", "updated", "created"]:
            date_str = entry.get(date_field)
            if date_str:
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except Exception:
                    continue
        
        return None
    
    def _extract_content(self, entry: Dict) -> Optional[str]:
        """Extract full content from entry."""
        # Try different content fields
        if "content" in entry and entry["content"]:
            contents = entry["content"]
            if isinstance(contents, list) and contents:
                return contents[0].get("value", "")
            return str(contents)
        
        if "summary_detail" in entry:
            return entry["summary_detail"].get("value", entry.get("summary", ""))
        
        return entry.get("summary") or entry.get("description")
    
    def fetch(
        self,
        feed_names: Optional[List[str]] = None,
        max_per_feed: int = 20,
        days_back: int = 7,
    ) -> List[Dict[str, Any]]:
        """
        Fetch articles from RSS feeds.
        
        Args:
            feed_names: List of feed names to fetch (None = all feeds)
            max_per_feed: Maximum articles per feed
            days_back: Only fetch articles published within this many days
            
        Returns:
            List of article dictionaries
        """
        if feed_names is None:
            feeds_to_fetch = self.feeds
        else:
            feeds_to_fetch = {k: v for k, v in self.feeds.items() if k in feed_names}
        
        articles = []
        cutoff_date = datetime.utcnow() - timedelta(days=days_back)
        
        for feed_name, feed_url in feeds_to_fetch.items():
            try:
                logger.info(f"Fetching RSS feed: {feed_name}")
                
                feed = feedparser.parse(feed_url)
                
                if feed.bozo and not feed.entries:
                    logger.warning(f"Failed to parse feed {feed_name}: {feed.bozo_exception}")
                    continue
                
                feed_articles = 0
                for entry in feed.entries:
                    if feed_articles >= max_per_feed:
                        break
                    
                    title = entry.get("title", "").strip()
                    if not title:
                        continue
                    
                    # Parse and check publication date
                    published_date = self._parse_date(entry)
                    
                    # Skip articles older than cutoff date
                    if published_date and published_date < cutoff_date:
                        logger.debug(f"Skipping old article from {feed_name}: {title} (published {published_date})")
                        continue
                    
                    # If no date found, use current time (assume recent)
                    if not published_date:
                        logger.debug(f"No date found for article from {feed_name}, assuming recent: {title}")
                        published_date = datetime.utcnow()
                    
                    content = self._extract_content(entry)
                    abstract = content[:500] if content else None
                    
                    article = {
                        "article_id": self._generate_article_id(entry, feed_name),
                        "source": f"rss_{feed_name}",
                        "title": title,
                        "abstract": abstract,
                        "full_text": content,
                        "url": entry.get("link", ""),
                        "published_date": published_date,
                        "metadata": {
                            "feed_name": feed_name,
                            "feed_url": feed_url,
                            "author": entry.get("author"),
                            "tags": [tag.get("term") for tag in entry.get("tags", [])],
                            "entry_id": entry.get("id"),
                        }
                    }
                    articles.append(article)
                    feed_articles += 1
                
                logger.info(f"Fetched {feed_articles} recent articles from {feed_name}")
                
            except Exception as e:
                logger.error(f"Error fetching feed {feed_name}: {e}")
                continue
        
        return articles
    
    def add_feed(self, name: str, url: str):
        """Add a new feed to the source."""
        self.feeds[name] = url
        logger.info(f"Added new feed: {name}")
    
    def remove_feed(self, name: str):
        """Remove a feed from the source."""
        if name in self.feeds:
            del self.feeds[name]
            logger.info(f"Removed feed: {name}")
    
    def list_feeds(self) -> Dict[str, str]:
        """List all configured feeds."""
        return self.feeds.copy()
    
    def test_feed(self, url: str) -> Dict[str, Any]:
        """
        Test if a feed URL is valid and accessible.
        
        Args:
            url: Feed URL to test
            
        Returns:
            Dict with status and feed info
        """
        try:
            feed = feedparser.parse(url)
            
            if feed.bozo and not feed.entries:
                return {
                    "valid": False,
                    "error": str(feed.bozo_exception),
                }
            
            return {
                "valid": True,
                "title": feed.feed.get("title", "Unknown"),
                "entries": len(feed.entries),
                "link": feed.feed.get("link", ""),
            }
            
        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }
