// Supabase Edge Function: send-digest
// Deploy with: supabase functions deploy send-digest
//
// This function sends the daily/weekly digest emails to subscribers.
// Schedule it with Supabase's cron jobs feature.

import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const RESEND_API_KEY = Deno.env.get("RESEND_API_KEY")
const SUPABASE_URL = Deno.env.get("SUPABASE_URL")
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")
const FROM_EMAIL = Deno.env.get("FROM_EMAIL") || "digest@pulsed.dev"
const SITE_URL = Deno.env.get("SITE_URL") || "https://pulsed.vercel.app"

interface Article {
  article_id: string
  title: string
  abstract: string
  url: string
  source: string
  predicted_label: string
  confidence: number
  summary_text: string
  key_takeaways: string[]
}

interface Subscriber {
  id: string
  email: string
  name: string | null
  digest_frequency: "daily" | "weekly"
  confirmation_token: string
}

serve(async (req: Request) => {
  try {
    // Verify request (optional: add secret header check)
    const { frequency = "daily" } = await req.json().catch(() => ({}))

    console.log(`Starting ${frequency} digest send...`)

    // Initialize Supabase client with service role
    const supabase = createClient(SUPABASE_URL!, SUPABASE_SERVICE_ROLE_KEY!)

    // Get today's articles
    const { data: articles, error: articlesError } = await supabase
      .rpc("get_todays_digest_articles")

    if (articlesError) {
      console.error("Error fetching articles:", articlesError)
      throw articlesError
    }

    if (!articles || articles.length === 0) {
      console.log("No articles to send today")
      return new Response(JSON.stringify({ message: "No articles to send" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      })
    }

    console.log(`Found ${articles.length} articles for digest`)

    // Get active subscribers for this frequency
    const { data: subscribers, error: subscribersError } = await supabase
      .from("subscribers")
      .select("id, email, name, digest_frequency, confirmation_token")
      .eq("status", "active")
      .eq("digest_frequency", frequency)

    if (subscribersError) {
      console.error("Error fetching subscribers:", subscribersError)
      throw subscribersError
    }

    if (!subscribers || subscribers.length === 0) {
      console.log("No subscribers for this frequency")
      return new Response(
        JSON.stringify({ message: "No subscribers to send to" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      )
    }

    console.log(`Sending to ${subscribers.length} subscribers`)

    // Create digest record
    const today = new Date().toISOString().split("T")[0]
    const { data: digest, error: digestError } = await supabase
      .from("digests")
      .insert({
        digest_date: today,
        subject: `Pulsed Daily Digest - ${formatDate(new Date())}`,
        article_ids: articles.map((a: Article) => a.article_id),
        total_recipients: subscribers.length,
      })
      .select()
      .single()

    if (digestError && digestError.code !== "23505") {
      // Ignore duplicate error
      console.error("Error creating digest:", digestError)
    }

    // Send emails via Resend
    let successful = 0
    let failed = 0

    for (const subscriber of subscribers) {
      try {
        // Generate HTML email with subscriber ID for feedback tracking
        const htmlContent = generateEmailHTML(articles, today, subscriber.id)
        
        const unsubscribeUrl = `${SITE_URL}/unsubscribe?token=${subscriber.confirmation_token}`
        const personalizedHtml = htmlContent.replace(
          "{{UNSUBSCRIBE_URL}}",
          unsubscribeUrl
        )

        const res = await fetch("https://api.resend.com/emails", {
          method: "POST",
          headers: {
            Authorization: `Bearer ${RESEND_API_KEY}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            from: FROM_EMAIL,
            to: subscriber.email,
            subject: `Pulsed Daily Digest - ${formatDate(new Date())}`,
            html: personalizedHtml,
          }),
        })

        if (res.ok) {
          successful++
          // Track email sent event
          await supabase.from("analytics_events").insert({
            event_type: "email_sent",
            subscriber_id: subscriber.id,
            digest_id: digest?.id,
          })
        } else {
          const error = await res.text()
          console.error(`Failed to send to ${subscriber.email}:`, error)
          failed++
        }
      } catch (error) {
        console.error(`Error sending to ${subscriber.email}:`, error)
        failed++
      }
    }

    // Update digest with send results
    if (digest) {
      await supabase
        .from("digests")
        .update({
          sent_at: new Date().toISOString(),
          successful_sends: successful,
          failed_sends: failed,
        })
        .eq("id", digest.id)
    }

    // Update daily stats
    await supabase
      .from("daily_stats")
      .upsert(
        {
          stat_date: today,
          emails_sent: successful,
        },
        { onConflict: "stat_date" }
      )

    console.log(`Digest sent: ${successful} success, ${failed} failed`)

    return new Response(
      JSON.stringify({
        message: "Digest sent successfully",
        successful,
        failed,
        total_articles: articles.length,
      }),
      { status: 200, headers: { "Content-Type": "application/json" } }
    )
  } catch (error) {
    console.error("Error in send-digest:", error)
    return new Response(
      JSON.stringify({ 
        error: error instanceof Error ? error.message : "Failed to send digest" 
      }), 
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      }
    )
  }
})

function formatDate(date: Date): string {
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    year: "numeric",
    month: "long",
    day: "numeric",
  })
}

function generateEmailHTML(
  articles: Article[], 
  dateStr: string, 
  subscriberId?: string
): string {
  const date = new Date(dateStr)

  const articleSections = articles
    .map(
      (article, index) => `
    <tr>
      <td style="padding: 24px 0; border-bottom: 1px solid #E5E7EB;">
        <table cellpadding="0" cellspacing="0" width="100%">
          <tr>
            <td width="40" valign="top">
              <div style="width: 32px; height: 32px; background-color: #DBEAFE; border-radius: 50%; text-align: center; line-height: 32px; color: #2563EB; font-weight: bold;">
                ${index + 1}
              </div>
            </td>
            <td style="padding-left: 16px;">
              <div style="margin-bottom: 8px;">
                <span style="display: inline-block; padding: 4px 12px; background-color: ${
                  article.predicted_label === "important"
                    ? "#FEE2E2"
                    : "#DBEAFE"
                }; color: ${
        article.predicted_label === "important" ? "#991B1B" : "#1E40AF"
      }; border-radius: 9999px; font-size: 12px; font-weight: 500;">
                  ${
                    article.predicted_label === "important"
                      ? "Important"
                      : "Worth Reading"
                  }
                </span>
                <span style="margin-left: 8px; color: #9CA3AF; font-size: 12px;">
                  ${article.source}
                </span>
              </div>
              <a href="${
                article.url
              }" style="color: #1F2937; font-size: 18px; font-weight: 600; text-decoration: none; line-height: 1.4;">
                ${article.title}
              </a>
              <p style="color: #6B7280; font-size: 14px; line-height: 1.6; margin-top: 12px;">
                ${article.summary_text || article.abstract || ""}
              </p>
              ${
                article.key_takeaways && article.key_takeaways.length > 0
                  ? `
                <div style="background-color: #F9FAFB; padding: 12px; border-radius: 8px; margin-top: 12px;">
                  <p style="margin: 0 0 8px 0; font-size: 11px; font-weight: 600; text-transform: uppercase; color: #6B7280;">Key Takeaways</p>
                  ${article.key_takeaways
                    .map(
                      (t) =>
                        `<p style="margin: 4px 0; font-size: 13px; color: #374151;">• ${t}</p>`
                    )
                    .join("")}
                </div>
              `
                  : ""
              }
              <div style="margin-top: 16px; padding-top: 12px; border-top: 1px solid #F3F4F6;">
                <p style="margin: 0 0 8px 0; font-size: 11px; color: #9CA3AF; font-weight: 600;">Was this article relevant?</p>
                <a href="${SITE_URL}/api/feedback/article?article_id=${encodeURIComponent(article.article_id)}&rating=useful&subscriber_id=${subscriberId || ''}" 
                   style="display: inline-block; margin-right: 8px; margin-bottom: 8px; padding: 6px 12px; background-color: #10B981; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">
                  👍 Useful
                </a>
                <a href="${SITE_URL}/api/feedback/article?article_id=${encodeURIComponent(article.article_id)}&rating=not_useful&subscriber_id=${subscriberId || ''}" 
                   style="display: inline-block; margin-right: 8px; margin-bottom: 8px; padding: 6px 12px; background-color: #EF4444; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">
                  👎 Not Useful
                </a>
                <a href="${SITE_URL}/api/feedback/article?article_id=${encodeURIComponent(article.article_id)}&rating=already_knew&subscriber_id=${subscriberId || ''}" 
                   style="display: inline-block; margin-bottom: 8px; padding: 6px 12px; background-color: #F59E0B; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">
                  📚 Already Knew
                </a>
                
                <p style="margin: 12px 0 8px 0; font-size: 11px; color: #9CA3AF; font-weight: 600;">How was the summary?</p>
                <a href="${SITE_URL}/api/feedback/article?article_id=${encodeURIComponent(article.article_id)}&summary_rating=good&subscriber_id=${subscriberId || ''}" 
                   style="display: inline-block; margin-right: 8px; padding: 6px 12px; background-color: #8B5CF6; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">
                  ✨ Good Summary
                </a>
                <a href="${SITE_URL}/api/feedback/article?article_id=${encodeURIComponent(article.article_id)}&summary_rating=poor&subscriber_id=${subscriberId || ''}" 
                   style="display: inline-block; padding: 6px 12px; background-color: #6B7280; color: white; text-decoration: none; border-radius: 6px; font-size: 12px;">
                  ❌ Poor Summary
                </a>
              </div>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  `
    )
    .join("")

  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Pulsed Daily Digest</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F3F4F6; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;">
  <table cellpadding="0" cellspacing="0" width="100%" style="max-width: 600px; margin: 0 auto;">
    <!-- Header -->
    <tr>
      <td style="background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); padding: 32px 24px; text-align: center;">
        <h1 style="margin: 0; color: white; font-size: 28px; font-weight: bold;">Pulsed</h1>
        <p style="margin: 8px 0 0 0; color: #BFDBFE; font-size: 16px;">AI & ML Daily Digest</p>
        <p style="margin: 4px 0 0 0; color: #93C5FD; font-size: 14px;">${formatDate(
          date
        )}</p>
      </td>
    </tr>
    
    <!-- Articles Count -->
    <tr>
      <td style="background-color: white; padding: 16px 24px; text-align: center; border-bottom: 1px solid #E5E7EB;">
        <p style="margin: 0; color: #6B7280; font-size: 14px;">
          Today's digest contains <strong style="color: #1F2937;">${
            articles.length
          } articles</strong>
        </p>
      </td>
    </tr>
    
    <!-- Articles -->
    <tr>
      <td style="background-color: white; padding: 0 24px;">
        <table cellpadding="0" cellspacing="0" width="100%">
          ${articleSections}
        </table>
      </td>
    </tr>
    
    <!-- Footer -->
    <tr>
      <td style="background-color: #F9FAFB; padding: 24px; text-align: center; border-top: 1px solid #E5E7EB;">
        <p style="margin: 0 0 8px 0; color: #6B7280; font-size: 12px;">
          You're receiving this because you subscribed to Pulsed.
        </p>
        <a href="{{UNSUBSCRIBE_URL}}" style="color: #3B82F6; font-size: 12px; text-decoration: none;">
          Unsubscribe
        </a>
        <p style="margin: 16px 0 0 0; color: #9CA3AF; font-size: 11px;">
          © ${new Date().getFullYear()} Pulsed. All rights reserved.
        </p>
      </td>
    </tr>
  </table>
</body>
</html>
  `
}
