-- Pulsed Supabase Database Schema
-- Run this in Supabase SQL Editor to set up the database

-- ============================================
-- CORE TABLES
-- ============================================

-- Subscribers table
CREATE TABLE IF NOT EXISTS subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    name TEXT,
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'active', 'unsubscribed', 'bounced')),
    digest_frequency TEXT DEFAULT 'daily' CHECK (digest_frequency IN ('daily', 'weekly')),
    preferences JSONB DEFAULT '{"categories": ["important", "worth_reading"]}',
    confirmation_token UUID DEFAULT gen_random_uuid(),
    confirmed_at TIMESTAMPTZ,
    unsubscribed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for email lookups
CREATE INDEX IF NOT EXISTS idx_subscribers_email ON subscribers(email);
CREATE INDEX IF NOT EXISTS idx_subscribers_status ON subscribers(status);

-- Articles synced from local database
CREATE TABLE IF NOT EXISTS articles (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    abstract TEXT,
    url TEXT,
    source TEXT,
    authors TEXT[],
    published_date TIMESTAMPTZ,
    fetched_date TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_articles_published ON articles(published_date DESC);
CREATE INDEX IF NOT EXISTS idx_articles_source ON articles(source);

-- Predictions synced from local classifier
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
    predicted_label TEXT NOT NULL,
    confidence FLOAT,
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id)
);

CREATE INDEX IF NOT EXISTS idx_predictions_label ON predictions(predicted_label);
CREATE INDEX IF NOT EXISTS idx_predictions_article ON predictions(article_id);

-- Summaries synced from local summarizer
CREATE TABLE IF NOT EXISTS summaries (
    id SERIAL PRIMARY KEY,
    article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
    summary_text TEXT NOT NULL,
    summary_type TEXT DEFAULT 'brief',
    key_takeaways TEXT[],
    model_version TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(article_id)
);

CREATE INDEX IF NOT EXISTS idx_summaries_article ON summaries(article_id);

-- Digest history
CREATE TABLE IF NOT EXISTS digests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    digest_date DATE NOT NULL UNIQUE,
    subject TEXT NOT NULL,
    html_content TEXT,
    article_ids TEXT[],
    total_recipients INTEGER DEFAULT 0,
    successful_sends INTEGER DEFAULT 0,
    failed_sends INTEGER DEFAULT 0,
    sent_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_digests_date ON digests(digest_date DESC);

-- ============================================
-- ANALYTICS TABLES
-- ============================================

-- Analytics events for tracking user interactions
CREATE TABLE IF NOT EXISTS analytics_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL CHECK (event_type IN (
        'page_view',
        'subscribe',
        'confirm_subscription',
        'unsubscribe',
        'email_sent',
        'email_open',
        'email_click',
        'feedback_submitted'
    )),
    subscriber_id UUID REFERENCES subscribers(id) ON DELETE SET NULL,
    digest_id UUID REFERENCES digests(id) ON DELETE SET NULL,
    article_id TEXT REFERENCES articles(id) ON DELETE SET NULL,
    metadata JSONB DEFAULT '{}',
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_analytics_type ON analytics_events(event_type);
CREATE INDEX IF NOT EXISTS idx_analytics_subscriber ON analytics_events(subscriber_id);
CREATE INDEX IF NOT EXISTS idx_analytics_created ON analytics_events(created_at DESC);

