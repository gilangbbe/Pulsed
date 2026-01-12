#!/bin/bash
# Initialize database with schema and bootstrap data
# Run this after setup.sh

set -e

echo "Initializing Pulsed Database"
echo "================================"

# Initialize database schema
echo "Creating database schema..."
python3 -c "
from src.utils.db import get_db

db = get_db()
db.init_db()
print('✅ Database schema created')
"

# Optionally fetch initial data for labeling
echo ""
echo "Fetching initial data for bootstrap labeling..."
python3 -c "
from src.data.fetch import DataFetcher
from src.data.preprocess import Preprocessor
from src.data.label import Labeler
from src.utils.db import get_db

# Fetch some initial articles (raw, without storing)
fetcher = DataFetcher()
articles = fetcher.fetch_raw(include_reddit=True)  # Now using JSON scraping, no API needed
print(f'Fetched {len(articles)} raw articles')

# Preprocess
preprocessor = Preprocessor()
processed = preprocessor.process_batch(articles)
print(f'After preprocessing: {len(processed)} articles')

# Deduplicate
unique = preprocessor.deduplicate(processed)
print(f'After deduplication: {len(unique)} unique articles')

# Apply bootstrap labels
labeler = Labeler()
labeled = labeler.label_batch(unique, return_confidence=True)

# Count by label
from collections import Counter
label_counts = Counter(a.get('heuristic_label', 'unknown') for a in labeled)
print(f'Bootstrap labels: {dict(label_counts)}')

# Show some examples for verification
print('\\nSample labeled articles:')
for i, article in enumerate(labeled[:3]):
    print(f'{i+1}. [{article.get(\"heuristic_label\")}] {article.get(\"title\", \"No title\")[:80]}')

# Store in database
db = get_db()
stored = 0
for article in labeled:
    try:
        inserted = db.insert_article(
            article_id=article.get('article_id'),
            source=article.get('source'),
            title=article.get('title'),
            url=article.get('url'),
            abstract=article.get('abstract'),
            full_text=article.get('full_text'),
            published_date=article.get('published_date'),
            metadata=article.get('metadata', {}),
        )
        if inserted:
            stored += 1
    except Exception as e:
        print(f'Warning: Failed to store article: {e}')
        
print(f'✅ Stored {stored} articles in database')
"

echo ""
echo "================================"
echo "✅ Database initialization complete!"

