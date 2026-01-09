"""Summary utilities for evaluation and post-processing."""

import re
from typing import Dict, List, Optional, Tuple

from rouge_score import rouge_scorer
from loguru import logger


class RougeEvaluator:
    """ROUGE score evaluator for summaries."""
    
    def __init__(self):
        self.scorer = rouge_scorer.RougeScorer(
            ['rouge1', 'rouge2', 'rougeL'], 
            use_stemmer=True
        )
    
    def score(self, reference: str, generated: str) -> Dict[str, float]:
        """
        Calculate ROUGE scores between reference and generated text.
        
        Args:
            reference: Reference/source text
            generated: Generated summary
            
        Returns:
            Dictionary with rouge1, rouge2, and rougeL F1 scores
        """
        scores = self.scorer.score(reference, generated)
        return {
            "rouge1": scores['rouge1'].fmeasure,
            "rouge2": scores['rouge2'].fmeasure,
            "rougeL": scores['rougeL'].fmeasure,
        }
    
    def batch_score(
        self, 
        references: List[str], 
        generated: List[str]
    ) -> Dict[str, float]:
        """
        Calculate average ROUGE scores for a batch.
        
        Args:
            references: List of reference texts
            generated: List of generated summaries
            
        Returns:
            Dictionary with average rouge1, rouge2, and rougeL scores
        """
        if len(references) != len(generated):
            raise ValueError("References and generated lists must have same length")
        
        if not references:
            return {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
        
        total_scores = {"rouge1": 0.0, "rouge2": 0.0, "rougeL": 0.0}
        
        for ref, gen in zip(references, generated):
            scores = self.score(ref, gen)
            for key in total_scores:
                total_scores[key] += scores[key]
        
        n = len(references)
        return {key: value / n for key, value in total_scores.items()}


def estimate_read_time(text: str, wpm: int = 200) -> int:
    """
    Estimate reading time in minutes.
    
    Args:
        text: The text to estimate reading time for
        wpm: Words per minute (default 200 for technical content)
        
    Returns:
        Estimated reading time in minutes (minimum 1)
    """
    if not text:
        return 1
    
    words = len(text.split())
    minutes = max(1, round(words / wpm))
    return minutes


def clean_summary(text: str) -> str:
    """
    Clean and post-process a generated summary.
    
    Args:
        text: Raw summary text
        
    Returns:
        Cleaned summary text
    """
    if not text:
        return ""
    
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    # Remove incomplete sentences at the end
    if text and not text[-1] in '.!?':
        # Try to find the last complete sentence
        last_period = text.rfind('.')
        last_exclaim = text.rfind('!')
        last_question = text.rfind('?')
        
        last_sentence_end = max(last_period, last_exclaim, last_question)
        if last_sentence_end > len(text) * 0.5:  # Only truncate if we keep >50%
            text = text[:last_sentence_end + 1]
    
    return text


def extract_key_takeaways(
    text: str, 
    max_takeaways: int = 5
) -> List[str]:
    """
    Extract key takeaways from text.
    
    This is a simple heuristic-based extraction. For production,
    consider using an LLM or more sophisticated NLP.
    
    Args:
        text: Source text to extract from
        max_takeaways: Maximum number of takeaways
        
    Returns:
        List of key takeaway strings
    """
    if not text:
        return []
    
    takeaways = []
    
    # Look for sentences with key indicators
    key_phrases = [
        r'we propose',
        r'we introduce',
        r'we present',
        r'our method',
        r'our approach',
        r'key contribution',
        r'main contribution',
        r'achieve[sd]?\s+(?:state-of-the-art|sota)',
        r'outperform[s]?',
        r'improve[sd]?\s+(?:by|over)',
        r'significant(?:ly)?\s+(?:better|improve)',
        r'first to',
        r'novel',
        r'new\s+(?:method|approach|technique|framework)',
    ]
    
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20:
            continue
        
        for phrase in key_phrases:
            if re.search(phrase, sentence, re.IGNORECASE):
                # Clean up the sentence
                cleaned = sentence.replace('\n', ' ').strip()
                if cleaned and cleaned not in takeaways:
                    takeaways.append(cleaned)
                    break
        
        if len(takeaways) >= max_takeaways:
            break
    
    return takeaways


def combine_title_abstract(
    title: str, 
    abstract: Optional[str] = None,
    full_text: Optional[str] = None,
    max_length: int = 512,
) -> str:
    """
    Combine title and abstract/full_text for model input.
    
    Args:
        title: Article title
        abstract: Article abstract
        full_text: Full article text
        max_length: Maximum number of words
        
    Returns:
        Combined text suitable for model input
    """
    parts = [title]
    
    if abstract:
        parts.append(abstract)
    elif full_text:
        # Use first part of full text if no abstract
        words = full_text.split()[:max_length - len(title.split())]
        parts.append(' '.join(words))
    
    combined = ' '.join(parts)
    
    # Truncate if needed
    words = combined.split()
    if len(words) > max_length:
        combined = ' '.join(words[:max_length])
    
    return combined


def format_summary_for_display(
    summary: str,
    key_takeaways: Optional[List[str]] = None,
    include_bullets: bool = True,
) -> str:
    """
    Format summary for display in digest.
    
    Args:
        summary: The summary text
        key_takeaways: Optional list of key points
        include_bullets: Whether to format takeaways as bullets
        
    Returns:
        Formatted summary string
    """
    result = summary.strip()
    
    if key_takeaways:
        result += "\n\nKey Takeaways:"
        for i, takeaway in enumerate(key_takeaways, 1):
            if include_bullets:
                result += f"\n• {takeaway}"
            else:
                result += f"\n{i}. {takeaway}"
    
    return result
