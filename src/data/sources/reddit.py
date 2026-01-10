"""Reddit data source for fetching ML/AI discussions."""

import time
from datetime import datetime
from typing import List, Dict, Any, Optional

import requests
from loguru import logger


class RedditSource:
    """Fetch posts from ML-related subreddits using JSON endpoint (no API key needed)."""
    
    # ML/AI focused subreddits
    SUBREDDITS = [
        "MachineLearning",
        "LocalLLaMA",
        "deeplearning",
        "learnmachinelearning",
        "artificial",
        "LanguageTechnology",
    ]
    
    def __init__(self, user_agent: str = "PulsedMLNewsFilter/1.0"):
        """
        Initialize Reddit source.
        
        Args:
            user_agent: User agent string for requests
        """
        self.user_agent = user_agent
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': user_agent
        })
        logger.info("Reddit JSON scraper initialized")
    
    def _generate_article_id(self, post_id: str) -> str:
        """Generate a unique article ID from Reddit post ID."""
        return f"reddit_{post_id}"
    
    def _is_quality_post(self, post_data: Dict[str, Any]) -> bool:
        """Filter for quality posts."""
        # Skip low-quality posts
        score = post_data.get('score', 0)
        if score < 10:
            return False
        
        # Skip very short self posts
        selftext = post_data.get('selftext', '')
        is_self = post_data.get('is_self', False)
        if is_self and selftext and len(selftext) < 50:
            return False
        
        # Skip certain flair types
        flair = post_data.get('link_flair_text', '')
        if flair:
            skip_flairs = ['meme', 'humor', 'off-topic']
            if flair.lower() in skip_flairs:
                return False
        
        return True
    
    def _parse_post(self, post_data: Dict[str, Any], subreddit_name: str) -> Dict[str, Any]:
        """
        Parse Reddit JSON post data into article format.
        
        Args:
            post_data: Post data from Reddit JSON API
            subreddit_name: Name of the subreddit
            
        Returns:
            Article dictionary
        """
        post_id = post_data.get('id', '')
        title = post_data.get('title', '')
        selftext = post_data.get('selftext', '')
        is_self = post_data.get('is_self', False)
        
        # For link posts, the URL is external; for self posts, use Reddit URL
        url = post_data.get('url', '')
        if is_self:
            permalink = post_data.get('permalink', '')
            url = f"https://reddit.com{permalink}" if permalink else url
        
        # Extract timestamp
        created_utc = post_data.get('created_utc', 0)
        published_date = datetime.fromtimestamp(created_utc) if created_utc else None
        
        return {
            "article_id": self._generate_article_id(post_id),
            "source": f"reddit_{subreddit_name}",
            "title": title,
            "abstract": selftext[:500] if selftext else None,
            "full_text": selftext if selftext else None,
            "url": url,
            "published_date": published_date,
            "metadata": {
                "reddit_id": post_id,
                "subreddit": subreddit_name,
                "score": post_data.get('score', 0),
                "upvote_ratio": post_data.get('upvote_ratio', 0),
                "num_comments": post_data.get('num_comments', 0),
                "author": post_data.get('author', '[deleted]'),
                "flair": post_data.get('link_flair_text'),
                "is_self": is_self,
                "external_url": post_data.get('url') if not is_self else None,
            }
        }
    
    def _fetch_subreddit_json(
        self,
        subreddit_name: str,
        sort: str = "hot",
        time_filter: str = "day",
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Fetch posts from a subreddit using JSON endpoint.
        
        Args:
            subreddit_name: Subreddit name
            sort: Sort method ('hot', 'top', 'new')
            time_filter: Time filter for 'top' sort
            limit: Maximum posts to fetch
            
        Returns:
            List of article dictionaries
        """
        articles = []
        after = None
        fetched = 0
        
        # Reddit returns ~25 posts per page, we'll paginate to get more
        max_pages = (limit // 25) + 1
        
        for page in range(max_pages):
            try:
                # Build URL
                if sort == "top":
                    url = f"https://www.reddit.com/r/{subreddit_name}/top.json"
                    params = {'t': time_filter, 'limit': 100}
                elif sort == "new":
                    url = f"https://www.reddit.com/r/{subreddit_name}/new.json"
                    params = {'limit': 100}
                else:  # hot
                    url = f"https://www.reddit.com/r/{subreddit_name}/hot.json"
                    params = {'limit': 100}
                
                # Add pagination
                if after:
                    params['after'] = after
                
                # Make request
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract posts
                posts = data.get('data', {}).get('children', [])
                if not posts:
                    break
                
                for post_wrapper in posts:
                    post_data = post_wrapper.get('data', {})
                    
                    # Filter quality
                    if not self._is_quality_post(post_data):
                        continue
                    
                    # Parse and add
                    article = self._parse_post(post_data, subreddit_name)
                    articles.append(article)
                    fetched += 1
                    
                    if fetched >= limit:
                        return articles
                
                # Get next page token
                after = data.get('data', {}).get('after')
                if not after:
                    break
                
                # Rate limiting - be nice to Reddit
                time.sleep(1)
                
            except requests.RequestException as e:
                logger.error(f"Error fetching from r/{subreddit_name}: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error parsing r/{subreddit_name}: {e}")
                break
        
        return articles
    
    def fetch(
        self,
        subreddits: Optional[List[str]] = None,
        limit: int = 50,
        time_filter: str = "day",
    ) -> List[Dict[str, Any]]:
        """
        Fetch top posts from subreddits using JSON endpoint.
        
        Args:
            subreddits: List of subreddit names to fetch from
            limit: Maximum posts per subreddit
            time_filter: Time filter for top posts ('hour', 'day', 'week', 'month', 'year', 'all')
            
        Returns:
            List of article dictionaries
        """
        if subreddits is None:
            subreddits = self.SUBREDDITS
        
        articles = []
        
        for subreddit_name in subreddits:
            logger.info(f"Fetching from r/{subreddit_name}")
            
            subreddit_articles = self._fetch_subreddit_json(
                subreddit_name=subreddit_name,
                sort="top",
                time_filter=time_filter,
                limit=limit,
            )
            
            articles.extend(subreddit_articles)
            logger.info(f"Fetched {len(subreddit_articles)} posts from r/{subreddit_name}")
        
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
        if subreddits is None:
            subreddits = self.SUBREDDITS
        
        articles = []
        
        for subreddit_name in subreddits:
            logger.info(f"Fetching hot posts from r/{subreddit_name}")
            
            subreddit_articles = self._fetch_subreddit_json(
                subreddit_name=subreddit_name,
                sort="hot",
                limit=limit,
            )
            
            articles.extend(subreddit_articles)
            logger.info(f"Fetched {len(subreddit_articles)} hot posts from r/{subreddit_name}")
        
        return articles
    
    def search(
        self,
        query: str,
        subreddits: Optional[List[str]] = None,
        limit: int = 50,
        time_filter: str = "month",
    ) -> List[Dict[str, Any]]:
        """
        Search for posts matching a query across subreddits.
        
        Args:
            query: Search query
            subreddits: Subreddits to search in (None = all ML subreddits)
            limit: Maximum results
            time_filter: Time filter
            
        Returns:
            List of article dictionaries
        """
        if subreddits is None:
            subreddits = self.SUBREDDITS
        
        articles = []
        
        for subreddit_name in subreddits:
            try:
                url = f"https://www.reddit.com/r/{subreddit_name}/search.json"
                params = {
                    'q': query,
                    'restrict_sr': 'on',
                    't': time_filter,
                    'limit': limit,
                }
                
                response = self.session.get(url, params=params, timeout=10)
                response.raise_for_status()
                
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                
                for post_wrapper in posts:
                    post_data = post_wrapper.get('data', {})
                    
                    if not self._is_quality_post(post_data):
                        continue
                    
                    article = self._parse_post(post_data, subreddit_name)
                    articles.append(article)
                
                time.sleep(1)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error searching r/{subreddit_name}: {e}")
                continue
        
        return articles
