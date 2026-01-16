"""Semantic Scholar data source for ML/AI papers."""

import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import requests
from loguru import logger


class SemanticScholarSource:
    """
    Fetch papers from Semantic Scholar API.
    
    Semantic Scholar TOS explicitly allows academic and non-commercial use.
    API: https://www.semanticscholar.org/product/api
    """
    
    BASE_URL = "https://api.semanticscholar.org/graph/v1"
    
    # ML/AI related fields of study
    FIELDS_OF_STUDY = [
        "Artificial Intelligence",
        "Machine Learning", 
        "Computer Vision",
        "Natural Language Processing",
        "Deep Learning",
    ]
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Semantic Scholar source.
        
        Args:
            api_key: Optional API key for higher rate limits (free tier: 100 req/5min)
        """
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers.update({'x-api-key': api_key})
        logger.info("Semantic Scholar source initialized")
    
    def _generate_article_id(self, paper_id: str) -> str:
        """Generate unique article ID."""
        return f"s2_{paper_id}"
    
    def fetch(
        self,
        days_back: int = 1,
        min_citations: int = 5,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Fetch recent papers from Semantic Scholar.
        
        Args:
            days_back: Number of days to look back
            min_citations: Minimum citation count filter
            limit: Maximum papers to fetch
            
        Returns:
            List of article dictionaries
        """
        articles = []
        
        try:
            # Search for recent ML papers
            for field in self.FIELDS_OF_STUDY:
                params = {
                    'query': field,
                    'fields': 'paperId,title,abstract,authors,url,publicationDate,citationCount,fieldsOfStudy,venue',
                    'limit': limit // len(self.FIELDS_OF_STUDY),
                    'publicationDateOrYear': f'{datetime.now().year}',
                }
                
                response = self.session.get(
                    f"{self.BASE_URL}/paper/search",
                    params=params,
                    timeout=30
                )
                response.raise_for_status()
                data = response.json()
                
                for paper in data.get('data', []):
                    # Filter by date
                    pub_date = paper.get('publicationDate')
                    if not pub_date:
                        continue
                        
                    try:
                        paper_date = datetime.fromisoformat(pub_date.replace('Z', '+00:00'))
                        cutoff_date = datetime.now() - timedelta(days=days_back)
                        
                        if paper_date < cutoff_date:
                            continue
                    except:
                        continue
                    
                    # Filter by citations (quality indicator)
                    citations = paper.get('citationCount', 0)
                    if citations < min_citations:
                        continue
                    
                    # Extract authors
                    authors = [
                        author.get('name', 'Unknown')
                        for author in paper.get('authors', [])
                    ]
                    
                    article = {
                        'article_id': self._generate_article_id(paper['paperId']),
                        'title': paper.get('title', 'Untitled'),
                        'abstract': paper.get('abstract', ''),
                        'url': paper.get('url') or f"https://www.semanticscholar.org/paper/{paper['paperId']}",
                        'source': 'semantic_scholar',
                        'authors': authors,
                        'published_date': pub_date,
                        'fetched_date': datetime.now().isoformat(),
                        'metadata': {
                            'paper_id': paper['paperId'],
                            'citation_count': citations,
                            'venue': paper.get('venue'),
                            'fields_of_study': paper.get('fieldsOfStudy', []),
                        }
                    }
                    
                    articles.append(article)
                    logger.debug(f"Fetched: {article['title']}")
                
                # Respect rate limits
                import time
                time.sleep(1)  # 1 request per second
        
        except Exception as e:
            logger.error(f"Error fetching from Semantic Scholar: {e}")
        
        logger.info(f"Fetched {len(articles)} papers from Semantic Scholar")
        return articles
