"""Main FastAPI application."""

from typing import Optional, List
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from .models import (
    ClassificationRequest,
    ClassificationResult,
    SummarizationRequest,
    SummarizationResult,
    BatchClassificationRequest,
    ArticleResponse,
    HealthResponse,
    StatsResponse,
    ModelsResponse,
    ModelInfo,
    PaginatedArticles,
)
from .feedback import router as feedback_router
from ..utils.db import get_db
from ..utils.config import config
from ..utils.mlflow_utils import (
    MLflowManager, 
    CLASSIFIER_MODEL_NAME, 
    SUMMARIZER_MODEL_NAME
)


# Global model instances (loaded on startup)
classifier = None
summarizer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    global classifier, summarizer
    
    logger.info("Starting Pulsed API...")
    
    # Initialize database
    db = get_db()
    db.init_db()
    logger.info("Database initialized")
    
    # Load models
    try:
        from ..models.classifier.inference import ClassifierInference
        from ..models.summarizer.inference import SummarizerInference
        
        classifier = ClassifierInference()
        summarizer = SummarizerInference()
        logger.info("Models loaded successfully")
    except Exception as e:
        logger.warning(f"Could not load models: {e}")
        logger.info("API will run in limited mode without model inference")
    
    yield
    
    # Cleanup
    logger.info("Shutting down Pulsed API...")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    
    app = FastAPI(
        title="Pulsed API",
        description="AI/ML News Filter API - Classify and summarize AI/ML articles",
        version="0.1.0",
        lifespan=lifespan,
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include feedback routes
    app.include_router(feedback_router)
    
    @app.get("/", tags=["root"])
    async def root():
        """Root endpoint."""
        return {
            "name": "Pulsed API",
            "description": "AI/ML News Filter",
            "docs": "/docs",
        }
    
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health_check():
        """Health check endpoint."""
        db = get_db()
        
        return HealthResponse(
            status="healthy",
            version="0.1.0",
            classifier_status="loaded" if classifier else "not loaded",
            summarizer_status="loaded" if summarizer else "not loaded",
            database_status="connected" if db else "disconnected",
            timestamp=datetime.utcnow(),
        )
    
    @app.get("/stats", response_model=StatsResponse, tags=["stats"])
    async def get_stats():
        """Get system statistics."""
        db = get_db()
        
        # Get counts from database
        feedback_stats = db.get_feedback_stats()
        
        return StatsResponse(
            total_articles=0,  # Would query from db
            predictions_today=0,  # Would query from db
            feedback_count=feedback_stats.get("classification_feedback", 0),
            classifier_version=None,
            summarizer_version=None,
        )
    
    @app.get("/models", response_model=ModelsResponse, tags=["models"])
    async def get_models():
        """Get information about loaded models."""
        mlflow_manager = MLflowManager()
        
        classifier_info = None
        summarizer_info = None
        
        try:
            clf_version = mlflow_manager.get_production_version(CLASSIFIER_MODEL_NAME)
            if clf_version:
                classifier_info = ModelInfo(
                    name=CLASSIFIER_MODEL_NAME,
                    version=clf_version["version"],
                    stage="Production",
                    run_id=clf_version.get("run_id"),
                    metrics={},
                )
        except Exception as e:
            logger.warning(f"Could not get classifier info: {e}")
        
        try:
            sum_version = mlflow_manager.get_production_version(SUMMARIZER_MODEL_NAME)
            if sum_version:
                summarizer_info = ModelInfo(
                    name=SUMMARIZER_MODEL_NAME,
                    version=sum_version["version"],
                    stage="Production",
                    run_id=sum_version.get("run_id"),
                    metrics={},
                )
        except Exception as e:
            logger.warning(f"Could not get summarizer info: {e}")
        
        return ModelsResponse(
            classifier=classifier_info,
            summarizer=summarizer_info,
        )
    
    @app.post("/classify", response_model=ClassificationResult, tags=["inference"])
    async def classify_article(request: ClassificationRequest):
        """Classify a single article."""
        if not classifier:
            raise HTTPException(
                status_code=503,
                detail="Classifier not loaded"
            )
        
        try:
            result = classifier.predict_single(
                title=request.title,
                abstract=request.abstract,
            )
            
            return ClassificationResult(
                label=result["label"],
                confidence=result["confidence"],
                probabilities=result["probabilities"],
            )
        except Exception as e:
            logger.error(f"Classification error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/classify/batch", response_model=List[ClassificationResult], tags=["inference"])
    async def classify_batch(request: BatchClassificationRequest):
        """Classify multiple articles."""
        if not classifier:
            raise HTTPException(
                status_code=503,
                detail="Classifier not loaded"
            )
        
        try:
            articles = [
                {"title": a.title, "abstract": a.abstract}
                for a in request.articles
            ]
            results = classifier.predict_batch(articles)
            
            return [
                ClassificationResult(
                    label=r["label"],
                    confidence=r["confidence"],
                    probabilities=r["probabilities"],
                )
                for r in results
            ]
        except Exception as e:
            logger.error(f"Batch classification error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/summarize", response_model=SummarizationResult, tags=["inference"])
    async def summarize_text(request: SummarizationRequest):
        """Summarize text."""
        if not summarizer:
            raise HTTPException(
                status_code=503,
                detail="Summarizer not loaded"
            )
        
        try:
            summary = summarizer.summarize_single(
                request.text,
                style=request.style,
            )
            
            return SummarizationResult(
                summary=summary,
                style=request.style,
                input_length=len(request.text),
                output_length=len(summary),
            )
        except Exception as e:
            logger.error(f"Summarization error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/articles", response_model=PaginatedArticles, tags=["articles"])
    async def list_articles(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        label: Optional[str] = Query(None),
    ):
        """List articles with pagination."""
        db = get_db()
        
        # This would need proper implementation in DatabaseManager
        # For now, return empty response
        return PaginatedArticles(
            items=[],
            total=0,
            page=page,
            page_size=page_size,
            total_pages=0,
        )
    
    @app.get("/articles/{article_id}", response_model=ArticleResponse, tags=["articles"])
    async def get_article(article_id: str):
        """Get a specific article by ID."""
        db = get_db()
        
        article = db.get_article_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=404,
                detail=f"Article {article_id} not found"
            )
        
        prediction = db.get_prediction_by_article_id(article_id)
        
        return ArticleResponse(
            id=article["id"],
            title=article["title"],
            abstract=article.get("abstract"),
            source=article["source"],
            url=article.get("url"),
            classification=ClassificationResult(
                label=prediction.get("label", "unknown") if prediction else "unknown",
                confidence=prediction.get("confidence", 0.0) if prediction else 0.0,
                probabilities={},
            ),
            summary=None,  # Would fetch from summaries table
            created_at=article.get("fetched_at", datetime.utcnow()),
        )
    
    return app


# Create the app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.api.main:app",
        host=config.api.host,
        port=config.api.port,
        reload=True,
    )
