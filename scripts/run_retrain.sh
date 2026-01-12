#!/bin/bash
# Run model retraining pipelines
# This can be scheduled weekly or triggered manually

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "⚡ Running Pulsed Retraining Pipeline"
echo "======================================"
echo "Time: $(date)"

# Check which model to retrain
MODEL="${1:-both}"

if [ "$MODEL" == "classifier" ] || [ "$MODEL" == "both" ]; then
    echo ""
    echo "🏷️ Retraining Classifier..."
    echo "----------------------------"
    python3 -c "
from src.pipelines.retrain_classifier import ClassifierRetrainPipeline
pipeline = ClassifierRetrainPipeline()
result = pipeline.run()
print(f'Result: {result}')
"
fi

if [ "$MODEL" == "summarizer" ] || [ "$MODEL" == "both" ]; then
    echo ""
    echo "📝 Retraining Summarizer..."
    echo "----------------------------"
    python3 -c "
from src.pipelines.retrain_summarizer import SummarizerRetrainPipeline
pipeline = SummarizerRetrainPipeline()
result = pipeline.run()
print(f'Result: {result}')
"
fi

if [ "$MODEL" != "classifier" ] && [ "$MODEL" != "summarizer" ] && [ "$MODEL" != "both" ]; then
    echo "Unknown model: $MODEL"
    echo "Usage: $0 [classifier|summarizer|both]"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ Retraining complete!"
echo "Time: $(date)"
