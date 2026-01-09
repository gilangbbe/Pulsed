"""Reddit data source for fetching ML/AI discussions."""

import hashlib
from datetime import datetime
from typing import List, Dict, Any, Optional

from loguru import logger

try:
    import praw
    PRAW_AVAILABLE = True
except ImportError:
    PRAW_AVAILABLE = False
    logger.warning("PRAW not installed. Reddit source will be disabled.")


from ...utils.config import config


class RedditSource:
    """Fetch posts from ML-related subreddits."""
    
    # ML/AI focused subreddits
    SUBREDDITS = [
        "MachineLearning",
        "LocalLLaMA",
        "deeplearning",
        "learnmachinelearning",
        "artificial",
        "LanguageTechnology",
    ]
    
    def __init__(self):
        self.reddit = None
        if PRAW_AVAILABLE and config.reddit.client_id:
            try:
                self.reddit = praw.Reddit(
                    client_id=config.reddit.client_id,
                    client_secret=config.reddit.client_secret,
                    user_agent=config.reddit.user_agent,
                )
                logger.info("Reddit API initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Reddit API: {e}")
    
    def _generate_article_id(self, post) -> str:
        """Generate a unique article ID from Reddit post."""
        return f"reddit_{post.id}"
    
    def _is_quality_post(self, post) -> bool:
        """Filter for quality posts."""
        # Skip low-quality posts
        if post.score < 10:
            return False
        
        # Skip very short posts
        if post.selftext and len(post.selftext) < 50:
            return False
        
        # Skip certain flair types (if available)
        if hasattr(post, 'link_flair_text') and post.link_flair_text:
            skip_flairs = ['meme', 'humor', 'off-topic']
            if post.link_flair_text.lower() in skip_flairs:
                return False
        
        return True
    
    def fetch(
        self,
        subreddits: Optional[List[str]] = None,
        limit: int = 50,
        time_filter: str = "day",
    ) -> List[Dict[str, Any]]:
        """
        Fetch top posts from subreddits.
        
        Args:
            subreddits: List of subreddit names to fetch from
            limit: Maximum posts per subreddit
            time_filter: Time filter for top posts ('hour', 'day', 'week', 'month', 'year', 'all')
            
        Returns:
            List of article dictionaries
        """
        if not self.reddit:
            logger.warning("Reddit API not initialized, skipping fetch")
            return []
        
        if subreddits is None:
            subreddits = self.SUBREDDITS
        
        articles = []
        
        for subreddit_name in subreddits:
            try:
                logger.info(f"Fetching from r/{subreddit_name}")
                subreddit = self.reddit.subreddit(subreddit_name)
                
                # Get top posts from the time period
                for post in subreddit.top(time_filter=time_filter, limit=limit):
                    if not self._is_quality_post(post):
                        continue
                    
                    # Combine title and selftext for full content
                    full_text = post.selftext if post.selftext else None
                    
                    # For link posts, the URL is external
                    url = post.url if not post.is_self else f"https://reddit.com{post.permalink}"
                    
                    article = {
                        "article_id": self._generate_article_id(post),
                        "source": f"reddit_{subreddit_name}",
                        "title": post.title,
                        "abstract": post.selftext[:500] if post.selftext else None,
                        "full_text": full_text,
                        "url": url,
                        "published_date": datetime.fromtimestamp(post.created_utc),
                        "metadata": {
                            "reddit_id": post.id,
                            "subreddit": subreddit_name,
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "num_comments": post.num_comments,
                            "author": str(post.author) if post.author else "[deleted]",
                            "flair": post.link_flair_text,
                            "is_self": post.is_self,
                            "external_url": post.url if not post.is_self else None,
                        }
                    }
                    articles.append(article)
                
                logger.info(f"Fetched {len([a for a in articles if subreddit_name in a['source']])} posts from r/{subreddit_name}")
                
            except Exception as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}")
                continue
        
        return articles
    
    def fetch_hot(
        self,
        subreddits: Optional[List[str]] = None,
        limit: int = 25,
    ) -> List[Dict[str, Any]]:
        """
        Fetch hot/trending posts from subreddits.
        
        Args:
            subreddits: List of subreddit names
            limit: Maximum posts per subreddit
            
        Returns:
            List of article dictionaries
        """
        if not self.reddit:
            return []
        
        if subreddits is None:
            subreddits = self.SUBREDDITS
        
        articles = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = self.reddit.subreddit(subreddit_name)
                
                for post in subreddit.hot(limit=limit):
                    if not self._is_quality_post(post):
                        continue
                    
                    full_text = post.selftext if post.selftext else None
                    url = post.url if not post.is_self else f"https://reddit.com{post.permalink}"
                    
                    article = {
                        "article_id": self._generate_article_id(post),
                        "source": f"reddit_{subreddit_name}",
                        "title": post.title,
                        "abstract": post.selftext[:500] if post.selftext else None,
                        "full_text": full_text,
                        "url": url,
                        "published_date": datetime.fromtimestamp(post.created_utc),
                        "metadata": {
                            "reddit_id": post.id,
                            "subreddit": subreddit_name,
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "num_comments": post.num_comments,
                            "author": str(post.author) if post.author else "[deleted]",
                            "flair": post.link_flair_text,
                            "is_self": post.is_self,
                        }
                    }
                    articles.append(article)
                    
            except Exception as e:
                logger.error(f"Error fetching hot posts from r/{subreddit_name}: {e}")
                continue
        
        return articles
    
    def search(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        limit: int = 50,
        time_filter: str = "month",
    ) -> List[Dict[str, Any]]:
        """
        Search for posts matching a query.
        
        Args:
            query: Search query
            subreddits: Subreddits to search in (None = all ML subreddits)
            limit: Maximum results
            time_filter: Time filter
            
        Returns:
            List of article dictionaries
        """
        if not self.reddit:
            return []
        
        articles = []
        
        try:
            if subreddits:
                subreddit_str = "+".join(subreddits)
            else:
                subreddit_str = "+".join(self.SUBREDDITS)
            
            subreddit = self.reddit.subreddit(subreddit_str)
            
            for post in subreddit.search(query, time_filter=time_filter, limit=limit):
                if not self._is_quality_post(post):
                    continue
                
                article = {
                    "article_id": self._generate_article_id(post),
                    "source": f"reddit_{post.subreddit.display_name}",
                    "title": post.title,
                    "abstract": post.selftext[:500] if post.selftext else None,
                    "full_text": post.selftext if post.selftext else None,
                    "url": post.url if not post.is_self else f"https://reddit.com{post.permalink}",
                    "published_date": datetime.fromtimestamp(post.created_utc),
                    "metadata": {
                        "reddit_id": post.id,
                        "subreddit": post.subreddit.display_name,
                        "score": post.score,
                        "num_comments": post.num_comments,
                    }
                }
                articles.append(article)
                
        except Exception as e:
            logger.error(f"Error searching Reddit: {e}")
        
        return articles
