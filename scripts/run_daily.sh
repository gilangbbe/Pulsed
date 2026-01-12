#!/bin/bash
# Run the daily pipeline
# This should be scheduled via cron to run multiple times per day

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "⚡ Running Pulsed Daily Pipeline"
echo "================================="
echo "Time: $(date)"

# Check run type
RUN_TYPE="${1:-hourly}"

if [ "$RUN_TYPE" == "hourly" ]; then
    echo "Running hourly fetch and inference..."
    python3 -c "
from src.pipelines.daily import run_hourly
stats = run_hourly()
print(f'Processed: {stats}')
"

elif [ "$RUN_TYPE" == "daily" ]; then
    echo "Running full daily pipeline with digest..."
    python3 -c "
from src.pipelines.daily import run_daily
stats = run_daily()
print(f'Daily stats: {stats}')
"

else
    echo "Unknown run type: $RUN_TYPE"
    echo "Usage: $0 [hourly|daily]"
    exit 1
fi

echo ""
echo "================================="
echo "✅ Pipeline complete!"
echo "Time: $(date)"
