#!/usr/bin/env python3
"""
Sync local SQLite database to Supabase PostgreSQL.

This script uploads articles, predictions, and summaries from the local
news.db to the Supabase cloud database for the live web service.

Usage:
    python scripts/sync_to_cloud.py
    python scripts/sync_to_cloud.py --date 2024-01-15  # Sync specific date
    python scripts/sync_to_cloud.py --all  # Sync all data
"""

import argparse
import os
import sqlite3
import sys
from datetime import datetime, date, timedelta
from typing import Optional
from dotenv import load_dotenv

load_dotenv() 

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase import create_client, Client
except ImportError:
    print("Error: supabase-py not installed. Run: pip install supabase")
    sys.exit(1)


# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for full access
LOCAL_DB_PATH = os.getenv("LOCAL_DB_PATH", "data/news.db")


def get_supabase_client() -> Client:
    """Create Supabase client with service role key."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError(
            "Missing Supabase credentials. Set SUPABASE_URL and SUPABASE_SERVICE_KEY environment variables."
        )
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def get_local_db_connection() -> sqlite3.Connection:
    """Connect to local SQLite database."""
    if not os.path.exists(LOCAL_DB_PATH):
        raise FileNotFoundError(f"Local database not found: {LOCAL_DB_PATH}")
    
    conn = sqlite3.connect(LOCAL_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def sync_articles(supabase: Client, conn: sqlite3.Connection, target_date: Optional[date] = None, sync_all: bool = False):
    """Sync articles from local DB to Supabase."""
    cursor = conn.cursor()
    
    if sync_all:
        cursor.execute("SELECT * FROM raw_articles")
    elif target_date:
        cursor.execute(
            "SELECT * FROM raw_articles WHERE DATE(fetched_date) = ?",
            (target_date.isoformat(),)
        )
    else:
        # Default: sync today's articles
        today = date.today().isoformat()
        cursor.execute(
            "SELECT * FROM raw_articles WHERE DATE(fetched_date) = ?",
            (today,)
        )
    
    articles = cursor.fetchall()
    print(f"Found {len(articles)} articles to sync")
    
    synced = 0
    errors = 0
    
    for row in articles:
        article = dict(row)  # Convert Row to dict for .get() access
        # Extract authors from metadata JSON if available
        authors = []
        if article.get("metadata"):
            try:
                import json
                metadata = json.loads(article["metadata"]) if isinstance(article["metadata"], str) else article["metadata"]
                authors = metadata.get("authors", [])
            except:
                pass
        
        article_data = {
            "id": article["article_id"],
            "title": article["title"],
            "abstract": article.get("abstract"),
            "url": article.get("url"),
            "source": article.get("source"),
            "authors": authors,
            "published_date": article.get("published_date"),
            "fetched_date": article.get("fetched_date"),
            "synced_at": datetime.utcnow().isoformat(),
        }
        
        try:
            # Upsert (insert or update)
            supabase.table("articles").upsert(article_data).execute()
            synced += 1
        except Exception as e:
            print(f"  Error syncing article {article['article_id']}: {e}")
            errors += 1
    
    print(f"  Synced {synced} articles, {errors} errors")
    return synced, errors


def sync_predictions(supabase: Client, conn: sqlite3.Connection, target_date: Optional[date] = None, sync_all: bool = False):
    """Sync predictions from local DB to Supabase."""
    cursor = conn.cursor()
    
    if sync_all:
        cursor.execute("""
            SELECT p.* FROM predictions p
            JOIN raw_articles a ON p.article_id = a.article_id
        """)
    elif target_date:
        cursor.execute("""
            SELECT p.* FROM predictions p
            JOIN raw_articles a ON p.article_id = a.article_id
            WHERE DATE(a.fetched_date) = ?
        """, (target_date.isoformat(),))
    else:
        today = date.today().isoformat()
        cursor.execute("""
            SELECT p.* FROM predictions p
            JOIN raw_articles a ON p.article_id = a.article_id
            WHERE DATE(a.fetched_date) = ?
        """, (today,))
    
    predictions = cursor.fetchall()
    print(f"Found {len(predictions)} predictions to sync")
    
    synced = 0
    errors = 0
    
    for row in predictions:
        pred = dict(row)  # Convert Row to dict for .get() access
        pred_data = {
            "article_id": pred["article_id"],
            "predicted_label": pred["predicted_label"],
            "confidence": pred.get("confidence"),
            "model_version": pred.get("classifier_version"),  # Local uses classifier_version
            "created_at": pred.get("prediction_time"),  # Local uses prediction_time
            "synced_at": datetime.utcnow().isoformat(),
        }
        
        try:
            # Upsert on article_id (unique constraint)
            supabase.table("predictions").upsert(
                pred_data, 
                on_conflict="article_id"
            ).execute()
            synced += 1
        except Exception as e:
            print(f"  Error syncing prediction for {pred['article_id']}: {e}")
            errors += 1
    
    print(f"  Synced {synced} predictions, {errors} errors")
    return synced, errors


def sync_summaries(supabase: Client, conn: sqlite3.Connection, target_date: Optional[date] = None, sync_all: bool = False):
    """Sync summaries from local DB to Supabase."""
    cursor = conn.cursor()
    
    if sync_all:
        cursor.execute("""
            SELECT s.* FROM summaries s
            JOIN raw_articles a ON s.article_id = a.article_id
        """)
    elif target_date:
        cursor.execute("""
            SELECT s.* FROM summaries s
            JOIN raw_articles a ON s.article_id = a.article_id
            WHERE DATE(a.fetched_date) = ?
        """, (target_date.isoformat(),))
    else:
        today = date.today().isoformat()
        cursor.execute("""
            SELECT s.* FROM summaries s
            JOIN raw_articles a ON s.article_id = a.article_id
            WHERE DATE(a.fetched_date) = ?
        """, (today,))
    
    summaries = cursor.fetchall()
    print(f"Found {len(summaries)} summaries to sync")
    
    synced = 0
    errors = 0
    
    for row in summaries:
        summary = dict(row)  # Convert Row to dict for .get() access
        # Parse key_takeaways if stored as JSON string
        key_takeaways = summary.get("key_takeaways")
        if isinstance(key_takeaways, str):
            import json
            try:
                key_takeaways = json.loads(key_takeaways)
            except:
                key_takeaways = []
        
        summary_data = {
            "article_id": summary["article_id"],
            "summary_text": summary["summary_text"],
            "summary_type": summary.get("summary_type", "brief"),
            "key_takeaways": key_takeaways or [],
            "model_version": summary.get("summarizer_version"),  # Local uses summarizer_version
            "created_at": summary.get("generation_time"),  # Local uses generation_time
            "synced_at": datetime.utcnow().isoformat(),
        }
        
        try:
            # Upsert on article_id (unique constraint)
            supabase.table("summaries").upsert(
                summary_data,
                on_conflict="article_id"
            ).execute()
            synced += 1
        except Exception as e:
            print(f"  Error syncing summary for {summary['article_id']}: {e}")
            errors += 1
    
    print(f"  Synced {synced} summaries, {errors} errors")
    return synced, errors


def update_daily_stats(supabase: Client, articles_synced: int, target_date: Optional[date] = None):
    """Update the daily stats table."""
    stat_date = target_date or date.today()
    
    try:
        # Check if stats exist for this date
        result = supabase.table("daily_stats").select("*").eq(
            "stat_date", stat_date.isoformat()
        ).execute()
        
        if result.data:
            # Update existing record
            supabase.table("daily_stats").update({
                "articles_synced": articles_synced
            }).eq("stat_date", stat_date.isoformat()).execute()
        else:
            # Insert new record
            supabase.table("daily_stats").insert({
                "stat_date": stat_date.isoformat(),
                "articles_synced": articles_synced
            }).execute()
        
        print(f"  Updated daily stats for {stat_date}")
    except Exception as e:
        print(f"  Error updating daily stats: {e}")


def main():
    parser = argparse.ArgumentParser(description="Sync local database to Supabase")
    parser.add_argument(
        "--date",
        type=str,
        help="Sync articles from specific date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Sync all data (not just today's)"
    )
    parser.add_argument(
        "--days",
        type=int,
        help="Sync articles from last N days"
    )
    args = parser.parse_args()
    
    print("=" * 60)
    print("Pulsed Cloud Sync")
    print("=" * 60)
    
    # Parse target date
    target_date = None
    sync_all = args.all
    
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
            print(f"Syncing data for: {target_date}")
        except ValueError:
            print(f"Invalid date format: {args.date}. Use YYYY-MM-DD")
            sys.exit(1)
    elif args.days:
        # Process multiple days
        dates_to_sync = [date.today() - timedelta(days=i) for i in range(args.days)]
        print(f"Syncing data for last {args.days} days")
    elif sync_all:
        print("Syncing ALL data")
    else:
        target_date = date.today()
        print(f"Syncing data for today: {target_date}")
    
    # Initialize connections
    try:
        supabase = get_supabase_client()
        print("Connected to Supabase")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        sys.exit(1)
    
    try:
        conn = get_local_db_connection()
        print(f"Connected to local database: {LOCAL_DB_PATH}")
    except Exception as e:
        print(f"Error connecting to local database: {e}")
        sys.exit(1)
    
    print("-" * 60)
    
    total_synced = 0
    total_errors = 0
    
    if args.days:
        # Sync multiple days
        for sync_date in dates_to_sync:
            print(f"\n[{sync_date}]")
            
            print("\n1. Syncing Articles...")
            synced, errors = sync_articles(supabase, conn, target_date=sync_date)
            total_synced += synced
            total_errors += errors
            
            print("\n2. Syncing Predictions...")
            synced, errors = sync_predictions(supabase, conn, target_date=sync_date)
            
            print("\n3. Syncing Summaries...")
            synced, errors = sync_summaries(supabase, conn, target_date=sync_date)
    else:
        print("\n1. Syncing Articles...")
        synced, errors = sync_articles(supabase, conn, target_date, sync_all)
        total_synced = synced
        total_errors = errors
        
        print("\n2. Syncing Predictions...")
        sync_predictions(supabase, conn, target_date, sync_all)
        
        print("\n3. Syncing Summaries...")
        sync_summaries(supabase, conn, target_date, sync_all)
        
        print("\n4. Updating Daily Stats...")
        update_daily_stats(supabase, total_synced, target_date)
    
    # Close connection
    conn.close()
    
    print("\n" + "=" * 60)
    print("Sync Complete!")
    print(f"Total articles synced: {total_synced}")
    if total_errors > 0:
        print(f"Errors encountered: {total_errors}")
    print("=" * 60)


if __name__ == "__main__":
    main()
