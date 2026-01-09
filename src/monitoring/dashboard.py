"""Streamlit monitoring dashboard."""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta

# Import monitoring utilities
import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from src.monitoring.metrics import MetricsCollector
from src.monitoring.drift import DriftDetector
from src.pipelines.promote import ModelPromoter
from src.utils.db import get_db
from src.utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME, SUMMARIZER_MODEL_NAME


def create_dashboard():
    """Create and run the Streamlit monitoring dashboard."""
    
    st.set_page_config(
        page_title="Pulsed - ML Monitor",
        page_icon="⚡",
        layout="wide",
    )
    
    st.title("⚡ Pulsed Monitoring Dashboard")
    st.markdown("Real-time monitoring for your AI/ML news filter")
    
    # Initialize components
    metrics_collector = MetricsCollector()
    drift_detector = DriftDetector()
    model_promoter = ModelPromoter()
    
    # Sidebar
    st.sidebar.header("Settings")
    days_back = st.sidebar.slider("Days to analyze", 1, 30, 7)
    auto_refresh = st.sidebar.checkbox("Auto-refresh (60s)", False)
    
    if auto_refresh:
        st.experimental_rerun()
    
    # Get dashboard data
    data = metrics_collector.get_dashboard_data(days=days_back)
    
    # Top-level metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Predictions",
            data["classification"]["total_predictions"],
            help="Total articles classified in the period"
        )
    
    with col2:
        st.metric(
            "Worth Learning",
            f"{data['classification']['distribution_pct'].get('worth_learning', 0)}%",
            help="Percentage of articles marked as worth learning"
        )
    
    with col3:
        st.metric(
            "Total Feedback",
            data["feedback"]["total_feedback"],
            help="Total feedback items collected"
        )
    
    with col4:
        drift_status = data["drift"]["alert_level"]
        drift_color = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(drift_status, "⚪")
        st.metric(
            "Drift Alert",
            f"{drift_color} {drift_status.title()}",
            help="Data drift detection status"
        )
    
    st.divider()
    
    # Tabs for different sections
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Classification",
        "📝 Summarization",
        "🔄 Model Registry",
        "⚠️ Drift Detection"
    ])
    
    with tab1:
        st.header("Classification Performance")
        
        # Distribution pie chart
        col1, col2 = st.columns([1, 2])
        
        with col1:
            dist = data["classification"]["distribution"]
            fig = px.pie(
                values=list(dist.values()),
                names=list(dist.keys()),
                title="Prediction Distribution",
                color_discrete_sequence=["#ef4444", "#3b82f6", "#22c55e"]
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            # Distribution over time
            by_date = data["classification"]["by_date"]
            if by_date:
                df = pd.DataFrame([
                    {"date": date, "label": label, "count": count}
                    for date, labels in by_date.items()
                    for label, count in labels.items()
                ])
                
                fig = px.bar(
                    df,
                    x="date",
                    y="count",
                    color="label",
                    title="Predictions Over Time",
                    barmode="stack"
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No prediction data available for the selected period")
        
        # Feedback progress
        st.subheader("Feedback Collection Progress")
        
        from src.utils.config import config
        feedback_count = data["feedback"]["classification_feedback"]
        threshold = config.retrain.classifier_threshold
        
        progress = min(feedback_count / threshold, 1.0)
        st.progress(progress)
        st.caption(f"{feedback_count}/{threshold} samples until next retraining")
    
    with tab2:
        st.header("Summarization Quality")
        
        summarization = data["summarization"]
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Summaries", summarization["total_summaries"])
        
        with col2:
            st.metric("Avg ROUGE-L", f"{summarization['avg_rouge_l']:.3f}")
        
        with col3:
            st.metric("Avg Latency", f"{summarization['avg_latency_ms']:.0f}ms")
        
        # Summary feedback progress
        st.subheader("Feedback Collection Progress")
        
        summary_feedback = data["feedback"]["summary_feedback"]
        summary_threshold = config.retrain.summarizer_threshold
        
        progress = min(summary_feedback / summary_threshold, 1.0)
        st.progress(progress)
        st.caption(f"{summary_feedback}/{summary_threshold} samples until next retraining")
    
    with tab3:
        st.header("Model Registry")
        
        # Get model versions
        try:
            classifier_status = model_promoter.get_model_versions(CLASSIFIER_MODEL_NAME)
            summarizer_status = model_promoter.get_model_versions(SUMMARIZER_MODEL_NAME)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("🏷️ Classifier")
                
                if classifier_status.get("production_version"):
                    prod = classifier_status["production_version"]
                    st.success(f"Production: v{prod['version']}")
                else:
                    st.warning("No production model")
                
                if classifier_status.get("staging_version"):
                    staging = classifier_status["staging_version"]
                    st.info(f"Staging: v{staging['version']}")
                
                # Version history
                with st.expander("Version History"):
                    for v in classifier_status.get("versions", [])[:5]:
                        st.text(f"v{v['version']} - {v['stage']}")
            
            with col2:
                st.subheader("📝 Summarizer")
                
                if summarizer_status.get("production_version"):
                    prod = summarizer_status["production_version"]
                    st.success(f"Production: v{prod['version']}")
                else:
                    st.warning("No production model")
                
                if summarizer_status.get("staging_version"):
                    staging = summarizer_status["staging_version"]
                    st.info(f"Staging: v{staging['version']}")
                
                with st.expander("Version History"):
                    for v in summarizer_status.get("versions", [])[:5]:
                        st.text(f"v{v['version']} - {v['stage']}")
            
        except Exception as e:
            st.error(f"Could not load model registry: {e}")
        
        # Manual promotion controls
        st.subheader("Manual Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("🔄 Rollback Classifier"):
                result = model_promoter.rollback(CLASSIFIER_MODEL_NAME)
                if result.get("success"):
                    st.success("Classifier rolled back!")
                else:
                    st.error(result.get("error", "Rollback failed"))
        
        with col2:
            if st.button("🔄 Rollback Summarizer"):
                result = model_promoter.rollback(SUMMARIZER_MODEL_NAME)
                if result.get("success"):
                    st.success("Summarizer rolled back!")
                else:
                    st.error(result.get("error", "Rollback failed"))
    
    with tab4:
        st.header("Drift Detection")
        
        drift = data["drift"]
        
        # Alert banner
        alert_level = drift.get("alert_level", "low")
        if alert_level == "high":
            st.error(f"⚠️ {drift.get('recommendation', 'Significant drift detected!')}")
        elif alert_level == "medium":
            st.warning(f"⚠️ {drift.get('recommendation', 'Drift may be emerging')}")
        else:
            st.success("✅ No significant drift detected")
        
        # Prediction drift details
        pred_drift = drift.get("prediction_drift", {})
        
        if pred_drift:
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Drift Statistic",
                    f"{pred_drift.get('statistic', 0):.4f}",
                    help="Chi-square or KS statistic"
                )
            
            with col2:
                st.metric(
                    "P-Value",
                    f"{pred_drift.get('p_value', 1):.4f}",
                    help="Lower p-value indicates stronger drift"
                )
            
            # Distribution comparison
            if "reference_distribution" in pred_drift and "current_distribution" in pred_drift:
                st.subheader("Distribution Comparison")
                
                ref = pred_drift["reference_distribution"]
                cur = pred_drift["current_distribution"]
                
                df = pd.DataFrame({
                    "Category": list(ref.keys()),
                    "Reference": list(ref.values()),
                    "Current": list(cur.values()),
                })
                
                fig = go.Figure()
                fig.add_trace(go.Bar(name="Reference", x=df["Category"], y=df["Reference"]))
                fig.add_trace(go.Bar(name="Current", x=df["Category"], y=df["Current"]))
                fig.update_layout(barmode="group", title="Prediction Distribution: Reference vs Current")
                
                st.plotly_chart(fig, use_container_width=True)
    
    # Footer
    st.divider()
    st.caption(f"Last updated: {data['generated_at']}")


if __name__ == "__main__":
    create_dashboard()
