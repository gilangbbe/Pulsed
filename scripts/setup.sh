#!/bin/bash
# Setup script for Pulsed project
# Run this once to initialize the development environment

set -e

echo "⚡ Setting up Pulsed - AI/ML News Filter"
echo "=========================================="

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1-2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Python $REQUIRED_VERSION or higher is required. Found: $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python version: $PYTHON_VERSION"

# Upgrade pip
echo "📦 Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "📦 Installing dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data/raw
mkdir -p data/processed
mkdir -p data/feedback
mkdir -p models/classifier
mkdir -p models/summarizer
mkdir -p logs
mkdir -p mlruns
mkdir -p notebooks

# Initialize database
echo "🗄️ Initializing database..."
python3 -c "
from src.utils.db import get_db
db = get_db()
db.init_db()
print('Database initialized successfully')
"

# Create .env file from example if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your actual configuration"
else
    echo "✅ .env file already exists"
fi

# Initialize DVC if not already initialized
if [ ! -d ".dvc" ]; then
    echo "📦 Initializing DVC..."
    dvc init
else
    echo "✅ DVC already initialized"
fi

# Initialize git if not already initialized
if [ ! -d ".git" ]; then
    echo "📦 Initializing git..."
    git init
    git add .
    git commit -m "Initial project setup"
else
    echo "✅ Git already initialized"
fi

echo ""
echo "=========================================="
echo "✅ Pulsed setup complete!"

