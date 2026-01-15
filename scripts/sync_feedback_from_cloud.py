#!/usr/bin/env python3
"""
Sync feedback from Supabase back to local database.

This script pulls feedback from the cloud database and stores it in the local
news.db for use in model retraining.

Usage:
    python scripts/sync_feedback_from_cloud.py
    python scripts/sync_feedback_from_cloud.py --days 7  # Last 7 days only
"""

import argparse
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)

from src.utils.db import get_db

# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase_client() -> Client:
    """Create Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Missing Supabase credentials")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def sync_article_feedback(supabase: Client, days: int = None):
    """
    Sync article feedback from Supabase to local database.
    
    The subscriber_feedback table has ratings: useful, not_useful, already_knew
    We'll map these to the local feedback system.
    """
    print("\nSyncing article feedback from cloud...")
    
    # Build query
    query = supabase.from_("subscriber_feedback").select("*")
    
    if days:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        query = query.gte("created_at", cutoff)
    
    result = query.execute()
    cloud_feedback = result.data or []
    
    print(f"Found {len(cloud_feedback)} feedback items in cloud")
    
    if not cloud_feedback:
        return 0
    
    db = get_db()
    synced = 0
    
    for item in cloud_feedback:
        article_id = item['article_id']
        rating = item['rating']
        
        # Map subscriber ratings to internal feedback
        # "useful" -> good article, keep this classification
        # "not_useful" -> should have been classified differently  
        # "already_knew" -> not bad, but maybe less important
        
        # Get the current prediction for this article
        prediction = db.get_prediction_by_article_id(article_id)
        
        if not prediction:
            print(f"  Warning: No prediction found for article {article_id}, skipping")
            continue
        
        original_label = prediction.get('predicted_label')
        
        # Determine corrected label based on feedback
        if rating == 'useful':
            # User found it useful - current label is correct
            corrected_label = original_label
        elif rating == 'not_useful':
            # User didn't find it useful - might need different classification
            # If it was marked "important" or "worth_learning", maybe it should be "garbage"
            if original_label in ['important', 'worth_learning']:
                corrected_label = 'garbage'
            else:
                corrected_label = original_label  # Already classified low
        elif rating == 'already_knew':
            # Not bad content, but maybe overestimated importance
            if original_label == 'important':
                corrected_label = 'worth_learning'
            else:
                corrected_label = original_label
        else:
            corrected_label = original_label
        
        # Only add feedback if there's a meaningful correction
        if corrected_label != original_label or rating == 'useful':
            try:
                db.add_feedback(
                    feedback_type="classification",
                    article_id=article_id,
                    original_value=original_label,
                    corrected_value=corrected_label,
                    user_id=item.get('subscriber_id'),
                    comment=f"Cloud feedback: {rating}" + (f" - {item.get('comment')}" if item.get('comment') else ""),
                )
                synced += 1
            except Exception as e:
                print(f"  Error syncing feedback for {article_id}: {e}")
    
    print(f"  Synced {synced} feedback items to local database")
    return synced


def main():
    parser = argparse.ArgumentParser(
        description="Sync feedback from Supabase to local database"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Only sync feedback from last N days"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("Syncing Feedback from Cloud")
    print("=" * 60)
    
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        sys.exit(1)
    
    total_synced = sync_article_feedback(supabase, args.days)
    
    print("\n" + "=" * 60)
    print(f"Sync Complete! Total feedback synced: {total_synced}")
    print("=" * 60)


if __name__ == "__main__":
    main()
