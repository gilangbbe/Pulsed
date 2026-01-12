#!/bin/bash
# Train initial models using bootstrap-labeled data
# Run this after init_db.sh to create the first models

set -e

# Change to project directory
cd "$(dirname "$0")/.."

# Set environment
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "⚡ Training Initial Pulsed Models"
echo "=================================="
echo "Time: $(date)"

MODEL="${1:-classifier}"

if [ "$MODEL" == "classifier" ] || [ "$MODEL" == "both" ]; then
    echo ""
    echo "🏷️ Training Initial Classifier..."
    echo "-----------------------------------"
    python3 -c "
import sys
sys.path.insert(0, '.')

from src.models.classifier.train import ClassifierTrainer
from src.models.classifier.config import ClassifierConfig
from src.utils.db import get_db
from src.utils.mlflow_utils import MLflowManager, CLASSIFIER_MODEL_NAME
from loguru import logger

# Get articles with heuristic labels from database
db = get_db()
db.init_db()

# Query articles - we'll use heuristic labels stored in metadata
# For now, we'll fetch and label on the fly
from src.data.fetch import DataFetcher
from src.data.preprocess import Preprocessor
from src.data.label import Labeler

logger.info('Fetching articles for training...')
fetcher = DataFetcher()
articles = fetcher.fetch_raw(include_reddit=False, include_pwc=False, days_back=7)
logger.info(f'Fetched {len(articles)} articles')

# Preprocess
preprocessor = Preprocessor()
processed = preprocessor.process_batch(articles)
unique = preprocessor.deduplicate(processed)
logger.info(f'After preprocessing: {len(unique)} unique articles')

# Label with heuristics
labeler = Labeler()
labeled = labeler.label_batch(unique, return_confidence=True)

# Filter to high-confidence labels only for training
high_conf = [a for a in labeled if a.get('label_confidence', 0) >= 0.5]
logger.info(f'High confidence samples: {len(high_conf)}')

if len(high_conf) < 10:
    logger.error('Not enough high-confidence samples for training. Need at least 10.')
    sys.exit(1)

# Prepare training data
from collections import Counter
label_dist = Counter(a['heuristic_label'] for a in high_conf)
logger.info(f'Label distribution: {dict(label_dist)}')

# Create training data in the format the trainer expects
train_articles = []
for article in high_conf:
    train_articles.append({
        'title': article.get('title', ''),
        'abstract': article.get('abstract', ''),
        'full_text': article.get('full_text', ''),
        'label': article['heuristic_label'],
    })

logger.info(f'Prepared {len(train_articles)} articles for training')

# Train model
logger.info('Training classifier...')
config = ClassifierConfig(
    num_epochs=3,  # Quick initial training
    batch_size=8,
    learning_rate=2e-5,
)
trainer = ClassifierTrainer(config)

# Run training - pass articles directly, trainer handles the rest
metrics = trainer.train(train_articles, output_dir='models/classifier/initial')
logger.info(f'Training complete! Metrics: {metrics}')

# Save and register model
import mlflow
mlflow_manager = MLflowManager()

# The trainer already logged to MLflow, now just promote to Production
from mlflow.tracking import MlflowClient
client = MlflowClient()

# Get the latest version
try:
    versions = client.search_model_versions(f\"name='{CLASSIFIER_MODEL_NAME}'\")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        client.transition_model_version_stage(
            name=CLASSIFIER_MODEL_NAME,
            version=latest.version,
            stage='Production',
        )
        logger.info(f'Promoted version {latest.version} to Production')
    else:
        logger.warning('No model versions found to promote')
except Exception as e:
    logger.warning(f'Could not promote model: {e}')

print('✅ Classifier training complete!')
"
fi

if [ "$MODEL" == "summarizer" ] || [ "$MODEL" == "both" ]; then
    echo ""
    echo "Note: Summarizer uses pre-trained model (BART-large-cnn)"
    echo "No initial training needed - will fine-tune from feedback later."
    echo ""
    echo "Registering pre-trained summarizer in MLflow..."
    python3 -c "
import sys
sys.path.insert(0, '.')

import mlflow
from mlflow.tracking import MlflowClient
from src.utils.mlflow_utils import MLflowManager, SUMMARIZER_MODEL_NAME
from src.models.summarizer.config import SummarizerConfig
from loguru import logger

logger.info('Registering pre-trained summarizer model...')

mlflow_manager = MLflowManager()

with mlflow.start_run(run_name='initial_summarizer_registration'):
    config = SummarizerConfig()
    
    # Log config as parameters
    mlflow.log_params({
        'model_name': config.model_name,
        'max_input_length': config.max_input_length,
        'brief_max_length': config.brief_max_length,
        'detailed_max_length': config.detailed_max_length,
        'type': 'pre-trained',
    })
    
    # Load the pre-trained model and tokenizer
    from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
    logger.info(f'Loading pre-trained model: {config.model_name}')
    
    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    model = AutoModelForSeq2SeqLM.from_pretrained(config.model_name)
    
    # Save to local directory first
    import os
    save_dir = 'models/summarizer/initial'
    os.makedirs(save_dir, exist_ok=True)
    model.save_pretrained(save_dir)
    tokenizer.save_pretrained(save_dir)
    
    # Log the model with MLflow transformers flavor
    logger.info('Logging model to MLflow...')
    import mlflow.transformers
    mlflow.transformers.log_model(
        transformers_model={
            'model': model,
            'tokenizer': tokenizer,
        },
        artifact_path='model',
        registered_model_name=SUMMARIZER_MODEL_NAME,
    )
    
    # Get the registered version and promote to Production
    from mlflow.tracking import MlflowClient
    client = MlflowClient()
    versions = client.search_model_versions(f\"name='{SUMMARIZER_MODEL_NAME}'\")
    if versions:
        latest = max(versions, key=lambda v: int(v.version))
        client.transition_model_version_stage(
            name=SUMMARIZER_MODEL_NAME,
            version=latest.version,
            stage='Production',
        )
        logger.info(f'Promoted version {latest.version} to Production')

print('✅ Summarizer registration complete!')
"
fi

echo ""
echo "=================================="
echo "✅ Initial training complete!"
echo "Time: $(date)"
echo ""
echo "You can now run: ./scripts/deploy.sh api"
