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
        page_title="Pulsed Monitor",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    
    # Custom CSS for professional styling
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
        
        html, body, [class*="css"] {
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            color: var(--text-color);
        }
        
        /* Main Container Background */
        .stApp {
            background-color: var(--background-color);
        }

        /* Header Styling */
        .main-header-container {
            padding: 2rem 0 1rem 0;
            border-bottom: 1px solid var(--secondary-background-color);
            margin-bottom: 2rem;
        }
        
        .main-header {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-color);
            margin: 0;
            line-height: 1.2;
        }
        
        .sub-header {
            font-size: 1rem;
            color: var(--text-color);
            opacity: 0.7;
            margin-top: 0.5rem;
            font-weight: 400;
        }
        
        /* Card Styling */
        div[data-testid="stMetric"], .metric-card {
            background-color: var(--secondary-background-color);
            padding: 1.5rem;
            border-radius: 0.75rem;
            border: 1px solid rgba(128, 128, 128, 0.2);
            box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1);
            transition: box-shadow 0.2s ease;
        }
        
        div[data-testid="stMetric"]:hover, .metric-card:hover {
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            border-color: rgba(128, 128, 128, 0.3);
        }

        div[data-testid="stMetricValue"] {
            font-size: 2rem !important;
            font-weight: 700 !important;
            color: var(--text-color) !important;
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.875rem !important;
            font-weight: 500 !important;
            color: var(--text-color) !important;
            opacity: 0.7;
        }
        
        /* Custom Custom Card Content */
        .card-label {
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-color);
            opacity: 0.7;
            margin-bottom: 0.25rem;
        }
        
        .card-value {
            font-size: 2rem;
            font-weight: 700;
            color: var(--text-color);
        }

        /* Status Badges */
        .status-badge {
            display: inline-flex;
            align-items: center;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            margin-top: 0.5rem;
        }
        
        .status-good {
            background-color: rgba(16, 185, 129, 0.1);
            color: #10b981;
            border: 1px solid rgba(16, 185, 129, 0.2);
        }
        
        .status-warning {
            background-color: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.2);
        }
        
        .status-critical {
            background-color: rgba(239, 68, 68, 0.1);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.2);
        }
        
        .status-unknown {
            background-color: rgba(107, 114, 128, 0.1);
            color: #6b7280;
            border: 1px solid rgba(107, 114, 128, 0.2);
        }
        
        /* Tabs Styling */
        .stTabs [data-baseweb="tab-list"] {
            background-color: transparent;
            padding: 0.5rem 0;
            border-bottom: 1px solid var(--secondary-background-color);
            gap: 2rem;
        }

        .stTabs [data-baseweb="tab"] {
            height: auto;
            white-space: pre-wrap;
            background-color: transparent;
            border: none;
            color: var(--text-color);
            opacity: 0.6;
            font-weight: 500;
            padding: 0.5rem 1rem;
        }

        .stTabs [aria-selected="true"] {
            color: var(--primary-color, #2563eb);
            opacity: 1;
            border-bottom: 2px solid var(--primary-color, #2563eb);
            font-weight: 600;
        }
        
        /* Button Styling */
        div.stButton > button {
            border-radius: 0.5rem;
            font-weight: 500;
            border: 1px solid rgba(128, 128, 128, 0.2);
            padding: 0.5rem 1rem;
            transition: all 0.2s;
            background-color: var(--secondary-background-color);
            color: var(--text-color);
        }
        
        div.stButton > button:hover {
            border-color: var(--primary-color, #2563eb);
            color: var(--primary-color, #2563eb);
            background-color: rgba(37, 99, 235, 0.05);
        }
        
        /* Sidebar Styling */
        [data-testid="stSidebar"] {
            background-color: var(--secondary-background-color);
            border-right: 1px solid rgba(128, 128, 128, 0.1);
        }
        
        [data-testid="stSidebar"] .stMarkdown h1, 
        [data-testid="stSidebar"] .stMarkdown h2, 
        [data-testid="stSidebar"] .stMarkdown h3 {
            color: var(--text-color);
            font-weight: 600;
        }
        
        hr {
            border-color: rgba(128, 128, 128, 0.2);
        }

        </style>
    """, unsafe_allow_html=True)
    
    # Header
    st.markdown("""
        <div class="main-header-container">
            <h1 class="main-header">Pulsed Monitor</h1>
            <p class="sub-header">Real-time observability for ML/AI classification & summarization pipelines</p>
        </div>
    """, unsafe_allow_html=True)
    
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
    with st.sidebar:
        st.header("Control Panel")
        days_back = st.slider("Analysis Period", min_value=1, max_value=30, value=7, help="Select the number of days to analyze")
        
        st.markdown("### Actions")
        if st.button("Refresh Dashboard", use_container_width=True):
            st.rerun()
            
        st.divider()
        st.markdown(f"""
            <div style='font-size: 0.75rem; color: #9ca3af;'>
                Last Synced<br>
                <span style='color: #4b5563; font-weight: 500;'>{datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</span>
            </div>
        """, unsafe_allow_html=True)
    
    # Get dashboard data
    try:
        data = metrics_collector.get_dashboard_data(days=days_back)
    except Exception as e:
        # Graceful fallback data structure
        st.error(f"Error loading metrics: {e}")
        data = {
            "classification": {"total_predictions": 0, "distribution_pct": {}, "by_date": {}},
            "feedback": {"total_feedback": 0, "unused_classification_feedback": 0, "unused_summary_feedback": 0},
            "summarization": {"total_summaries": 0, "avg_rouge_l": 0, "avg_latency_ms": 0},
            "drift": {"alert_level": "unknown"},
        }
    
    # Top-level metrics
    st.markdown("### System Overview")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Predictions",
            f"{data['classification']['total_predictions']:,}",
            delta=None,
            help="Total articles classified in the selected period"
        )
    
    with col2:
        wl_pct = data['classification']['distribution_pct'].get('worth_learning', 0)
        st.metric(
            "Worth Learning",
            f"{wl_pct}%",
            help="Percentage of articles classified as 'worth learning'"
        )
    
    with col3:
        st.metric(
            "Feedback Volume",
            f"{data['feedback']['total_feedback']:,}",
            help="Total user feedback received"
        )
    
    with col4:
        drift_status = data["drift"].get("alert_level", "unknown")
        drift_display = {"low": "Stable", "medium": "Warning", "high": "Critical"}.get(drift_status, "Unknown")
        drift_class = {"low": "status-good", "medium": "status-warning", "high": "status-critical"}.get(drift_status, "status-unknown")
        
        st.markdown(f"""
            <div class="metric-card">
                <div class="card-label">Model Health</div>
                <div class="status-badge {drift_class}">
                    {drift_display}
                </div>
            </div>
        """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Main content tabs
    tab1, tab2, tab3, tab4 = st.tabs([
        "Classification",
        "Summarization", 
        "Model Registry",
        "Drift Analysis"
    ])
    
    with tab1:
        st.markdown("#### Classification Performance")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            dist = data["classification"].get("distribution", {"garbage": 0, "important": 0, "worth_learning": 0})
            if sum(dist.values()) > 0:
                fig = px.pie(
                    values=list(dist.values()),
                    names=list(dist.keys()),
                    title="Class Distribution",
                    color=list(dist.keys()),
                    color_discrete_map={
                        "garbage": "#ef4444",
                        "important": "#3b82f6",
                        "worth_learning": "#22c55e"
                    },
                    hole=0.6
                )
                fig.update_layout(
                    showlegend=True,
                    height=300,
                    margin=dict(t=30, b=0, l=0, r=0),
                    font=dict(family="Inter", size=12),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No classification data available for the selected period")
        
        with col2:
            by_date = data["classification"].get("by_date", {})
            if by_date:
                df_list = []
                for date, labels in by_date.items():
                    for label, count in labels.items():
                        df_list.append({"date": date, "label": label, "count": count})
                
                if df_list:
                    df = pd.DataFrame(df_list)
                    fig = px.bar(
                        df, 
                        x="date", 
                        y="count", 
                        color="label", 
                        title="Predictions Volume Trend",
                        barmode="stack",
                        color_discrete_map={
                            "garbage": "#ef4444",
                            "important": "#3b82f6",
                            "worth_learning": "#22c55e"
                        }
                    )
                    fig.update_layout(
                        xaxis_title=None,
                        yaxis_title="Predictions",
                        height=300,
                        margin=dict(t=30, b=0, l=0, r=0),
                        font=dict(family="Inter", size=12),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        xaxis=dict(showgrid=False),
                        yaxis=dict(showgrid=True, gridcolor="#f3f4f6"),
                    )
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No time-series data available")
        
        # Feedback progress
        st.markdown("#### Retraining Readiness")
        st.caption("Tracking feedback volume against retraining thresholds")
        
        unused_feedback = data["feedback"]["unused_classification_feedback"]
        threshold = config.retrain.classifier_threshold
        progress = min(unused_feedback / max(threshold, 1), 1.0)
        
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(progress)
            with col2:
                st.write(f"**{unused_feedback}** / {threshold} samples")
            
            if unused_feedback >= threshold:
                st.success("✨ Ready for retraining")
            else:
                remaining = threshold - unused_feedback
                st.info(f"Collecting feedback... ({remaining} more needed)")
    
    with tab2:
        st.markdown("#### Summarization Quality")
        
        summarization = data.get("summarization", {})
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Summaries", f"{summarization.get('total_summaries', 0):,}")
        with col2:
            rouge = summarization.get('avg_rouge_l', 0)
            st.metric("Avg ROUGE-L", f"{rouge:.3f}")
        with col3:
            latency = summarization.get('avg_latency_ms', 0)
            st.metric("Avg Latency", f"{latency:.0f}ms")
        
        # Summarizer feedback progress
        st.markdown("#### Retraining Readiness")
        unused_summary_feedback = data["feedback"]["unused_summary_feedback"]
        summary_threshold = config.retrain.summarizer_threshold
        progress = min(unused_summary_feedback / max(summary_threshold, 1), 1.0)
        
        with st.container():
            col1, col2 = st.columns([3, 1])
            with col1:
                st.progress(progress)
            with col2:
                st.write(f"**{unused_summary_feedback}** / {summary_threshold} samples")
            
            if unused_summary_feedback >= summary_threshold:
                st.success("✨ Ready for retraining")
            else:
                remaining = summary_threshold - unused_summary_feedback
                st.info(f"Collecting feedback... ({remaining} more needed)")
    
    with tab3:
        st.markdown("#### Model Registry")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("##### Classifier")
            try:
                classifier_status = model_promoter.get_model_versions(CLASSIFIER_MODEL_NAME)
                if classifier_status.get("production_version"):
                    prod = classifier_status["production_version"]
                    st.success(f"**Production**: v{prod['version']}")
                    st.caption(f"Deployed: {prod.get('creation_timestamp', 'N/A')}")
                else:
                    st.warning("No production model")
                
                with st.expander("Version History"):
                    versions = classifier_status.get("versions", [])[:5]
                    if versions:
                        st.table(pd.DataFrame(versions)[['version', 'stage']].set_index('version'))
                    else:
                        st.caption("No versions available")
            except Exception as e:
                st.error(f"Error loading classifier: {e}")
        
        with col2:
            st.markdown("##### Summarizer")
            try:
                summarizer_status = model_promoter.get_model_versions(SUMMARIZER_MODEL_NAME)
                if summarizer_status.get("production_version"):
                    prod = summarizer_status["production_version"]
                    st.success(f"**Production**: v{prod['version']}")
                    st.caption(f"Deployed: {prod.get('creation_timestamp', 'N/A')}")
                else:
                    st.warning("No production model")
                
                with st.expander("Version History"):
                    versions = summarizer_status.get("versions", [])[:5]
                    if versions:
                        st.table(pd.DataFrame(versions)[['version', 'stage']].set_index('version'))
                    else:
                        st.caption("No versions available")
            except Exception as e:
                st.error(f"Error loading summarizer: {e}")
        
        st.divider()
        st.markdown("#### Operational Controls")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Rollback Classifier", type="secondary", use_container_width=True):
                try:
                    result = model_promoter.rollback(CLASSIFIER_MODEL_NAME)
                    if result.get("success"):
                        st.success("Classifier rolled back successfully")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Rollback failed"))
                except Exception as e:
                    st.error(f"Rollback exception: {e}")
        
        with col2:
            if st.button("Rollback Summarizer", type="secondary", use_container_width=True):
                try:
                    result = model_promoter.rollback(SUMMARIZER_MODEL_NAME)
                    if result.get("success"):
                        st.success("Summarizer rolled back successfully")
                        st.rerun()
                    else:
                        st.error(result.get("error", "Rollback failed"))
                except Exception as e:
                    st.error(f"Rollback exception: {e}")
    
    with tab4:
        st.markdown("#### Drift Analysis")
        
        drift = data.get("drift", {})
        alert_level = drift.get("alert_level", "unknown")
        
        if alert_level == "high":
            st.error(drift.get('recommendation', 'Significant drift detected - consider retraining'))
        elif alert_level == "medium":
            st.warning(drift.get('recommendation', 'Moderate drift detected - monitor closely'))
        elif alert_level == "low":
            st.success("No significant drift detected - models performing within expected parameters")
        else:
            st.info("Insufficient data for drift detection")
        
        pred_drift = drift.get("prediction_drift", {})
        if pred_drift and not pred_drift.get("error"):
            st.markdown("##### Statistical Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Drift Statistic", f"{pred_drift.get('statistic', 0):.4f}")
            with col2:
                p_value = pred_drift.get('p_value', 1)
                st.metric("P-Value", f"{p_value:.4f}")
                if p_value < 0.05:
                    st.caption("⚠️ Statistically significant (p < 0.05)")

if __name__ == "__main__":
    main()