-- Daily analytics summary (for fast dashboard loading)
CREATE TABLE IF NOT EXISTS daily_stats (
    id SERIAL PRIMARY KEY,
    stat_date DATE NOT NULL UNIQUE,
    page_views INTEGER DEFAULT 0,
    new_subscribers INTEGER DEFAULT 0,
    unsubscribes INTEGER DEFAULT 0,
    emails_sent INTEGER DEFAULT 0,
    emails_opened INTEGER DEFAULT 0,
    email_clicks INTEGER DEFAULT 0,
    articles_synced INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_daily_stats_date ON daily_stats(stat_date DESC);

-- Subscriber feedback on articles
CREATE TABLE IF NOT EXISTS subscriber_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID REFERENCES subscribers(id) ON DELETE CASCADE,
    article_id TEXT REFERENCES articles(id) ON DELETE CASCADE,
    digest_id UUID REFERENCES digests(id) ON DELETE SET NULL,
    rating TEXT NOT NULL CHECK (rating IN ('useful', 'not_useful', 'already_knew')),
    comment TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(subscriber_id, article_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_article ON subscriber_feedback(article_id);
CREATE INDEX IF NOT EXISTS idx_feedback_rating ON subscriber_feedback(rating);

-- ============================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================

-- Enable RLS on all tables
ALTER TABLE subscribers ENABLE ROW LEVEL SECURITY;
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE summaries ENABLE ROW LEVEL SECURITY;
ALTER TABLE digests ENABLE ROW LEVEL SECURITY;
ALTER TABLE analytics_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE subscriber_feedback ENABLE ROW LEVEL SECURITY;

-- Public policies (for subscriber-facing features)
-- Anyone can subscribe (insert into subscribers)
CREATE POLICY "Anyone can subscribe" ON subscribers
    FOR INSERT WITH CHECK (true);

-- Subscribers can view their own data
CREATE POLICY "Subscribers can view own data" ON subscribers
    FOR SELECT USING (
        confirmation_token::text = current_setting('request.headers', true)::json->>'x-confirmation-token'
        OR auth.uid() IS NOT NULL
    );

-- Public can read articles (for digest preview)
CREATE POLICY "Public can read articles" ON articles
    FOR SELECT USING (true);

-- Public can read predictions (for showing categories)
CREATE POLICY "Public can read predictions" ON predictions
    FOR SELECT USING (true);

-- Public can read summaries (for digest display)
CREATE POLICY "Public can read summaries" ON summaries
    FOR SELECT USING (true);

-- Admin policies (for sync scripts and dashboard)
-- Service role can do everything (used by sync scripts)
CREATE POLICY "Service role has full access to subscribers" ON subscribers
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to articles" ON articles
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to predictions" ON predictions
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to summaries" ON summaries
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to digests" ON digests
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to analytics" ON analytics_events
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to daily_stats" ON daily_stats
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role has full access to feedback" ON subscriber_feedback
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- FUNCTIONS
-- ============================================

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger for subscribers updated_at
CREATE TRIGGER subscribers_updated_at
    BEFORE UPDATE ON subscribers
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at();

-- Function to confirm a subscription
CREATE OR REPLACE FUNCTION confirm_subscription(token UUID)
RETURNS JSON AS $$
DECLARE
    sub_record subscribers%ROWTYPE;
BEGIN
    UPDATE subscribers 
    SET status = 'active', confirmed_at = NOW()
    WHERE confirmation_token = token AND status = 'pending'
    RETURNING * INTO sub_record;
    
    IF sub_record.id IS NULL THEN
        RETURN json_build_object('success', false, 'error', 'Invalid or expired token');
    END IF;
    
    -- Log the confirmation event
    INSERT INTO analytics_events (event_type, subscriber_id)
    VALUES ('confirm_subscription', sub_record.id);
    
    RETURN json_build_object('success', true, 'email', sub_record.email);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to unsubscribe
CREATE OR REPLACE FUNCTION unsubscribe(token UUID)
RETURNS JSON AS $$
DECLARE
    sub_record subscribers%ROWTYPE;
BEGIN
    UPDATE subscribers 
    SET status = 'unsubscribed', unsubscribed_at = NOW()
    WHERE confirmation_token = token
    RETURNING * INTO sub_record;
    
    IF sub_record.id IS NULL THEN
        RETURN json_build_object('success', false, 'error', 'Invalid token');
    END IF;
    
    -- Log the unsubscribe event
    INSERT INTO analytics_events (event_type, subscriber_id)
    VALUES ('unsubscribe', sub_record.id);
    
    RETURN json_build_object('success', true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get today's articles for digest
CREATE OR REPLACE FUNCTION get_todays_digest_articles()
RETURNS TABLE (
    article_id TEXT,
    title TEXT,
    abstract TEXT,
    url TEXT,
    source TEXT,
    predicted_label TEXT,
    confidence FLOAT,
    summary_text TEXT,
    key_takeaways TEXT[]
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id as article_id,
        a.title,
        a.abstract,
        a.url,
        a.source,
        p.predicted_label,
        p.confidence,
        s.summary_text,
        s.key_takeaways
    FROM articles a
    LEFT JOIN predictions p ON a.id = p.article_id
    LEFT JOIN summaries s ON a.id = s.article_id
    WHERE DATE(a.synced_at) = CURRENT_DATE
    AND p.predicted_label IN ('important', 'worth_reading')
    ORDER BY 
        CASE p.predicted_label 
            WHEN 'important' THEN 1 
            WHEN 'worth_reading' THEN 2 
            ELSE 3 
        END,
        p.confidence DESC;
END;
$$ LANGUAGE plpgsql;

-- Function to get admin statistics
CREATE OR REPLACE FUNCTION get_admin_stats()
RETURNS JSON AS $$
DECLARE
    result JSON;
BEGIN
    SELECT json_build_object(
        'total_subscribers', (SELECT COUNT(*) FROM subscribers WHERE status = 'active'),
        'pending_subscribers', (SELECT COUNT(*) FROM subscribers WHERE status = 'pending'),
        'total_articles', (SELECT COUNT(*) FROM articles),
        'articles_today', (SELECT COUNT(*) FROM articles WHERE DATE(synced_at) = CURRENT_DATE),
        'digests_sent', (SELECT COUNT(*) FROM digests WHERE sent_at IS NOT NULL),
        'total_email_opens', (SELECT COUNT(*) FROM analytics_events WHERE event_type = 'email_open'),
        'subscribers_this_week', (SELECT COUNT(*) FROM subscribers WHERE created_at > NOW() - INTERVAL '7 days'),
        'open_rate', (
            SELECT ROUND(
                COALESCE(
                    (SELECT COUNT(*)::numeric FROM analytics_events WHERE event_type = 'email_open') /
                    NULLIF((SELECT COUNT(*)::numeric FROM analytics_events WHERE event_type = 'email_sent'), 0) * 100,
                    0
                ), 2
            )
        )
    ) INTO result;
    
    RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to track page view
CREATE OR REPLACE FUNCTION track_page_view(page_path TEXT, user_ip INET DEFAULT NULL, user_agent_str TEXT DEFAULT NULL)
RETURNS VOID AS $$
BEGIN
    INSERT INTO analytics_events (event_type, metadata, ip_address, user_agent)
    VALUES ('page_view', json_build_object('path', page_path), user_ip, user_agent_str);
    
    -- Update daily stats
    INSERT INTO daily_stats (stat_date, page_views)
    VALUES (CURRENT_DATE, 1)
    ON CONFLICT (stat_date) 
    DO UPDATE SET page_views = daily_stats.page_views + 1;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================
-- SAMPLE DATA FOR TESTING (Optional)
-- ============================================

-- Uncomment to insert sample data for testing
/*
INSERT INTO articles (id, title, abstract, url, source, published_date, fetched_date)
VALUES 
    ('sample-1', 'Sample ML Article', 'This is a sample article about machine learning.', 'https://example.com/1', 'arxiv', NOW(), NOW()),
    ('sample-2', 'Another AI Paper', 'Deep learning breakthrough announced.', 'https://example.com/2', 'arxiv', NOW(), NOW());

INSERT INTO predictions (article_id, predicted_label, confidence, model_version)
VALUES 
    ('sample-1', 'important', 0.95, 'v1.0'),
    ('sample-2', 'worth_reading', 0.82, 'v1.0');

INSERT INTO summaries (article_id, summary_text, key_takeaways, model_version)
VALUES 
    ('sample-1', 'A breakthrough in machine learning using novel attention mechanisms.', ARRAY['New attention mechanism', 'Better performance'], 'v1.0'),
    ('sample-2', 'Researchers achieve state-of-the-art results in image recognition.', ARRAY['State-of-the-art results', 'Image recognition'], 'v1.0');
*/
