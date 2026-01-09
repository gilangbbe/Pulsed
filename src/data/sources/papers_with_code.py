"""Papers With Code data source."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from loguru import logger


class PapersWithCodeSource:
    """Fetch trending papers from Papers With Code."""
    
    BASE_URL = "https://paperswithcode.com/api/v1"
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Pulsed/1.0 (ML News Aggregator)",
            "Accept": "application/json",
        })
    
    def _generate_article_id(self, paper: Dict) -> str:
        """Generate a unique article ID."""
        paper_id = paper.get("id") or paper.get("paper_id", "")
        return f"pwc_{paper_id}"
    
    def fetch_trending(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Fetch trending papers from Papers With Code.
        
        Args:
            limit: Maximum number of papers to fetch
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            # Papers With Code doesn't have a direct "trending" endpoint
            # We'll use the papers endpoint sorted by recent
            url = f"{self.BASE_URL}/papers/"
            params = {
                "items_per_page": min(limit, 50),
                "page": 1,
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = data.get("results", [])
            
            for paper in papers:
                abstract = paper.get("abstract", "")
                
                article = {
                    "article_id": self._generate_article_id(paper),
                    "source": "papers_with_code",
                    "title": paper.get("title", "").strip(),
                    "abstract": abstract[:1000] if abstract else None,
                    "full_text": abstract,
                    "url": paper.get("url_abs") or paper.get("url_pdf") or f"https://paperswithcode.com/paper/{paper.get('id', '')}",
                    "published_date": self._parse_date(paper.get("published")),
                    "metadata": {
                        "pwc_id": paper.get("id"),
                        "arxiv_id": paper.get("arxiv_id"),
                        "authors": paper.get("authors", []),
                        "repository": paper.get("repository"),
                        "conference": paper.get("conference"),
                        "tasks": paper.get("tasks", []),
                    }
                }
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} papers from Papers With Code")
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching from Papers With Code: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching from Papers With Code: {e}")
        
        return articles
    
    def fetch_by_task(
        self, 
        task: str, 
        limit: int = 25
    ) -> List[Dict[str, Any]]:
        """
        Fetch papers for a specific ML task.
        
        Args:
            task: Task name (e.g., "image-classification", "question-answering")
            limit: Maximum number of papers
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            url = f"{self.BASE_URL}/papers/"
            params = {
                "task": task,
                "items_per_page": min(limit, 50),
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = data.get("results", [])
            
            for paper in papers:
                abstract = paper.get("abstract", "")
                
                article = {
                    "article_id": self._generate_article_id(paper),
                    "source": f"pwc_{task}",
                    "title": paper.get("title", "").strip(),
                    "abstract": abstract[:1000] if abstract else None,
                    "full_text": abstract,
                    "url": paper.get("url_abs") or f"https://paperswithcode.com/paper/{paper.get('id', '')}",
                    "published_date": self._parse_date(paper.get("published")),
                    "metadata": {
                        "pwc_id": paper.get("id"),
                        "task": task,
                        "arxiv_id": paper.get("arxiv_id"),
                        "authors": paper.get("authors", []),
                    }
                }
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} papers for task: {task}")
            
        except Exception as e:
            logger.error(f"Error fetching papers for task {task}: {e}")
        
        return articles
    
    def fetch_methods(self, limit: int = 25) -> List[Dict[str, Any]]:
        """
        Fetch recently introduced methods.
        
        Args:
            limit: Maximum number of methods
            
        Returns:
            List of article dictionaries (representing methods)
        """
        articles = []
        
        try:
            url = f"{self.BASE_URL}/methods/"
            params = {
                "items_per_page": min(limit, 50),
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            methods = data.get("results", [])
            
            for method in methods:
                description = method.get("description", "")
                
                article = {
                    "article_id": f"pwc_method_{method.get('id', '')}",
                    "source": "pwc_methods",
                    "title": method.get("name", "").strip(),
                    "abstract": description[:500] if description else None,
                    "full_text": description,
                    "url": f"https://paperswithcode.com/method/{method.get('id', '')}",
                    "published_date": self._parse_date(method.get("introduced_date")),
                    "metadata": {
                        "method_id": method.get("id"),
                        "full_name": method.get("full_name"),
                        "paper_id": method.get("paper"),
                        "categories": method.get("categories", []),
                    }
                }
                articles.append(article)
            
            logger.info(f"Fetched {len(articles)} methods from Papers With Code")
            
        except Exception as e:
            logger.error(f"Error fetching methods: {e}")
        
        return articles
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        try:
            # Try different formats
            for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%SZ"]:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
        
        return None
    
    def search(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Search for papers.
        
        Args:
            query: Search query
            limit: Maximum results
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            url = f"{self.BASE_URL}/papers/"
            params = {
                "q": query,
                "items_per_page": min(limit, 50),
            }
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            papers = data.get("results", [])
            
            for paper in papers:
                article = {
                    "article_id": self._generate_article_id(paper),
                    "source": "pwc_search",
                    "title": paper.get("title", "").strip(),
                    "abstract": paper.get("abstract", "")[:1000],
                    "full_text": paper.get("abstract"),
                    "url": paper.get("url_abs") or f"https://paperswithcode.com/paper/{paper.get('id', '')}",
                    "published_date": self._parse_date(paper.get("published")),
                    "metadata": {
                        "pwc_id": paper.get("id"),
                        "search_query": query,
                    }
                }
                articles.append(article)
            
            logger.info(f"Found {len(articles)} papers for query: {query}")
            
        except Exception as e:
            logger.error(f"Error searching Papers With Code: {e}")
        
        return articles
