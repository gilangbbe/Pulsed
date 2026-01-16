"""Data sources package - TOS compliant sources only."""

from .arxiv import ArxivSource
# Reddit removed - TOS prohibits transformative use
# from .reddit import RedditSource
from .papers_with_code import PapersWithCodeSource
from .rss_feeds import RSSFeedSource
from .semantic_scholar import SemanticScholarSource

__all__ = ["ArxivSource", "PapersWithCodeSource", "RSSFeedSource", "SemanticScholarSource"]
