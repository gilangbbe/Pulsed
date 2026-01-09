"""Feedback collection endpoints."""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from loguru import logger

from .models import (
    ClassificationFeedback,
    SummaryFeedback,
    FeedbackResponse,
)
from ..utils.db import get_db

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("/classification", response_model=FeedbackResponse)
async def submit_classification_feedback(feedback: ClassificationFeedback):
    """
    Submit feedback for a classification prediction.
    
    This is used when a user indicates the model's classification was wrong
    and provides the correct label.
    """
    db = get_db()
    
    try:
        # Get the prediction for this article
        prediction = db.get_prediction_by_article_id(feedback.article_id)
        
        if not prediction:
            raise HTTPException(
                status_code=404,
                detail=f"No prediction found for article {feedback.article_id}"
            )
        
        # Store the feedback
        db.add_feedback(
            feedback_type="classification",
            article_id=feedback.article_id,
            original_value=prediction.get("label"),
            corrected_value=feedback.corrected_label.value,
            user_id=feedback.user_id,
            comment=feedback.comment,
        )
        
        logger.info(
            f"Classification feedback received for article {feedback.article_id}: "
            f"{prediction.get('label')} -> {feedback.corrected_label.value}"
        )
        
        return FeedbackResponse(
            success=True,
            message="Classification feedback recorded successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing classification feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/summary", response_model=FeedbackResponse)
async def submit_summary_feedback(feedback: SummaryFeedback):
    """
    Submit feedback for a generated summary.
    
    This indicates whether the summary was helpful or not.
    """
    db = get_db()
    
    try:
        # Store the feedback
        db.add_feedback(
            feedback_type="summary",
            article_id=feedback.article_id,
            original_value="",  # Summary content could be too long
            corrected_value="good" if feedback.is_good else "bad",
            user_id=feedback.user_id,
            comment=feedback.comment,
        )
        
        logger.info(
            f"Summary feedback received for article {feedback.article_id}: "
            f"{'good' if feedback.is_good else 'bad'}"
        )
        
        return FeedbackResponse(
            success=True,
            message="Summary feedback recorded successfully"
        )
        
    except Exception as e:
        logger.error(f"Error storing summary feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quick/{article_id}/{feedback_type}/{value}")
async def quick_feedback(
    article_id: str,
    feedback_type: str,
    value: str,
    user_id: Optional[str] = Query(None),
):
    """
    Quick feedback endpoint for email links.
    
    This simplified endpoint allows one-click feedback from email digests.
    
    - `feedback_type`: "classification" or "summary"
    - `value`: For classification, one of "garbage", "important", "worth_learning"
               For summary, "good" or "bad"
    """
    db = get_db()
    
    valid_labels = ["garbage", "important", "worth_learning"]
    valid_summary = ["good", "bad"]
    
    if feedback_type == "classification":
        if value not in valid_labels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid label. Must be one of: {valid_labels}"
            )
        
        # Get original prediction
        prediction = db.get_prediction_by_article_id(article_id)
        original = prediction.get("label") if prediction else "unknown"
        
        db.add_feedback(
            feedback_type="classification",
            article_id=article_id,
            original_value=original,
            corrected_value=value,
            user_id=user_id,
        )
        
    elif feedback_type == "summary":
        if value not in valid_summary:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid value. Must be one of: {valid_summary}"
            )
        
        db.add_feedback(
            feedback_type="summary",
            article_id=article_id,
            original_value="",
            corrected_value=value,
            user_id=user_id,
        )
    else:
        raise HTTPException(
            status_code=400,
            detail="feedback_type must be 'classification' or 'summary'"
        )
    
    # Return a simple HTML response for browser display
    return {
        "success": True,
        "message": f"Thank you for your feedback!",
        "article_id": article_id,
        "feedback_type": feedback_type,
        "value": value,
    }


@router.get("/stats")
async def get_feedback_stats():
    """Get feedback collection statistics."""
    db = get_db()
    stats = db.get_feedback_stats()
    
    return {
        "classification_feedback": stats.get("classification_feedback", 0),
        "summary_feedback": stats.get("summary_feedback", 0),
        "unused_feedback": stats.get("unused_feedback", 0),
        "total": (
            stats.get("classification_feedback", 0) + 
            stats.get("summary_feedback", 0)
        ),
    }
