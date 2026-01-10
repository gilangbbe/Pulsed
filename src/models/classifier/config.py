"""Classifier configuration."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ClassifierConfig:
    """Configuration for the classifier model."""
    
    # Model architecture
    model_name: str = "distilbert-base-uncased"
    num_labels: int = 3
    
    # Training hyperparameters
    learning_rate: float = 2e-5
    batch_size: int = 16
    num_epochs: int = 3
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    max_length: int = 512
    
    # Training settings
    seed: int = 42
    fp16: bool = True  # Use mixed precision if available
    gradient_accumulation_steps: int = 1
    
    # Evaluation
    eval_batch_size: int = 32
    eval_steps: int = 100
    save_steps: int = 500
    
    # Early stopping
    early_stopping_patience: int = 3
    early_stopping_threshold: float = 0.001
    
    # Regularization
    dropout: float = 0.1
    
    # Label smoothing
    label_smoothing: float = 0.0
    
    # Class weights for imbalanced data
    use_class_weights: bool = True
    
    # Output
    output_dir: str = "models/classifier"
    
    def to_dict(self) -> dict:
        """Convert config to dictionary."""
        return {
            "model_name": self.model_name,
            "num_labels": self.num_labels,
            "learning_rate": self.learning_rate,
            "batch_size": self.batch_size,
            "num_epochs": self.num_epochs,
            "warmup_ratio": self.warmup_ratio,
            "weight_decay": self.weight_decay,
            "max_length": self.max_length,
            "seed": self.seed,
            "fp16": self.fp16,
            "gradient_accumulation_steps": self.gradient_accumulation_steps,
            "eval_batch_size": self.eval_batch_size,
            "dropout": self.dropout,
            "label_smoothing": self.label_smoothing,
            "use_class_weights": self.use_class_weights,
        }


# Predefined configurations for different scenarios
QUICK_TRAIN_CONFIG = ClassifierConfig(
    num_epochs=1,
    batch_size=32,
    eval_steps=50,
)

FULL_TRAIN_CONFIG = ClassifierConfig(
    num_epochs=5,
    batch_size=16,
    learning_rate=1e-5,
    warmup_ratio=0.1,
    early_stopping_patience=3,
)

FINE_TUNE_CONFIG = ClassifierConfig(
    num_epochs=2,
    batch_size=8,
    learning_rate=5e-6,
    warmup_ratio=0.0,
)
