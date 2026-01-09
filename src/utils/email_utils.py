"""Email utilities for sending digests."""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List, Dict, Any
from datetime import datetime

from jinja2 import Template
from loguru import logger

from .config import config


# HTML email template for digest
DIGEST_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            background-color: white;
            border-radius: 8px;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .header {
            text-align: center;
            margin-bottom: 30px;
            border-bottom: 2px solid #eee;
            padding-bottom: 20px;
        }
        .header h1 {
            color: #667eea;
            margin: 0;
            font-size: 28px;
        }
        .header .date {
            color: #666;
            font-size: 14px;
            margin-top: 5px;
        }
        .section {
            margin-bottom: 30px;
        }
        .section-header {
            display: flex;
            align-items: center;
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #eee;
        }
        .section-header .emoji {
            font-size: 24px;
            margin-right: 10px;
        }
        .section-header h2 {
            margin: 0;
            font-size: 20px;
            color: #333;
        }
        .article {
            background-color: #fafafa;
            border-radius: 6px;
            padding: 20px;
            margin-bottom: 15px;
            border-left: 4px solid #667eea;
        }
        .article.worth-learning {
            border-left-color: #f59e0b;
        }
        .article.important {
            border-left-color: #10b981;
        }
        .article-title {
            font-size: 18px;
            font-weight: 600;
            color: #1a1a1a;
            text-decoration: none;
            margin-bottom: 10px;
            display: block;
        }
        .article-title:hover {
            color: #667eea;
        }
        .article-meta {
            font-size: 12px;
            color: #888;
            margin-bottom: 10px;
        }
        .article-summary {
            color: #444;
            margin-bottom: 15px;
        }
        .key-takeaways {
            background-color: #fff8e6;
            border-radius: 4px;
            padding: 12px;
            margin-top: 10px;
        }
        .key-takeaways h4 {
            margin: 0 0 8px 0;
            font-size: 14px;
            color: #b45309;
        }
        .key-takeaways ul {
            margin: 0;
            padding-left: 20px;
        }
        .key-takeaways li {
            color: #444;
            font-size: 14px;
            margin-bottom: 5px;
        }
        .feedback-buttons {
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid #eee;
        }
        .feedback-buttons a {
            display: inline-block;
            padding: 6px 12px;
            margin-right: 8px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 12px;
            transition: background-color 0.2s;
        }
        .btn-good {
            background-color: #d1fae5;
            color: #065f46;
        }
        .btn-good:hover {
            background-color: #a7f3d0;
        }
        .btn-bad {
            background-color: #fee2e2;
            color: #991b1b;
        }
        .btn-bad:hover {
            background-color: #fecaca;
        }
        .btn-wrong {
            background-color: #e0e7ff;
            color: #3730a3;
        }
        .btn-wrong:hover {
            background-color: #c7d2fe;
        }
        .read-time {
            font-size: 12px;
            color: #666;
            background-color: #f3f4f6;
            padding: 2px 8px;
            border-radius: 12px;
            margin-left: 10px;
        }
        .stats {
            background-color: #f0f4ff;
            border-radius: 6px;
            padding: 15px;
            margin-top: 30px;
            text-align: center;
        }
        .stats h3 {
            margin: 0 0 10px 0;
            color: #4f46e5;
            font-size: 16px;
        }
        .stats p {
            margin: 5px 0;
            color: #666;
            font-size: 14px;
        }
        .footer {
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #888;
            font-size: 12px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚡ Pulsed Daily Digest</h1>
            <div class="date">{{ date }}</div>
        </div>
        
        {% if worth_learning %}
        <div class="section">
            <div class="section-header">
                <span class="emoji">🔥</span>
                <h2>Worth Learning ({{ worth_learning|length }} articles)</h2>
            </div>
            {% for article in worth_learning %}
            <div class="article worth-learning">
                <a href="{{ article.url }}" class="article-title" target="_blank">
                    {{ article.title }}
                    {% if article.estimated_read_time %}
                    <span class="read-time">{{ article.estimated_read_time }} min read</span>
                    {% endif %}
                </a>
                <div class="article-meta">
                    {{ article.source }} • {{ article.published_date or 'Recent' }}
                </div>
                <div class="article-summary">
                    {{ article.summary_text or article.abstract or 'No summary available.' }}
                </div>
                {% if article.key_takeaways %}
                <div class="key-takeaways">
                    <h4>Key Takeaways</h4>
                    <ul>
                        {% for takeaway in article.key_takeaways %}
                        <li>{{ takeaway }}</li>
                        {% endfor %}
                    </ul>
                </div>
                {% endif %}
                <div class="feedback-buttons">
                    <a href="{{ feedback_base_url }}/feedback/summary?article_id={{ article.article_id }}&rating=good" class="btn-good">👍 Good summary</a>
                    <a href="{{ feedback_base_url }}/feedback/summary?article_id={{ article.article_id }}&rating=bad" class="btn-bad">👎 Bad summary</a>
                    <a href="{{ feedback_base_url }}/feedback/classification?article_id={{ article.article_id }}&label=important" class="btn-wrong">Should be Important</a>
                    <a href="{{ feedback_base_url }}/feedback/classification?article_id={{ article.article_id }}&label=garbage" class="btn-wrong">Should be Garbage</a>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if important %}
        <div class="section">
            <div class="section-header">
                <span class="emoji">⚠️</span>
                <h2>Important ({{ important|length }} articles)</h2>
            </div>
            {% for article in important %}
            <div class="article important">
                <a href="{{ article.url }}" class="article-title" target="_blank">
                    {{ article.title }}
                    {% if article.estimated_read_time %}
                    <span class="read-time">{{ article.estimated_read_time }} min read</span>
                    {% endif %}
                </a>
                <div class="article-meta">
                    {{ article.source }} • {{ article.published_date or 'Recent' }}
                </div>
                <div class="article-summary">
                    {{ article.summary_text or article.abstract or 'No summary available.' }}
                </div>
                <div class="feedback-buttons">
                    <a href="{{ feedback_base_url }}/feedback/summary?article_id={{ article.article_id }}&rating=good" class="btn-good">👍 Good</a>
                    <a href="{{ feedback_base_url }}/feedback/summary?article_id={{ article.article_id }}&rating=bad" class="btn-bad">👎 Bad</a>
                    <a href="{{ feedback_base_url }}/feedback/classification?article_id={{ article.article_id }}&label=worth_learning" class="btn-wrong">Worth Learning</a>
                    <a href="{{ feedback_base_url }}/feedback/classification?article_id={{ article.article_id }}&label=garbage" class="btn-wrong">Garbage</a>
                </div>
            </div>
            {% endfor %}
        </div>
        {% endif %}
        
        {% if not worth_learning and not important %}
        <div class="section">
            <p style="text-align: center; color: #666;">No articles to show today. Check back tomorrow!</p>
        </div>
        {% endif %}
        
        {% if stats %}
        <div class="stats">
            <h3>📊 Today's Stats</h3>
            <p>Total articles processed: {{ stats.total }}</p>
            <p>Filtered out: {{ stats.garbage }} ({{ stats.garbage_pct }}%)</p>
            {% if stats.trend %}
            <p>{{ stats.trend }}</p>
            {% endif %}
        </div>
        {% endif %}
        
        <div class="footer">
            <p>Pulsed - AI/ML News Filter</p>
            <p>Your feedback helps improve our recommendations!</p>
        </div>
    </div>
