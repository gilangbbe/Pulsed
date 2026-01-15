"""Database connection and query utilities."""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from loguru import logger

from .config import config


# Database schema
SCHEMA = """
-- Raw articles before classification
CREATE TABLE IF NOT EXISTS raw_articles (
    article_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    title TEXT NOT NULL,
    abstract TEXT,
    full_text TEXT,
    url TEXT NOT NULL,
    published_date TIMESTAMP,
    fetched_date TIMESTAMP NOT NULL,
    metadata JSON,
    data_version TEXT
);

-- Classification predictions
CREATE TABLE IF NOT EXISTS predictions (
    prediction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    classifier_version TEXT NOT NULL,
    predicted_label TEXT NOT NULL,
    confidence FLOAT NOT NULL,
    prediction_time TIMESTAMP NOT NULL,
    latency_ms FLOAT,
    FOREIGN KEY (article_id) REFERENCES raw_articles(article_id)
);
CREATE INDEX IF NOT EXISTS idx_predictions_article ON predictions(article_id);
CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(prediction_time);

-- Generated summaries
CREATE TABLE IF NOT EXISTS summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    summarizer_version TEXT NOT NULL,
    summary_type TEXT NOT NULL,
    summary_text TEXT NOT NULL,
    key_takeaways TEXT,
    estimated_read_time INTEGER,
    generation_time TIMESTAMP NOT NULL,
    latency_ms FLOAT,
    rouge_1 FLOAT,
    rouge_2 FLOAT,
    rouge_l FLOAT,
    FOREIGN KEY (article_id) REFERENCES raw_articles(article_id)
);
CREATE INDEX IF NOT EXISTS idx_summaries_article ON summaries(article_id);

-- User feedback for continuous learning
CREATE TABLE IF NOT EXISTS feedback (
    feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
    article_id TEXT NOT NULL,
    predicted_label TEXT,
    correct_label TEXT,
    classifier_version TEXT,
    summary_rating TEXT,
    summary_edited_text TEXT,
    summary_issues TEXT,
    summarizer_version TEXT,
    feedback_time TIMESTAMP NOT NULL,
    used_for_training BOOLEAN DEFAULT FALSE,
    used_for_classifier_training BOOLEAN DEFAULT FALSE,
    used_for_summarizer_training BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (article_id) REFERENCES raw_articles(article_id)
);
CREATE INDEX IF NOT EXISTS idx_feedback_time ON feedback(feedback_time);
CREATE INDEX IF NOT EXISTS idx_feedback_used ON feedback(used_for_training);
CREATE INDEX IF NOT EXISTS idx_feedback_classifier_used ON feedback(used_for_classifier_training);
CREATE INDEX IF NOT EXISTS idx_feedback_summarizer_used ON feedback(used_for_summarizer_training);

-- Training run metadata
CREATE TABLE IF NOT EXISTS training_runs (
    run_id TEXT PRIMARY KEY,
    model_type TEXT NOT NULL,
    model_version TEXT NOT NULL,
    training_date TIMESTAMP NOT NULL,
    num_training_samples INTEGER,
    test_accuracy FLOAT,
    test_precision FLOAT,
    test_recall FLOAT,
    test_f1_macro FLOAT,
    avg_rouge_1 FLOAT,
    avg_rouge_2 FLOAT,
    avg_rouge_l FLOAT,
    avg_user_rating FLOAT,
    data_version TEXT,
    promoted_to_production BOOLEAN DEFAULT FALSE,
    promotion_date TIMESTAMP,
    notes TEXT
);

-- Daily aggregated metrics for monitoring
CREATE TABLE IF NOT EXISTS monitoring_metrics (
    metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    classifier_version TEXT,
    total_predictions INTEGER,
    avg_confidence FLOAT,
    garbage_pct FLOAT,
    important_pct FLOAT,
    worth_learning_pct FLOAT,
    classification_feedback_count INTEGER,
    summarizer_version TEXT,
    summaries_generated INTEGER,
    avg_summary_length_brief INTEGER,
    avg_summary_length_detailed INTEGER,
    avg_generation_latency_ms FLOAT,
    avg_rouge_score FLOAT,
    summary_feedback_count INTEGER,
    good_summary_pct FLOAT,
    data_drift_score FLOAT,
    total_articles_fetched INTEGER
);
CREATE INDEX IF NOT EXISTS idx_monitoring_date ON monitoring_metrics(date);
"""


