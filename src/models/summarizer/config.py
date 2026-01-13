"""Summarizer configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class SummarizerConfig:
    """Configuration for the summarizer model."""
    
    # Model architecture
    model_name: str = "sshleifer/distilbart-cnn-12-6"
    
    # Generation parameters - Brief summaries (for "important")
    brief_max_length: int = 100
    brief_min_length: int = 30
    brief_num_beams: int = 4
    
    # Generation parameters - Detailed summaries (for "worth_learning")
    detailed_max_length: int = 250
    detailed_min_length: int = 100
    detailed_num_beams: int = 6
    
    # Common generation parameters
    length_penalty: float = 2.0
    early_stopping: bool = True
    no_repeat_ngram_size: int = 3
    
    # Input settings
    max_input_length: int = 1024
    
    # Training hyperparameters (for fine-tuning)
    learning_rate: float = 5e-5
    batch_size: int = 4
    num_epochs: int = 3
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    gradient_accumulation_steps: int = 4
    
    # Training settings
    seed: int = 42
    fp16: bool = True
    
    # Output
    output_dir: str = "models/summarizer"
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "model_name": self.model_name,
            "brief_max_length": self.brief_max_length,
            "brief_min_length": self.brief_min_length,
            "detailed_max_length": self.detailed_max_length,
            "detailed_min_length": self.detailed_min_length,
            "length_penalty": self.length_penalty,
            "no_repeat_ngram_size": self.no_repeat_ngram_size,
            "max_input_length": self.max_input_length,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "num_epochs": self.num_epochs,
        }


# Alternative model configurations
BART_CONFIG = SummarizerConfig(
    model_name="facebook/bart-large-cnn",
)

PEGASUS_CONFIG = SummarizerConfig(
    model_name="google/pegasus-xsum",
    brief_max_length=80,
    brief_min_length=20,
    detailed_max_length=200,
    detailed_min_length=80,
)

# Smaller model for faster inference
DISTILBART_CONFIG = SummarizerConfig(
    model_name="sshleifer/distilbart-cnn-12-6",
    brief_num_beams=3,
    detailed_num_beams=4,
)

# T5 alternative
T5_CONFIG = SummarizerConfig(
    model_name="t5-base",
    brief_max_length=100,
    detailed_max_length=200,
)
