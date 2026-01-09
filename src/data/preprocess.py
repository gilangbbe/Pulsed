"""Data preprocessing utilities."""

import re
import hashlib
from typing import List, Dict, Any, Optional, Set
from difflib import SequenceMatcher

from loguru import logger


class Preprocessor:
    """Preprocessor for cleaning and deduplicating articles."""
    
    def __init__(self, similarity_threshold: float = 0.85):
        """
        Initialize preprocessor.
        
        Args:
            similarity_threshold: Minimum similarity for duplicate detection (0-1)
        """
        self.similarity_threshold = similarity_threshold
    
    def clean_text(self, text: Optional[str]) -> Optional[str]:
        """
        Clean and normalize text.
        
        Args:
            text: Input text
            
        Returns:
            Cleaned text or None
        """
        if not text:
            return None
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove control characters
        text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
        
        # Normalize unicode
        text = text.encode('utf-8', 'ignore').decode('utf-8')
        
        return text if text else None
    
    def clean_title(self, title: str) -> str:
        """
        Clean article title.
        
        Args:
            title: Raw title
            
        Returns:
            Cleaned title
        """
        if not title:
            return ""
        
        # Remove common prefixes
        prefixes = ["[D]", "[R]", "[P]", "[N]", "RE:", "Re:", "FW:", "Fw:"]
        for prefix in prefixes:
            if title.startswith(prefix):
                title = title[len(prefix):].strip()
        
        # Clean whitespace
        title = re.sub(r'\s+', ' ', title).strip()
        
        # Remove trailing punctuation repetition
        title = re.sub(r'[.!?]+$', lambda m: m.group(0)[0], title)
        
        return title
    
    def process_article(self, article: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single article.
        
        Args:
            article: Raw article dictionary
            
        Returns:
            Processed article dictionary
        """
        processed = article.copy()
        
        # Clean title
        processed["title"] = self.clean_title(article.get("title", ""))
        
        # Clean abstract and full text
        processed["abstract"] = self.clean_text(article.get("abstract"))
        processed["full_text"] = self.clean_text(article.get("full_text"))
        
        # Ensure URL is present
        if not processed.get("url"):
            logger.warning(f"Article missing URL: {processed.get('title', 'Unknown')}")
        
        return processed
    
    def process_batch(self, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Process a batch of articles.
        
        Args:
            articles: List of raw articles
            
        Returns:
            List of processed articles
        """
        processed = []
        for article in articles:
            try:
                p = self.process_article(article)
                if p.get("title"):  # Only keep articles with valid titles
                    processed.append(p)
            except Exception as e:
                logger.warning(f"Failed to process article: {e}")
        
        return processed
    
    def _normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Lowercase
        normalized = title.lower()
        
        # Remove punctuation
        normalized = re.sub(r'[^\w\s]', '', normalized)
        
        # Remove extra spaces
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        return normalized
    
    def _title_similarity(self, title1: str, title2: str) -> float:
        """
        Calculate similarity between two titles.
        
        Args:
            title1: First title
            title2: Second title
            
        Returns:
            Similarity score (0-1)
        """
        norm1 = self._normalize_title(title1)
        norm2 = self._normalize_title(title2)
        
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def deduplicate(
        self,
        articles: List[Dict[str, Any]],
        key: str = "title",
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate articles based on title similarity.
        
        Args:
            articles: List of articles
            key: Field to use for deduplication
            
        Returns:
            List of unique articles
        """
        if not articles:
            return []
        
        unique = []
        seen_titles: List[str] = []
        
        for article in articles:
            title = article.get(key, "")
            if not title:
                continue
            
            # Check against already seen titles
            is_duplicate = False
            for seen_title in seen_titles:
                if self._title_similarity(title, seen_title) >= self.similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(article)
                seen_titles.append(title)
        
        if len(articles) != len(unique):
            logger.info(f"Removed {len(articles) - len(unique)} duplicates")
        
        return unique
    
    def deduplicate_fast(
        self,
        articles: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Fast deduplication using exact article_id matching.
        
        Args:
            articles: List of articles
            
        Returns:
            List of unique articles (by article_id)
        """
        seen_ids: Set[str] = set()
        unique = []
        
        for article in articles:
            article_id = article.get("article_id")
            if article_id and article_id not in seen_ids:
                unique.append(article)
                seen_ids.add(article_id)
        
        return unique
    
    def filter_by_length(
        self,
        articles: List[Dict[str, Any]],
        min_title_length: int = 10,
        min_content_length: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Filter out articles with very short titles or content.
        
        Args:
            articles: List of articles
            min_title_length: Minimum title length
            min_content_length: Minimum content (abstract/full_text) length
            
        Returns:
            Filtered list of articles
        """
        filtered = []
        
        for article in articles:
            title = article.get("title", "")
            content = article.get("abstract") or article.get("full_text") or ""
            
            if len(title) >= min_title_length and len(content) >= min_content_length:
                filtered.append(article)
        
        return filtered
