"""ArXiv data source for fetching ML/AI papers."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import arxiv
from loguru import logger


class ArxivSource:
    """Fetch papers from ArXiv."""
    
    # AI/ML related categories
    CATEGORIES = [
        "cs.AI",   # Artificial Intelligence
        "cs.LG",   # Machine Learning
        "cs.CV",   # Computer Vision
        "cs.CL",   # Computation and Language (NLP)
        "cs.NE",   # Neural and Evolutionary Computing
        "stat.ML", # Machine Learning (Statistics)
    ]
    
    def __init__(self, max_results_per_category: int = 50):
        self.max_results = max_results_per_category
        self.client = arxiv.Client()
    
    def _generate_article_id(self, entry: arxiv.Result) -> str:
        """Generate a unique article ID from ArXiv entry."""
        # Use ArXiv ID as the base
        return f"arxiv_{entry.get_short_id()}"
    
    def fetch(
        self, 
        categories: Optional[List[str]] = None,
        days_back: int = 1,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent papers from ArXiv.
        
        Args:
            categories: List of ArXiv categories to fetch (default: all ML/AI)
            days_back: Number of days to look back
            
        Returns:
            List of article dictionaries
        """
        if categories is None:
            categories = self.CATEGORIES
        
        articles = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for category in categories:
            try:
                logger.info(f"Fetching ArXiv papers from {category}")
                
                search = arxiv.Search(
                    query=f"cat:{category}",
                    max_results=self.max_results,
                    sort_by=arxiv.SortCriterion.SubmittedDate,
                    sort_order=arxiv.SortOrder.Descending,
                )
                
                for result in self.client.results(search):
                    # Check if paper is recent enough
                    if result.published.replace(tzinfo=None) < cutoff_date:
                        continue
                    
                    article = {
                        "article_id": self._generate_article_id(result),
                        "source": f"arxiv_{category}",
                        "title": result.title.replace('\n', ' ').strip(),
                        "abstract": result.summary.replace('\n', ' ').strip(),
                        "full_text": None,  # ArXiv doesn't provide full text via API
                        "url": result.pdf_url or result.entry_id,
                        "published_date": result.published,
                        "metadata": {
                            "arxiv_id": result.get_short_id(),
                            "categories": result.categories,
                            "authors": [a.name for a in result.authors],
                            "primary_category": result.primary_category,
                            "doi": result.doi,
                            "comment": result.comment,
                        }
                    }
                    articles.append(article)
                
                logger.info(f"Fetched {len([a for a in articles if category in a['source']])} papers from {category}")
                
            except Exception as e:
                logger.error(f"Error fetching from ArXiv category {category}: {e}")
                continue
        
        return articles
    
    def fetch_by_ids(self, arxiv_ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetch specific papers by ArXiv ID.
        
        Args:
            arxiv_ids: List of ArXiv IDs (e.g., "2301.00001")
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            search = arxiv.Search(id_list=arxiv_ids)
            
            for result in self.client.results(search):
                article = {
                    "article_id": self._generate_article_id(result),
                    "source": f"arxiv_{result.primary_category}",
                    "title": result.title.replace('\n', ' ').strip(),
                    "abstract": result.summary.replace('\n', ' ').strip(),
                    "full_text": None,
                    "url": result.pdf_url or result.entry_id,
                    "published_date": result.published,
                    "metadata": {
                        "arxiv_id": result.get_short_id(),
                        "categories": result.categories,
                        "authors": [a.name for a in result.authors],
                        "primary_category": result.primary_category,
                    }
                }
                articles.append(article)
                
        except Exception as e:
            logger.error(f"Error fetching ArXiv papers by ID: {e}")
        
        return articles
    
    def search(self, query: str, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Search ArXiv for papers matching a query.
        
        Args:
            query: Search query
            max_results: Maximum number of results
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )
            
            for result in self.client.results(search):
                article = {
                    "article_id": self._generate_article_id(result),
                    "source": f"arxiv_{result.primary_category}",
                    "title": result.title.replace('\n', ' ').strip(),
                    "abstract": result.summary.replace('\n', ' ').strip(),
                    "full_text": None,
                    "url": result.pdf_url or result.entry_id,
                    "published_date": result.published,
                    "metadata": {
                        "arxiv_id": result.get_short_id(),
                        "categories": result.categories,
                        "authors": [a.name for a in result.authors],
                        "primary_category": result.primary_category,
                    }
                }
                articles.append(article)
                
        except Exception as e:
            logger.error(f"Error searching ArXiv: {e}")
        
        return articles
