"""Pydantic models for API requests and responses."""

from typing import Optional, List
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class LabelType(str, Enum):
    """Valid label types for classification."""
    GARBAGE = "garbage"
    IMPORTANT = "important"
    WORTH_LEARNING = "worth_learning"


class FeedbackType(str, Enum):
    """Types of feedback."""
    CLASSIFICATION = "classification"
    SUMMARY = "summary"


# Request Models

class ClassificationFeedback(BaseModel):
    """Feedback for classification predictions."""
    article_id: str = Field(..., description="ID of the article")
    corrected_label: LabelType = Field(..., description="The correct label")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    comment: Optional[str] = Field(None, description="Optional feedback comment")


class SummaryFeedback(BaseModel):
    """Feedback for generated summaries."""
    article_id: str = Field(..., description="ID of the article")
    is_good: bool = Field(..., description="Whether the summary was helpful")
    user_id: Optional[str] = Field(None, description="Optional user identifier")
    comment: Optional[str] = Field(None, description="Optional feedback comment")


class ClassificationRequest(BaseModel):
    """Request for classifying an article."""
    title: str = Field(..., description="Article title")
    abstract: str = Field(..., description="Article abstract or content")
    source: Optional[str] = Field(None, description="Source of the article")


class SummarizationRequest(BaseModel):
    """Request for summarizing text."""
    text: str = Field(..., description="Text to summarize")
    style: str = Field("brief", description="Summary style: 'brief' or 'detailed'")


class BatchClassificationRequest(BaseModel):
    """Request for batch classification."""
    articles: List[ClassificationRequest] = Field(..., description="List of articles to classify")


# Response Models

class ClassificationResult(BaseModel):
    """Result of classification."""
    label: LabelType
    confidence: float
    probabilities: dict


class SummarizationResult(BaseModel):
    """Result of summarization."""
    summary: str
    style: str
    input_length: int
    output_length: int


class ArticleResponse(BaseModel):
    """Full article response with classification and summary."""
    id: str
    title: str
    abstract: Optional[str]
    source: str
    url: Optional[str]
    classification: ClassificationResult
    summary: Optional[str]
    created_at: datetime


class FeedbackResponse(BaseModel):
    """Response after submitting feedback."""
    success: bool
    message: str
    feedback_id: Optional[int] = None


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    classifier_status: str
    summarizer_status: str
    database_status: str
    timestamp: datetime


class StatsResponse(BaseModel):
    """Statistics response."""
    total_articles: int
    predictions_today: int
    feedback_count: int
    classifier_version: Optional[str]
    summarizer_version: Optional[str]


class ModelInfo(BaseModel):
    """Information about a model version."""
    name: str
    version: str
    stage: str
    run_id: Optional[str]
    metrics: dict


class ModelsResponse(BaseModel):
    """Response with model information."""
    classifier: Optional[ModelInfo]
    summarizer: Optional[ModelInfo]


class PaginatedArticles(BaseModel):
    """Paginated list of articles."""
    items: List[ArticleResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
