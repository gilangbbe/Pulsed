"""Heuristic labeling for initial training data."""

import re
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum

from loguru import logger


class Label(Enum):
    """Classification labels."""
    GARBAGE = "garbage"
    IMPORTANT = "important"
    WORTH_LEARNING = "worth_learning"


class Labeler:
    """
    Heuristic-based labeler for bootstrapping training data.
    
    Uses rule-based heuristics to provide initial labels that can be
    refined through active learning and user feedback.
    """
    
    # Patterns indicating garbage content
    GARBAGE_PATTERNS = [
        r'\b(hiring|job|career|salary|interview)\b',
        r'\b(buy|sell|discount|offer|promo|coupon)\b',
        r'\b(crypto|bitcoin|nft|blockchain)\b',
        r'\b(stocks?|trading|invest(ment|or|ing)?)\b',
        r'^\[hiring\]',
        r'\b(meme|funny|lol|lmao)\b',
        r'\b(vs\.?|versus|battle|fight)\b.*\b(who|which)\s+(wins?|better)',
        r'click(bait)?|shocking|unbelievable|mind.?blow',
        r'\b\d+\s*(ways?|tips?|tricks?|hacks?)\s+to\b',
        r'you\s+won\'?t\s+believe',
    ]
    
    # Patterns indicating important news (but not deep learning)
    IMPORTANT_PATTERNS = [
        r'\b(announce[sd]?|launch(ed|es)?|release[sd]?|unveil(ed)?)\b',
        r'\b(funding|raise[sd]?|million|billion|acquisition|acquire[sd]?)\b',
        r'\b(partnership|collaborate|collaboration|partner)\b',
        r'\b(open.?source[sd]?|available|access)\b',
        r'\b(update[sd]?|version|v\d+|upgrade[sd]?)\b',
        r'\b(beta|alpha|preview|early.?access)\b',
        r'\b(api|sdk|library|framework|tool|platform)\b.*\b(release|launch|available)\b',
        r'\b(company|startup|org(anization)?|team|lab)\b.*\b(announce|launch|release)\b',
    ]
    
    # Patterns indicating worth learning (deep technical content)
    WORTH_LEARNING_PATTERNS = [
        # Academic/research patterns
        r'\b(paper|research|study|experiment|evaluation)\b',
        r'\b(propose[sd]?|introduce[sd]?|present(ed)?|novel|new)\s+(method|approach|technique|model|architecture|framework|algorithm)\b',
        r'\b(state.?of.?the.?art|sota|benchmark|outperform|surpass)\b',
        r'\b(ablation|analysis|empirical|theoretical)\b',
        
        # Technical depth patterns
        r'\b(transformer|attention|encoder|decoder|embedding)\b',
        r'\b(gradient|backprop|optimization|loss|objective)\b',
        r'\b(architecture|layer|module|block|component)\b',
        r'\b(training|fine.?tun(e|ing)|pretrain|pretraining)\b',
        r'\b(dataset|corpus|benchmark|evaluation)\b',
        r'\b(accuracy|precision|recall|f1|perplexity|bleu|rouge)\b',
        
        # Tutorial/learning patterns
        r'\b(tutorial|guide|introduction|explain(ed|ing)?|understand(ing)?|deep.?dive|walkthrough)\b',
        r'\b(implement(ation|ed|ing)?|code|coding|build(ing)?)\b.*\b(from.?scratch|step.?by.?step)\b',
        r'how\s+(to|does?|do)\s+\w+\s+(work|implement|build|train)',
    ]
    
    # Source-based heuristics (some sources are more likely to have quality content)
    HIGH_QUALITY_SOURCES = [
        "arxiv",
        "papers_with_code",
        "distill",
        "deepmind",
        "openai",
        "anthropic",
        "google_ai",
    ]
    
    MEDIUM_QUALITY_SOURCES = [
        "huggingface",
        "pytorch",
        "tensorflow",
        "meta_ai",
    ]
    
    def __init__(self):
        # Compile regex patterns for efficiency
        self.garbage_re = [re.compile(p, re.IGNORECASE) for p in self.GARBAGE_PATTERNS]
        self.important_re = [re.compile(p, re.IGNORECASE) for p in self.IMPORTANT_PATTERNS]
        self.worth_learning_re = [re.compile(p, re.IGNORECASE) for p in self.WORTH_LEARNING_PATTERNS]
    
    def _count_pattern_matches(
        self,
        text: str,
        patterns: List[re.Pattern],
    ) -> int:
        """Count how many patterns match in the text."""
        return sum(1 for p in patterns if p.search(text))
    
    def _get_source_quality(self, source: str) -> str:
        """Get quality tier based on source."""
        source_lower = source.lower()
        
        for high_source in self.HIGH_QUALITY_SOURCES:
            if high_source in source_lower:
                return "high"
        
        for medium_source in self.MEDIUM_QUALITY_SOURCES:
            if medium_source in source_lower:
                return "medium"
        
        return "low"
    
    def label_article(
        self,
        article: Dict[str, Any],
        return_confidence: bool = False,
    ) -> Tuple[str, float] if return_confidence else str:
        """
        Apply heuristic labeling to an article.
        
        Args:
            article: Article dictionary with title, abstract, source, etc.
            return_confidence: Whether to return confidence score
            
        Returns:
            Label string (and optionally confidence score)
        """
        title = article.get("title", "")
        abstract = article.get("abstract", "")
        full_text = article.get("full_text", "")
        source = article.get("source", "")
        
        # Combine text for analysis
        combined_text = f"{title} {abstract} {full_text}".strip()
        
        if not combined_text:
            result = (Label.GARBAGE.value, 0.5) if return_confidence else Label.GARBAGE.value
            return result
        
        # Count pattern matches
        garbage_score = self._count_pattern_matches(combined_text, self.garbage_re)
        important_score = self._count_pattern_matches(combined_text, self.important_re)
        worth_learning_score = self._count_pattern_matches(combined_text, self.worth_learning_re)
        
        # Source quality boost
        source_quality = self._get_source_quality(source)
        if source_quality == "high":
            worth_learning_score += 2
        elif source_quality == "medium":
            important_score += 1
        
        # ArXiv papers are more likely to be worth learning
        if "arxiv" in source.lower():
            worth_learning_score += 3
        
        # Reddit posts from specific subreddits
        if "MachineLearning" in source:
            worth_learning_score += 1
        elif "LocalLLaMA" in source:
            important_score += 1
        
        # Determine label based on scores
        scores = {
            Label.GARBAGE.value: garbage_score,
            Label.IMPORTANT.value: important_score,
            Label.WORTH_LEARNING.value: worth_learning_score,
        }
        
        max_score = max(scores.values())
        
        if max_score == 0:
            # Default to important if no patterns match
            label = Label.IMPORTANT.value
            confidence = 0.3
        else:
            # Choose label with highest score
            label = max(scores, key=scores.get)
            
            # Calculate confidence based on score difference
            sorted_scores = sorted(scores.values(), reverse=True)
            if len(sorted_scores) > 1 and sorted_scores[0] > 0:
                confidence = min(0.9, 0.5 + (sorted_scores[0] - sorted_scores[1]) * 0.1)
            else:
                confidence = 0.5
        
        if return_confidence:
            return label, confidence
        return label
    
    def label_batch(
        self,
        articles: List[Dict[str, Any]],
        return_confidence: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Label a batch of articles.
        
        Args:
            articles: List of article dictionaries
            return_confidence: Whether to include confidence scores
            
        Returns:
            List of articles with 'heuristic_label' (and optionally 'label_confidence') added
        """
        labeled = []
        
        for article in articles:
            article_copy = article.copy()
            
            if return_confidence:
                label, confidence = self.label_article(article, return_confidence=True)
                article_copy["heuristic_label"] = label
                article_copy["label_confidence"] = confidence
            else:
                article_copy["heuristic_label"] = self.label_article(article)
            
            labeled.append(article_copy)
        
        return labeled
    
    def get_label_distribution(
        self,
        articles: List[Dict[str, Any]],
    ) -> Dict[str, int]:
        """
        Get distribution of heuristic labels.
        
        Args:
            articles: List of labeled articles
            
        Returns:
            Dictionary with label counts
        """
        distribution = {
            Label.GARBAGE.value: 0,
            Label.IMPORTANT.value: 0,
            Label.WORTH_LEARNING.value: 0,
        }
        
        labeled = self.label_batch(articles)
        
        for article in labeled:
            label = article.get("heuristic_label")
            if label in distribution:
                distribution[label] += 1
        
        return distribution
    
    def suggest_for_review(
        self,
        articles: List[Dict[str, Any]],
        min_confidence: float = 0.3,
        max_confidence: float = 0.6,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Suggest articles for manual review (low confidence labels).
        
        Args:
            articles: List of articles
            min_confidence: Minimum confidence threshold
            max_confidence: Maximum confidence threshold
            limit: Maximum number of suggestions
            
        Returns:
            List of articles needing review, sorted by confidence
        """
        labeled = self.label_batch(articles, return_confidence=True)
        
        # Filter by confidence range
        uncertain = [
            a for a in labeled
            if min_confidence <= a.get("label_confidence", 0) <= max_confidence
        ]
        
        # Sort by confidence (lowest first - most uncertain)
        uncertain.sort(key=lambda x: x.get("label_confidence", 0))
        
        return uncertain[:limit]
