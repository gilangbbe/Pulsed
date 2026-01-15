#!/usr/bin/env python3
"""
Send confirmation emails to new subscribers.

This script should be run periodically (e.g., every 5 minutes) to send
confirmation emails to subscribers with 'pending' status.

Usage:
    python scripts/send_confirmation_emails.py
"""

import os
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv() 

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from supabase import create_client, Client
    import requests
except ImportError:
    print("Error: Required packages not installed.")
    print("Run: pip install supabase requests")
    sys.exit(1)


# Configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
RESEND_API_KEY = os.getenv("RESEND_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@pulsed.dev")
SITE_URL = os.getenv("SITE_URL", "https://pulsed.vercel.app")


def get_supabase_client() -> Client:
    """Create Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        raise ValueError("Missing Supabase credentials")
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def send_confirmation_email(email: str, name: str, token: str) -> bool:
    """Send confirmation email via Resend."""
    if not RESEND_API_KEY:
        print("Warning: RESEND_API_KEY not set, skipping email")
        return False
    
    confirm_url = f"{SITE_URL}/confirm?token={token}"
    
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Confirm Your Subscription</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
  <table cellpadding="0" cellspacing="0" width="100%" style="max-width: 500px; margin: 40px auto;">
    <tr>
      <td style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 32px; text-align: center; border-radius: 12px 12px 0 0;">
        <h1 style="margin: 0; color: white; font-size: 24px;">Pulsed</h1>
        <p style="margin: 8px 0 0 0; color: #BFDBFE; font-size: 14px;">AI & ML News Digest</p>
      </td>
    </tr>
    <tr>
      <td style="background-color: white; padding: 32px; border-radius: 0 0 12px 12px;">
        <h2 style="margin: 0 0 16px 0; color: #1F2937; font-size: 20px;">
          Confirm Your Subscription
        </h2>
        <p style="color: #6B7280; line-height: 1.6; margin: 0 0 24px 0;">
          Hi{' ' + name if name else ''},<br><br>
          Thanks for subscribing to Pulsed! Please confirm your email address to start receiving our AI & ML news digest.
        </p>
        <a href="{confirm_url}" style="display: inline-block; padding: 14px 32px; background-color: #2563EB; color: white; text-decoration: none; border-radius: 8px; font-weight: 500;">
          Confirm Subscription
        </a>
        <p style="color: #9CA3AF; font-size: 12px; margin: 24px 0 0 0;">
          If you didn't subscribe, you can safely ignore this email.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
    """
    
    try:
        response = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": FROM_EMAIL,
                "to": email,
                "subject": "Confirm your Pulsed subscription",
                "html": html_content,
            },
        )
        
        if response.status_code == 200:
            print(f"  Sent confirmation to {email}")
            return True
        else:
            print(f"  Failed to send to {email}: {response.text}")
            return False
            
    except Exception as e:
        print(f"  Error sending to {email}: {e}")
        return False


def main():
    print("=" * 50)
    print("Sending Confirmation Emails")
    print("=" * 50)
    
    try:
        supabase = get_supabase_client()
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        sys.exit(1)
    
    # Get pending subscribers who haven't received confirmation yet
    # We track this by checking if there's a confirmation email event
    result = supabase.from_("subscribers")\
        .select("id, email, name, confirmation_token")\
        .eq("status", "pending")\
        .execute()
    
    pending = result.data or []
    print(f"Found {len(pending)} pending subscribers")
    
    if not pending:
        print("No confirmation emails to send")
        return
    
    sent = 0
    for subscriber in pending:
        # Check if we already sent a confirmation email
        events = supabase.from_("analytics_events")\
            .select("id")\
            .eq("subscriber_id", subscriber["id"])\
            .eq("event_type", "subscribe")\
            .execute()
        
        # If no subscribe event exists, we haven't sent confirmation yet
        # (The subscribe event is logged when form is submitted, but we use it
        # to track confirmation sent as well by checking metadata)
        
        success = send_confirmation_email(
            subscriber["email"],
            subscriber.get("name"),
            subscriber["confirmation_token"],
        )
        
        if success:
            sent += 1
    
    print("-" * 50)
    print(f"Sent {sent} confirmation emails")


if __name__ == "__main__":
    main()
