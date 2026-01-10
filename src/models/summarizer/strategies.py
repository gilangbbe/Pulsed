"""Summarization strategies for different content types."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass

from .config import SummarizerConfig


@dataclass
class SummaryOutput:
    """Output from a summarization strategy."""
    summary_text: str
    summary_type: str
    key_takeaways: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class SummaryStrategy(ABC):
    """Abstract base class for summarization strategies."""
    
    @abstractmethod
    def get_generation_params(self) -> Dict[str, Any]:
        """Get generation parameters for this strategy."""
        pass
    
    @abstractmethod
    def post_process(self, summary: str, source_text: str) -> SummaryOutput:
        """Post-process the generated summary."""
        pass
    
    @property
    @abstractmethod
    def summary_type(self) -> str:
        """Return the type of summary this strategy produces."""
        pass


class BriefStrategy(SummaryStrategy):
    """Strategy for brief summaries (2-3 sentences for 'important' articles)."""
    
    def __init__(self, config: Optional[SummarizerConfig] = None):
        self.config = config or SummarizerConfig()
    
    @property
    def summary_type(self) -> str:
        return "brief"
    
    def get_generation_params(self) -> Dict[str, Any]:
        return {
            "max_length": self.config.brief_max_length,
            "min_length": self.config.brief_min_length,
            "num_beams": self.config.brief_num_beams,
            "length_penalty": self.config.length_penalty,
            "early_stopping": self.config.early_stopping,
            "no_repeat_ngram_size": self.config.no_repeat_ngram_size,
        }
    
    def post_process(self, summary: str, source_text: str) -> SummaryOutput:
        """Post-process brief summary."""
        # Clean up the summary
        summary = summary.strip()
        
        # Ensure it ends with proper punctuation
        if summary and summary[-1] not in ".!?":
            summary += "."
        
        return SummaryOutput(
            summary_text=summary,
            summary_type=self.summary_type,
            key_takeaways=None,  # No takeaways for brief summaries
            metadata={"strategy": "brief"},
        )


class DetailedStrategy(SummaryStrategy):
    """Strategy for detailed summaries (5-7 sentences for 'worth_learning' articles)."""
    
    def __init__(self, config: Optional[SummarizerConfig] = None):
        self.config = config or SummarizerConfig()
    
    @property
    def summary_type(self) -> str:
        return "detailed"
    
    def get_generation_params(self) -> Dict[str, Any]:
        return {
            "max_length": self.config.detailed_max_length,
            "min_length": self.config.detailed_min_length,
            "num_beams": self.config.detailed_num_beams,
            "length_penalty": self.config.length_penalty,
            "early_stopping": self.config.early_stopping,
            "no_repeat_ngram_size": self.config.no_repeat_ngram_size,
        }
    
    def _extract_key_takeaways(self, summary: str, source_text: str) -> List[str]:
        """Extract key takeaways from the summary and source."""
        takeaways = []
        
        # Split summary into sentences
        import re
        sentences = re.split(r'(?<=[.!?])\s+', summary)
        
        # Key phrases that indicate important points
        key_indicators = [
            "propose", "introduce", "present", "achieve",
            "outperform", "improve", "novel", "new",
            "key", "main", "significant", "important",
        ]
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Check if sentence contains key indicators
            sentence_lower = sentence.lower()
            if any(ind in sentence_lower for ind in key_indicators):
                # Clean and add as takeaway
                if len(sentence) > 20 and sentence not in takeaways:
                    takeaways.append(sentence)
        
        # Limit to top 3-5 takeaways
        return takeaways[:5]
    
    def post_process(self, summary: str, source_text: str) -> SummaryOutput:
        """Post-process detailed summary with key takeaways."""
        # Clean up the summary
        summary = summary.strip()
        
        # Ensure it ends with proper punctuation
        if summary and summary[-1] not in ".!?":
            summary += "."
        
        # Extract key takeaways
        takeaways = self._extract_key_takeaways(summary, source_text)
        
        return SummaryOutput(
            summary_text=summary,
            summary_type=self.summary_type,
            key_takeaways=takeaways if takeaways else None,
            metadata={"strategy": "detailed", "num_takeaways": len(takeaways)},
        )


class StrategyFactory:
    """Factory for creating summarization strategies."""
    
    _strategies = {
        "brief": BriefStrategy,
        "detailed": DetailedStrategy,
    }
    
    @classmethod
    def get_strategy(
        cls,
        strategy_type: str,
        config: Optional[SummarizerConfig] = None,
    ) -> SummaryStrategy:
        """
        Get a summarization strategy by type.
        
        Args:
            strategy_type: Type of strategy ('brief' or 'detailed')
            config: Optional configuration
            
        Returns:
            SummaryStrategy instance
        """
        if strategy_type not in cls._strategies:
            raise ValueError(f"Unknown strategy type: {strategy_type}")
        
        return cls._strategies[strategy_type](config)
    
    @classmethod
    def get_strategy_for_label(
        cls,
        label: str,
        config: Optional[SummarizerConfig] = None,
    ) -> SummaryStrategy:
        """
        Get the appropriate strategy based on classification label.
        
        Args:
            label: Classification label ('important' or 'worth_learning')
            config: Optional configuration
            
        Returns:
            SummaryStrategy instance
        """
        if label == "worth_learning":
            return cls.get_strategy("detailed", config)
        else:
            return cls.get_strategy("brief", config)
