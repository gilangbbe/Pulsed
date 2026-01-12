#!/bin/bash
# Deploy script for Pulsed application
# Handles starting API, dashboard, and scheduled tasks

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Activate virtual environment
# source venv/bin/activate

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

ACTION="${1:-help}"

case "$ACTION" in
    api)
        echo "Starting Pulsed API..."
        uvicorn src.api.main:app --host 0.0.0.0 --port 8000
        ;;
    
    api-dev)
        echo "Starting Pulsed API (development mode)..."
        uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
        ;;
    
    dashboard)
        echo "Starting Pulsed Dashboard..."
        streamlit run dashboards/monitoring.py --server.port 8501
        ;;
    
    mlflow)
        echo "Starting MLflow UI..."
        mlflow ui --host 0.0.0.0 --port 5001
        ;;
    
    all)
        echo "Starting all services..."
        echo "This will run services in the background"
        
        # Start MLflow
        mlflow ui --host 0.0.0.0 --port 5001&
        MLFLOW_PID=$!
        echo "MLflow UI started (PID: $MLFLOW_PID)"
        
        # Start API
        uvicorn src.api.main:app --host 0.0.0.0 --port 8000 &
        API_PID=$!
        echo "API started (PID: $API_PID)"
        
        # Start Dashboard
        streamlit run dashboards/monitoring.py --server.port 8501 &
        DASH_PID=$!
        echo "Dashboard started (PID: $DASH_PID)"
        
        echo ""
        echo "Services running:"
        echo "  - API:       http://localhost:8000"
        echo "  - Dashboard: http://localhost:8501"
        echo "  - MLflow:    http://localhost:5000"
        echo ""
        echo "Press Ctrl+C to stop all services"
        
        # Wait for any to exit
        wait
        ;;
    
    setup-cron)
        echo "📅 Setting up cron jobs..."
        
        # Get absolute path to scripts
        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        
        # Create cron entries
        (crontab -l 2>/dev/null || true; cat << EOF
# Pulsed - Hourly data fetch and inference
0 * * * * cd $(dirname "$SCRIPT_DIR") && $SCRIPT_DIR/run_daily.sh hourly >> logs/hourly.log 2>&1

# Pulsed - Daily digest at 6 PM
0 18 * * * cd $(dirname "$SCRIPT_DIR") && $SCRIPT_DIR/run_daily.sh daily >> logs/daily.log 2>&1

# Pulsed - Weekly retraining on Sundays at 2 AM
0 2 * * 0 cd $(dirname "$SCRIPT_DIR") && $SCRIPT_DIR/run_retrain.sh both >> logs/retrain.log 2>&1
EOF
        ) | crontab -
        
        echo "✅ Cron jobs installed:"
        echo "  - Hourly: data fetch and inference"
        echo "  - Daily: digest email at 6 PM"
        echo "  - Weekly: model retraining on Sundays"
        ;;
    
    status)
        echo "📊 Checking service status..."
        
        # Check if API is running
        if curl -s http://localhost:8000/health > /dev/null 2>&1; then
            echo "✅ API: Running"
        else
            echo "❌ API: Not running"
        fi
        
        # Check if Dashboard is running
        if curl -s http://localhost:8501 > /dev/null 2>&1; then
            echo "✅ Dashboard: Running"
        else
            echo "❌ Dashboard: Not running"
        fi
        
        # Check if MLflow is running
        if curl -s http://localhost:5000 > /dev/null 2>&1; then
            echo "✅ MLflow: Running"
        else
            echo "❌ MLflow: Not running"
        fi
        ;;
    
    help|*)
        echo "Pulsed Deployment Script"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  api        - Start the API server"
        echo "  api-dev    - Start the API server in development mode"
        echo "  dashboard  - Start the Streamlit dashboard"
        echo "  mlflow     - Start the MLflow UI"
        echo "  all        - Start all services"
        echo "  setup-cron - Install cron jobs for scheduled tasks"
        echo "  status     - Check service status"
        echo "  help       - Show this help message"
        ;;
esac
