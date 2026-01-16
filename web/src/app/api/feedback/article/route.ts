import { NextRequest, NextResponse } from 'next/server'
import { supabase } from '@/lib/supabase'

/**
 * Submit article feedback (thumbs up/down on articles in digest)
 * 
 * GET /api/feedback/article?article_id=xxx&rating=useful&subscriber_id=xxx
 */
export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url)
    const article_id = searchParams.get('article_id')
    const rating = searchParams.get('rating')
    const summary_rating = searchParams.get('summary_rating')
    const subscriber_id = searchParams.get('subscriber_id')

    if (!article_id) {
      return NextResponse.json(
        { error: 'Missing article_id' },
        { status: 400 }
      )
    }

    if (!rating && !summary_rating) {
      return NextResponse.json(
        { error: 'Must provide either rating or summary_rating' },
        { status: 400 }
      )
    }

    // Validate ratings
    if (rating) {
      const validRatings = ['useful', 'not_useful', 'already_knew']
      if (!validRatings.includes(rating)) {
        return NextResponse.json(
          { error: 'Invalid rating. Must be: useful, not_useful, or already_knew' },
          { status: 400 }
        )
      }
    }

    if (summary_rating) {
      const validSummaryRatings = ['good', 'poor']
      if (!validSummaryRatings.includes(summary_rating)) {
        return NextResponse.json(
          { error: 'Invalid summary_rating. Must be: good or poor' },
          { status: 400 }
        )
      }
    }

    // Build feedback object
    const feedbackData: any = {
      subscriber_id: subscriber_id || null,
      article_id,
    }

    if (rating) {
      feedbackData.rating = rating
    }

    if (summary_rating) {
      feedbackData.summary_rating = summary_rating
    }

    // Insert or update feedback
    const { error } = await supabase
      .from('subscriber_feedback')
      .upsert(feedbackData, {
        onConflict: 'subscriber_id,article_id',
        ignoreDuplicates: false,
      })

    if (error) throw error

    // Track analytics event
    await supabase.from('analytics_events').insert({
      event_type: 'feedback_submitted',
      subscriber_id: subscriber_id || null,
      article_id,
      metadata: { rating, summary_rating },
    })

    // Return HTML response for browser
    return new NextResponse(
      `
      <!DOCTYPE html>
      <html>
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>Feedback Received</title>
        <style>
          body {
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3a8a 0%, #3b82f6 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .container {
            background: white;
            border-radius: 12px;
            padding: 40px;
            max-width: 400px;
            text-align: center;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
          }
          .icon {
            width: 64px;
            height: 64px;
            margin: 0 auto 20px;
            background: #10b981;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
          }
          .checkmark {
            color: white;
            font-size: 32px;
          }
          h1 {
            color: #1f2937;
            font-size: 24px;
            margin: 0 0 12px 0;
          }
          p {
            color: #6b7280;
            font-size: 16px;
            line-height: 1.5;
            margin: 0;
          }
          .close-link {
            margin-top: 24px;
            color: #3b82f6;
            text-decoration: none;
            font-size: 14px;
          }
        </style>
      </head>
      <body>
        <div class="container">
          <div class="icon">
            <span class="checkmark">✓</span>
          </div>
          <h1>Thank you!</h1>
          <p>Your feedback helps us improve the digest quality.</p>
          <a href="#" class="close-link" onclick="window.close(); return false;">Close this window</a>
        </div>
      </body>
      </html>
      `,
      {
        status: 200,
        headers: { 'Content-Type': 'text/html' },
      }
    )
  } catch (error) {
    console.error('Error submitting feedback:', error)
    return NextResponse.json(
      { error: 'Failed to submit feedback' },
      { status: 500 }
    )
  }
}

/**
 * POST endpoint for structured feedback
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const { article_id, rating, subscriber_id, comment } = body

    if (!article_id || !rating) {
      return NextResponse.json(
        { error: 'Missing article_id or rating' },
        { status: 400 }
      )
    }

    const { error } = await supabase
      .from('subscriber_feedback')
      .upsert({
        subscriber_id: subscriber_id || null,
        article_id,
        rating,
        comment: comment || null,
      }, {
        onConflict: 'subscriber_id,article_id',
      })

    if (error) throw error

    await supabase.from('analytics_events').insert({
      event_type: 'feedback_submitted',
      subscriber_id: subscriber_id || null,
      article_id,
      metadata: { rating, has_comment: !!comment },
    })

    return NextResponse.json({ success: true })
  } catch (error) {
    console.error('Error submitting feedback:', error)
    return NextResponse.json(
      { error: 'Failed to submit feedback' },
      { status: 500 }
    )
  }
}
