"""Streamlit monitoring dashboard - main entry point."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta
import sys
from pathlib import Path

# Add src to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Now we can import from src
try:
    from src.monitoring.metrics import MetricsCollector
    from src.monitoring.drift import DriftDetector
    from src.pipelines.promote import ModelPromoter
    from src.utils.db import get_db, DatabaseManager
    from src.utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME, SUMMARIZER_MODEL_NAME
    from src.utils.config import config
    IMPORTS_AVAILABLE = True
except ImportError as e:
    IMPORTS_AVAILABLE = False
    import_error = str(e)


def main():
    st.set_page_config(
        page_title="Pulsed - ML Monitor",
        page_icon="⚡",
        layout="wide",
    )
    
    st.title("⚡ Pulsed Monitoring Dashboard")
    
    if not IMPORTS_AVAILABLE:
        st.error(f"Could not import required modules: {import_error}")
        st.info("Make sure to install all requirements: pip install -r requirements.txt")
        st.stop()
    
    # Initialize database if needed
    try:
        db = get_db()
        db.init_db()
    except Exception as e:
        st.warning(f"Database initialization issue: {e}")
    
    # Initialize components
    metrics_collector = MetricsCollector()
    drift_detector = DriftDetector()
    model_promoter = ModelPromoter()
    
    # Sidebar
    st.sidebar.header("⚙️ Settings")
    days_back = st.sidebar.slider("Days to analyze", 1, 30, 7)
    
    if st.sidebar.button("🔄 Refresh Data"):
        st.rerun()
    
    # Get dashboard data
    try:
        data = metrics_collector.get_dashboard_data(days=days_back)
    except Exception as e:
        st.error(f"Error loading metrics: {e}")
        data = {
            "classification": {"total_predictions": 0, "distribution_pct": {}, "by_date": {}},
            "feedback": {"total_feedback": 0, "classification_feedback": 0, "summary_feedback": 0},
            "summarization": {"total_summaries": 0, "avg_rouge_l": 0, "avg_latency_ms": 0},
            "drift": {"alert_level": "unknown"},
        }
    
    # Top-level metrics
    st.subheader("📈 Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Predictions",
            data["classification"]["total_predictions"],
        )
    
    with col2:
        st.metric(
            "Worth Learning %",
            f"{data['classification']['distribution_pct'].get('worth_learning', 0)}%",
        )
    
    with col3:
        st.metric(
            "Total Feedback",
            data["feedback"]["total_feedback"],
        )
    
    with col4:
        drift_status = data["drift"].get("alert_level", "unknown")
        drift_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(drift_status, "⚪")
        st.metric("Drift Status", f"{drift_emoji} {drift_status.title()}")
    
    st.divider()
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Classification",
        "📝 Summarization", 
        "🔄 Models",
        "⚠️ Drift"
    ])
    
    with tab1:
        st.header("Classification Performance")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            dist = data["classification"].get("distribution", {"garbage": 0, "important": 0, "worth_learning": 0})
            if sum(dist.values()) > 0:
                fig = px.pie(
                    values=list(dist.values()),
                    names=list(dist.keys()),
                    title="Prediction Distribution",
                    color_discrete_sequence=["#ef4444", "#3b82f6", "#22c55e"]
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No classification data yet")
        
        with col2:
            by_date = data["classification"].get("by_date", {})
            if by_date:
                df_list = []
                for date, labels in by_date.items():
                    for label, count in labels.items():
                        df_list.append({"date": date, "label": label, "count": count})
                
                if df_list:
                    df = pd.DataFrame(df_list)
                    fig = px.bar(df, x="date", y="count", color="label", 
                               title="Predictions Over Time", barmode="stack")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No time-series data available")
        
        # Feedback progress
        st.subheader("Retraining Progress")
        feedback_count = data["feedback"]["classification_feedback"]
        threshold = config.retrain.classifier_threshold
        progress = min(feedback_count / max(threshold, 1), 1.0)
        st.progress(progress)
        st.caption(f"{feedback_count}/{threshold} feedback samples until next retraining")
    
    with tab2:
        st.header("Summarization Quality")
        
        summarization = data.get("summarization", {})
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Summaries", summarization.get("total_summaries", 0))
        with col2:
            st.metric("Avg ROUGE-L", f"{summarization.get('avg_rouge_l', 0):.3f}")
        with col3:
            st.metric("Avg Latency", f"{summarization.get('avg_latency_ms', 0):.0f}ms")
        
        # Summarizer feedback progress
        st.subheader("Retraining Progress")
        summary_feedback = data["feedback"]["summary_feedback"]
        summary_threshold = config.retrain.summarizer_threshold
        progress = min(summary_feedback / max(summary_threshold, 1), 1.0)
        st.progress(progress)
        st.caption(f"{summary_feedback}/{summary_threshold} feedback samples until next retraining")
    
    with tab3:
        st.header("Model Registry")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🏷️ Classifier")
            try:
                classifier_status = model_promoter.get_model_versions(CLASSIFIER_MODEL_NAME)
                if classifier_status.get("production_version"):
                    prod = classifier_status["production_version"]
                    st.success(f"Production: v{prod['version']}")
                else:
                    st.info("No production model registered")
                
                with st.expander("Version History"):
                    for v in classifier_status.get("versions", [])[:5]:
                        st.text(f"v{v['version']} - {v['stage']}")
            except Exception as e:
                st.warning(f"Could not load classifier info: {e}")
        
        with col2:
            st.subheader("📝 Summarizer")
            try:
                summarizer_status = model_promoter.get_model_versions(SUMMARIZER_MODEL_NAME)
                if summarizer_status.get("production_version"):
                    prod = summarizer_status["production_version"]
                    st.success(f"Production: v{prod['version']}")
                else:
                    st.info("No production model registered")
                
                with st.expander("Version History"):
                    for v in summarizer_status.get("versions", [])[:5]:
                        st.text(f"v{v['version']} - {v['stage']}")
            except Exception as e:
                st.warning(f"Could not load summarizer info: {e}")
        
        st.subheader("🎛️ Manual Controls")
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔙 Rollback Classifier"):
                try:
                    result = model_promoter.rollback(CLASSIFIER_MODEL_NAME)
                    if result.get("success"):
                        st.success("Classifier rolled back!")
                    else:
                        st.error(result.get("error", "Rollback failed"))
                except Exception as e:
                    st.error(f"Rollback failed: {e}")
        
        with col2:
            if st.button("🔙 Rollback Summarizer"):
                try:
                    result = model_promoter.rollback(SUMMARIZER_MODEL_NAME)
                    if result.get("success"):
                        st.success("Summarizer rolled back!")
                    else:
                        st.error(result.get("error", "Rollback failed"))
                except Exception as e:
                    st.error(f"Rollback failed: {e}")
    
    with tab4:
        st.header("Drift Detection")
        
        drift = data.get("drift", {})
        alert_level = drift.get("alert_level", "unknown")
        
        if alert_level == "high":
            st.error(f"⚠️ {drift.get('recommendation', 'Significant drift detected!')}")
        elif alert_level == "medium":
            st.warning(f"⚠️ {drift.get('recommendation', 'Drift may be emerging')}")
        elif alert_level == "low":
            st.success("✅ No significant drift detected")
        else:
            st.info("Drift detection status unknown")
        
        pred_drift = drift.get("prediction_drift", {})
        if pred_drift and not pred_drift.get("error"):
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Drift Statistic", f"{pred_drift.get('statistic', 0):.4f}")
            with col2:
                st.metric("P-Value", f"{pred_drift.get('p_value', 1):.4f}")
    
    # Footer
    st.divider()
    st.caption(f"Dashboard generated at: {datetime.utcnow().isoformat()}")


if __name__ == "__main__":
    main()