</body>
</html>
"""


class EmailSender:
    """Email sender for digest delivery."""
    
    def __init__(self):
        self.sender = config.email.sender
        self.password = config.email.password
        self.recipient = config.email.recipient
        self.smtp_server = config.email.smtp_server
        self.smtp_port = config.email.smtp_port
        self.template = Template(DIGEST_TEMPLATE)
    
    def _parse_key_takeaways(self, takeaways_str: Optional[str]) -> List[str]:
        """Parse key takeaways from JSON string."""
        if not takeaways_str:
            return []
        try:
            import json
            return json.loads(takeaways_str)
        except:
            return []
    
    def generate_digest_html(
        self,
        worth_learning: List[Dict[str, Any]],
        important: List[Dict[str, Any]],
        stats: Optional[Dict[str, Any]] = None,
        feedback_base_url: str = "http://localhost:8000",
    ) -> str:
        """Generate the HTML content for the digest email."""
        # Process key takeaways for worth_learning articles
        for article in worth_learning:
            if isinstance(article.get("key_takeaways"), str):
                article["key_takeaways"] = self._parse_key_takeaways(article["key_takeaways"])
        
        return self.template.render(
            date=datetime.now().strftime("%B %d, %Y"),
            worth_learning=worth_learning,
            important=important,
            stats=stats,
            feedback_base_url=feedback_base_url,
        )
    
    def send_digest(
        self,
        worth_learning: List[Dict[str, Any]],
        important: List[Dict[str, Any]],
        stats: Optional[Dict[str, Any]] = None,
        feedback_base_url: str = "http://localhost:8000",
    ) -> bool:
        """Send the daily digest email."""
        if not self.sender or not self.password:
            logger.warning("Email credentials not configured, skipping digest send")
            return False
        
        try:
            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"⚡ Pulsed Daily Digest - {datetime.now().strftime('%B %d, %Y')}"
            msg["From"] = self.sender
            msg["To"] = self.recipient
            
            # Generate HTML content
            html_content = self.generate_digest_html(
                worth_learning=worth_learning,
                important=important,
                stats=stats,
                feedback_base_url=feedback_base_url,
            )
            
            # Create plain text fallback
            text_content = f"""
Pulsed Daily Digest - {datetime.now().strftime('%B %d, %Y')}

Worth Learning ({len(worth_learning)} articles):
{chr(10).join(f'- {a["title"]}: {a.get("url", "")}' for a in worth_learning)}

Important ({len(important)} articles):
{chr(10).join(f'- {a["title"]}: {a.get("url", "")}' for a in important)}
            """
            
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipient, msg.as_string())
            
            logger.info(f"Digest sent to {self.recipient}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send digest: {e}")
            return False
    
    def send_test_email(self) -> bool:
        """Send a test email to verify configuration."""
        try:
            msg = MIMEText("This is a test email from Pulsed.")
            msg["Subject"] = "Pulsed Test Email"
            msg["From"] = self.sender
            msg["To"] = self.recipient
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender, self.password)
                server.sendmail(self.sender, self.recipient, msg.as_string())
            
            logger.info("Test email sent successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to send test email: {e}")
            return False
