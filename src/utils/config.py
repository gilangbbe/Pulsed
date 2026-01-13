"""Global configuration for Pulsed."""

import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from loguru import logger

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
PROCESSED_DATA_DIR = DATA_DIR / "processed"
SUMMARIES_DATA_DIR = DATA_DIR / "summaries"


class RedditConfig(BaseModel):
    """Reddit API configuration."""
    client_id: str = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret: str = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent: str = os.getenv("REDDIT_USER_AGENT", "pulsed:v1.0.0")


class EmailConfig(BaseModel):
    """Email configuration."""
    sender: str = os.getenv("EMAIL_SENDER", "")
    password: str = os.getenv("EMAIL_PASSWORD", "")
    recipient: str = os.getenv("EMAIL_RECIPIENT", "")
    smtp_server: str = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    smtp_port: int = int(os.getenv("SMTP_PORT", "587"))


class MLflowConfig(BaseModel):
    """MLflow configuration."""
    tracking_uri: str = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
    experiment_name: str = os.getenv("MLFLOW_EXPERIMENT_NAME", "pulsed")


class ModelConfig(BaseModel):
    """Model configuration."""
    classifier_model_name: str = os.getenv("CLASSIFIER_MODEL_NAME", "distilbert-base-uncased")
    summarizer_model_name: str = os.getenv("SUMMARIZER_MODEL_NAME", "sshleifer/distilbart-cnn-12-6")
    
    # Inference settings
    classifier_batch_size: int = 32
    summarizer_batch_size: int = 8
    max_input_length: int = 512
    
    # Brief summary settings (for "important")
    brief_max_length: int = 100
    brief_min_length: int = 30
    
    # Detailed summary settings (for "worth_learning")
    detailed_max_length: int = 250
    detailed_min_length: int = 100


class RetrainConfig(BaseModel):
    """Retraining thresholds configuration."""
    classifier_threshold: int = int(os.getenv("CLASSIFIER_RETRAIN_THRESHOLD", "100"))
    summarizer_threshold: int = int(os.getenv("SUMMARIZER_RETRAIN_THRESHOLD", "50"))
    classifier_improvement: float = float(os.getenv("CLASSIFIER_IMPROVEMENT_THRESHOLD", "0.02"))
    summarizer_improvement: float = float(os.getenv("SUMMARIZER_IMPROVEMENT_THRESHOLD", "0.05"))


class DatabaseConfig(BaseModel):
    """Database configuration."""
    url: str = os.getenv("DATABASE_URL", f"sqlite:///{PROJECT_ROOT}/news.db")


class APIConfig(BaseModel):
    """API configuration."""
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))


class Config(BaseModel):
    """Main configuration class."""
    reddit: RedditConfig = RedditConfig()
    email: EmailConfig = EmailConfig()
    mlflow: MLflowConfig = MLflowConfig()
    model: ModelConfig = ModelConfig()
    retrain: RetrainConfig = RetrainConfig()
    database: DatabaseConfig = DatabaseConfig()
    api: APIConfig = APIConfig()
    
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    digest_send_hour: int = int(os.getenv("DIGEST_SEND_HOUR", "8"))
    fetch_interval_hours: int = int(os.getenv("FETCH_INTERVAL_HOURS", "1"))


# Global config instance
config = Config()


def setup_logging():
    """Setup logging configuration."""
    logger.remove()
    logger.add(
        "logs/pulsed_{time:YYYY-MM-DD}.log",
        rotation="1 day",
        retention="30 days",
        level=config.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}",
    )
    logger.add(
        lambda msg: print(msg, end=""),
        level=config.log_level,
        format="{time:HH:mm:ss} | {level} | {message}",
    )


# Classification labels
LABELS = ["garbage", "important", "worth_learning"]
LABEL_TO_ID = {label: idx for idx, label in enumerate(LABELS)}
ID_TO_LABEL = {idx: label for idx, label in enumerate(LABELS)}