class DatabaseManager:
    """Database manager for Pulsed."""
    
    def __init__(self, db_url: Optional[str] = None):
        self.db_url = db_url or config.database.url
        self.engine = create_engine(self.db_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
    
    def init_db(self):
        """Initialize database with schema."""
        with self.engine.connect() as conn:
            for statement in SCHEMA.split(";"):
                statement = statement.strip()
                if statement:
                    try:
                        conn.execute(text(statement))
                    except Exception as e:
                        # Ignore errors for IF NOT EXISTS statements
                        if "already exists" not in str(e).lower():
                            logger.warning(f"Schema statement warning: {e}")
            conn.commit()
        logger.info("Database initialized successfully")
    
    @contextmanager
    def get_session(self) -> Session:
        """Get a database session."""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    # Article operations
    def insert_article(
        self,
        article_id: str,
        source: str,
        title: str,
        url: str,
        abstract: Optional[str] = None,
        full_text: Optional[str] = None,
        published_date: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        data_version: Optional[str] = None,
    ) -> bool:
        """Insert a new article. Returns True if inserted, False if duplicate."""
        with self.get_session() as session:
            # Check for duplicate
            result = session.execute(
                text("SELECT 1 FROM raw_articles WHERE article_id = :id"),
                {"id": article_id}
            ).fetchone()
            
            if result:
                return False
            
            session.execute(
                text("""
                    INSERT INTO raw_articles 
                    (article_id, source, title, abstract, full_text, url, 
                     published_date, fetched_date, metadata, data_version)
                    VALUES (:article_id, :source, :title, :abstract, :full_text, :url,
                            :published_date, :fetched_date, :metadata, :data_version)
                """),
                {
                    "article_id": article_id,
                    "source": source,
                    "title": title,
                    "abstract": abstract,
                    "full_text": full_text,
                    "url": url,
                    "published_date": published_date,
                    "fetched_date": datetime.utcnow(),
                    "metadata": json.dumps(metadata) if metadata else None,
                    "data_version": data_version,
                }
            )
            return True
    
    def get_article_by_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get a single article by ID."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT article_id, source, title, abstract, full_text,
                           url, published_date, fetched_date, metadata, data_version
                    FROM raw_articles
                    WHERE article_id = :article_id
                """),
                {"article_id": article_id}
            ).fetchone()
            
            if result:
                columns = ["id", "source", "title", "abstract", "full_text",
                          "url", "published_date", "fetched_at", "metadata", "data_version"]
                return dict(zip(columns, result))
            return None
    
    def get_unclassified_articles(self, limit: int = 200) -> List[Dict[str, Any]]:
        """Get articles that haven't been classified yet."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT a.* FROM raw_articles a
                    LEFT JOIN predictions p ON a.article_id = p.article_id
                    WHERE p.prediction_id IS NULL
                    ORDER BY a.fetched_date DESC
                    LIMIT :limit
                """),
                {"limit": limit}
            ).fetchall()
            
            columns = ["article_id", "source", "title", "abstract", "full_text", 
                      "url", "published_date", "fetched_date", "metadata", "data_version"]
            return [dict(zip(columns, row)) for row in result]
    
    def get_articles_needing_summary(self) -> List[Dict[str, Any]]:
        """Get classified articles that need summarization."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT a.*, p.predicted_label FROM raw_articles a
                    INNER JOIN predictions p ON a.article_id = p.article_id
                    LEFT JOIN summaries s ON a.article_id = s.article_id
                    WHERE p.predicted_label IN ('important', 'worth_learning')
                    AND s.summary_id IS NULL
                    ORDER BY p.prediction_time DESC
                """)
            ).fetchall()
            
            columns = ["article_id", "source", "title", "abstract", "full_text",
                      "url", "published_date", "fetched_date", "metadata", 
                      "data_version", "predicted_label"]
            return [dict(zip(columns, row)) for row in result]
    
    # Prediction operations
    def insert_prediction(
        self,
        article_id: str,
        classifier_version: str,
        predicted_label: str,
        confidence: float,
        latency_ms: Optional[float] = None,
    ):
        """Insert a classification prediction."""
        with self.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO predictions 
                    (article_id, classifier_version, predicted_label, confidence, 
                     prediction_time, latency_ms)
                    VALUES (:article_id, :classifier_version, :predicted_label, 
                            :confidence, :prediction_time, :latency_ms)
                """),
                {
                    "article_id": article_id,
                    "classifier_version": classifier_version,
                    "predicted_label": predicted_label,
                    "confidence": confidence,
                    "prediction_time": datetime.utcnow(),
                    "latency_ms": latency_ms,
                }
            )
    
    def get_prediction_by_article_id(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get the prediction for a specific article."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT prediction_id, article_id, classifier_version, 
                           predicted_label, confidence, prediction_time, latency_ms
                    FROM predictions
                    WHERE article_id = :article_id
                    ORDER BY prediction_time DESC
                    LIMIT 1
                """),
                {"article_id": article_id}
            ).fetchone()
            
            if result:
                columns = ["prediction_id", "article_id", "classifier_version", 
                          "predicted_label", "confidence", "prediction_time", "latency_ms"]
                return dict(zip(columns, result))
            return None
    
    # Summary operations
    def insert_summary(
        self,
        article_id: str,
        summarizer_version: str,
        summary_type: str,
        summary_text: str,
        key_takeaways: Optional[List[str]] = None,
        estimated_read_time: Optional[int] = None,
        latency_ms: Optional[float] = None,
        rouge_scores: Optional[Dict[str, float]] = None,
    ):
        """Insert a generated summary."""
        with self.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO summaries 
                    (article_id, summarizer_version, summary_type, summary_text,
                     key_takeaways, estimated_read_time, generation_time, latency_ms,
                     rouge_1, rouge_2, rouge_l)
                    VALUES (:article_id, :summarizer_version, :summary_type, :summary_text,
                            :key_takeaways, :estimated_read_time, :generation_time, :latency_ms,
                            :rouge_1, :rouge_2, :rouge_l)
                """),
                {
                    "article_id": article_id,
                    "summarizer_version": summarizer_version,
                    "summary_type": summary_type,
                    "summary_text": summary_text,
                    "key_takeaways": json.dumps(key_takeaways) if key_takeaways else None,
                    "estimated_read_time": estimated_read_time,
                    "generation_time": datetime.utcnow(),
                    "latency_ms": latency_ms,
                    "rouge_1": rouge_scores.get("rouge1") if rouge_scores else None,
                    "rouge_2": rouge_scores.get("rouge2") if rouge_scores else None,
                    "rouge_l": rouge_scores.get("rougeL") if rouge_scores else None,
                }
            )
    
    def get_summary(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get summary for an article if it exists."""
        with self.get_session() as session:
            result = session.execute(
                text("SELECT * FROM summaries WHERE article_id = :id ORDER BY generation_time DESC LIMIT 1"),
                {"id": article_id}
            ).fetchone()
            
            if result:
                columns = ["summary_id", "article_id", "summarizer_version", "summary_type",
                          "summary_text", "key_takeaways", "estimated_read_time", 
                          "generation_time", "latency_ms", "rouge_1", "rouge_2", "rouge_l"]
                return dict(zip(columns, result))
            return None
    
    def get_summary_stats(self, days: int = 7) -> Dict[str, Any]:
        """Get summary statistics over time period."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT 
                        COUNT(*) as total,
                        AVG(CASE WHEN rouge_l IS NOT NULL THEN rouge_l ELSE 0 END) as avg_rouge_l,
                        AVG(latency_ms) as avg_latency_ms,
                        summary_type,
                        COUNT(CASE WHEN summary_type = 'brief' THEN 1 END) as brief_count,
                        COUNT(CASE WHEN summary_type = 'detailed' THEN 1 END) as detailed_count
                    FROM summaries
                    WHERE generation_time >= datetime('now', :days_ago)
                    GROUP BY summary_type
                """),
                {"days_ago": f"-{days} days"}
            ).fetchall()
            
            if not result or not result[0][0]:
                return {
                    "total_summaries": 0,
                    "avg_rouge_l": 0.0,
                    "avg_latency_ms": 0.0,
                    "by_type": {
                        "brief": {"count": 0},
                        "detailed": {"count": 0},
                    }
                }
            
            # Aggregate across types
            total = 0
            rouge_sum = 0
            latency_sum = 0
            by_type = {"brief": {"count": 0}, "detailed": {"count": 0}}
            
            for row in result:
                count = row[0] or 0
                rouge = row[1] or 0.0
                latency = row[2] or 0.0
                summary_type = row[3] or "brief"
                
                total += count
                rouge_sum += rouge * count
                latency_sum += latency * count
                
                if summary_type in by_type:
                    by_type[summary_type]["count"] = count
            
            return {
                "total_summaries": total,
                "avg_rouge_l": rouge_sum / total if total > 0 else 0.0,
                "avg_latency_ms": latency_sum / total if total > 0 else 0.0,
                "by_type": by_type,
            }
    
    # Feedback operations
    def insert_classification_feedback(
        self,
        article_id: str,
        predicted_label: str,
        correct_label: str,
        classifier_version: str,
    ):
        """Insert classification feedback."""
        with self.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO feedback 
                    (article_id, predicted_label, correct_label, classifier_version, feedback_time)
                    VALUES (:article_id, :predicted_label, :correct_label, 
                            :classifier_version, :feedback_time)
                """),
                {
                    "article_id": article_id,
                    "predicted_label": predicted_label,
                    "correct_label": correct_label,
                    "classifier_version": classifier_version,
                    "feedback_time": datetime.utcnow(),
                }
            )
    
    def insert_summary_feedback(
        self,
        article_id: str,
        rating: str,
        summarizer_version: str,
        edited_text: Optional[str] = None,
        issues: Optional[str] = None,
    ):
        """Insert summary feedback."""
        with self.get_session() as session:
            session.execute(
                text("""
                    INSERT INTO feedback 
                    (article_id, summary_rating, summary_edited_text, summary_issues,
                     summarizer_version, feedback_time)
                    VALUES (:article_id, :summary_rating, :summary_edited_text, :summary_issues,
                            :summarizer_version, :feedback_time)
                """),
                {
                    "article_id": article_id,
                    "summary_rating": rating,
                    "summary_edited_text": edited_text,
                    "summary_issues": issues,
                    "summarizer_version": summarizer_version,
                    "feedback_time": datetime.utcnow(),
                }
            )
    
    def add_feedback(
        self,
        feedback_type: str,
        article_id: str,
        original_value: Optional[str] = None,
        corrected_value: Optional[str] = None,
        user_id: Optional[str] = None,
        comment: Optional[str] = None,
    ):
        """
        Generic method to add feedback (for API compatibility).
        Routes to appropriate specific method.
        """
        if feedback_type == "classification":
            # Get the classifier version from the prediction
            prediction = self.get_prediction_by_article_id(article_id)
            classifier_version = prediction.get("classifier_version", "unknown") if prediction else "unknown"
            
            self.insert_classification_feedback(
                article_id=article_id,
                predicted_label=original_value or "unknown",
                correct_label=corrected_value or "unknown",
                classifier_version=classifier_version,
            )
        elif feedback_type == "summary":
            # Get the summarizer version from the summary
            summary = self.get_summary(article_id)
            summarizer_version = summary.get("summarizer_version", "unknown") if summary else "unknown"
            
            self.insert_summary_feedback(
                article_id=article_id,
                rating=corrected_value or "unknown",
                summarizer_version=summarizer_version,
                issues=comment,
            )
    
    def get_unused_classification_feedback(self) -> List[Dict[str, Any]]:
        """Get classification feedback not yet used for classifier training."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT f.*, a.title, a.abstract, a.full_text 
                    FROM feedback f
                    INNER JOIN raw_articles a ON f.article_id = a.article_id
                    WHERE f.correct_label IS NOT NULL 
                    AND f.used_for_classifier_training = FALSE
                """)
            ).fetchall()
            
            columns = ["feedback_id", "article_id", "predicted_label", "correct_label",
                      "classifier_version", "summary_rating", "summary_edited_text",
                      "summary_issues", "summarizer_version", "feedback_time", 
                      "used_for_training", "used_for_classifier_training", 
                      "used_for_summarizer_training", "title", "abstract", "full_text"]
            return [dict(zip(columns, row)) for row in result]
    
    def get_unused_summary_feedback(self) -> List[Dict[str, Any]]:
        """Get summary feedback not yet used for summarizer training."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT f.*, a.title, a.abstract, a.full_text 
                    FROM feedback f
                    INNER JOIN raw_articles a ON f.article_id = a.article_id
                    WHERE (f.summary_rating IS NOT NULL OR f.summary_edited_text IS NOT NULL)
                    AND f.used_for_summarizer_training = FALSE
                """)
            ).fetchall()
            
            columns = ["feedback_id", "article_id", "predicted_label", "correct_label",
                      "classifier_version", "summary_rating", "summary_edited_text",
                      "summary_issues", "summarizer_version", "feedback_time",
                      "used_for_training", "used_for_classifier_training",
                      "used_for_summarizer_training", "title", "abstract", "full_text"]
            return [dict(zip(columns, row)) for row in result]
    
    def mark_feedback_used(self, feedback_ids: List[int], model_type: str = "both"):
        """Mark feedback as used for training.
        
        Args:
            feedback_ids: List of feedback IDs to mark as used
            model_type: Which model used the feedback - 'classifier', 'summarizer', or 'both'
        """
        if not feedback_ids:
            return
            
        with self.get_session() as session:
            from sqlalchemy import bindparam
            
            # Set the appropriate columns based on model type
            if model_type == "classifier":
                stmt = text("""UPDATE feedback 
                              SET used_for_training = TRUE, used_for_classifier_training = TRUE 
                              WHERE feedback_id IN :ids""")
            elif model_type == "summarizer":
                stmt = text("""UPDATE feedback 
                              SET used_for_training = TRUE, used_for_summarizer_training = TRUE 
                              WHERE feedback_id IN :ids""")
            else:  # both
                stmt = text("""UPDATE feedback 
                              SET used_for_training = TRUE, 
                                  used_for_classifier_training = TRUE,
                                  used_for_summarizer_training = TRUE 
                              WHERE feedback_id IN :ids""")
            
            stmt = stmt.bindparams(bindparam("ids", expanding=True))
            session.execute(stmt, {"ids": feedback_ids})
    
    # Digest operations
    def get_digest_articles(self, since_hours: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Get articles for daily digest grouped by classification."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT a.*, p.predicted_label, p.confidence, s.summary_text, 
                           s.summary_type, s.key_takeaways, s.estimated_read_time
                    FROM raw_articles a
                    INNER JOIN predictions p ON a.article_id = p.article_id
                    LEFT JOIN summaries s ON a.article_id = s.article_id
                    WHERE p.predicted_label IN ('important', 'worth_learning')
                    AND a.fetched_date >= datetime('now', :hours_ago)
                    ORDER BY p.predicted_label DESC, p.confidence DESC
                """),
                {"hours_ago": f"-{since_hours} hours"}
            ).fetchall()
            
            columns = ["article_id", "source", "title", "abstract", "full_text",
                      "url", "published_date", "fetched_date", "metadata", 
                      "data_version", "predicted_label", "confidence", 
                      "summary_text", "summary_type", "key_takeaways", "estimated_read_time"]
            
            articles = {"worth_learning": [], "important": []}
            for row in result:
                article = dict(zip(columns, row))
                label = article["predicted_label"]
                if label in articles:
                    articles[label].append(article)
            
            return articles
    
    # Monitoring operations
    def get_prediction_distribution(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get prediction distribution over time."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT DATE(prediction_time) as date, predicted_label, COUNT(*) as count
                    FROM predictions
                    WHERE prediction_time >= datetime('now', :days_ago)
                    GROUP BY DATE(prediction_time), predicted_label
                    ORDER BY date
                """),
                {"days_ago": f"-{days} days"}
            ).fetchall()
            
            return [{"date": row[0], "label": row[1], "count": row[2]} for row in result]
    
    def get_feedback_stats(self) -> Dict[str, int]:
        """Get feedback statistics with model-specific tracking."""
        with self.get_session() as session:
            result = session.execute(
                text("""
                    SELECT 
                        SUM(CASE WHEN correct_label IS NOT NULL THEN 1 ELSE 0 END) as total_classification_feedback,
                        SUM(CASE WHEN correct_label IS NOT NULL AND used_for_classifier_training = FALSE THEN 1 ELSE 0 END) as unused_classification_feedback,
                        SUM(CASE WHEN (summary_rating IS NOT NULL OR summary_edited_text IS NOT NULL) THEN 1 ELSE 0 END) as total_summary_feedback,
                        SUM(CASE WHEN (summary_rating IS NOT NULL OR summary_edited_text IS NOT NULL) AND used_for_summarizer_training = FALSE THEN 1 ELSE 0 END) as unused_summary_feedback,
                        SUM(CASE WHEN used_for_training = FALSE THEN 1 ELSE 0 END) as total_unused_feedback
                    FROM feedback
                """)
            ).fetchone()
            
            return {
                "total_classification_feedback": result[0] or 0,
                "unused_classification_feedback": result[1] or 0,
                "total_summary_feedback": result[2] or 0,
                "unused_summary_feedback": result[3] or 0,
                "total_unused_feedback": result[4] or 0,
            }


# Global database instance
_db: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """Get the global database instance."""
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db
