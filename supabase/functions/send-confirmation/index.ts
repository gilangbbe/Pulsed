import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2.39.0'

const RESEND_API_KEY = Deno.env.get('RESEND_API_KEY')
const FROM_EMAIL = Deno.env.get('FROM_EMAIL') || 'digest@yourdomain.com'
const SITE_URL = Deno.env.get('SITE_URL') || 'https://your-app.vercel.app'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
const SUPABASE_SERVICE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

interface Subscriber {
  id: string
  email: string
  name?: string
  confirmation_token: string
  status: string
  confirmation_sent_at?: string
  created_at: string
}

serve(async (req: Request) => {
  try {
    // Handle CORS for webhooks
    if (req.method === 'OPTIONS') {
      return new Response('ok', {
        headers: {
          'Access-Control-Allow-Origin': '*',
          'Access-Control-Allow-Methods': 'POST',
          'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
        }
      })
    }

    const { record } = await req.json()
    const subscriber = record as Subscriber

    if (!subscriber || !subscriber.email) {
      throw new Error('Invalid subscriber data')
    }

    // Only send confirmation if status is pending
    if (subscriber.status !== 'pending') {
      return new Response(
        JSON.stringify({ message: 'Skipped - subscriber not pending' }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    }

    // Check if confirmation email already sent (prevent duplicates)
    if (subscriber.confirmation_sent_at) {
      return new Response(
        JSON.stringify({ 
          message: 'Skipped - confirmation already sent',
          sent_at: subscriber.confirmation_sent_at 
        }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    }

    // Additional check: Only send if subscriber was created recently (within last 5 minutes)
    const createdAt = new Date(subscriber.created_at).getTime()
    const now = Date.now()
    const fiveMinutes = 5 * 60 * 1000
    
    if (now - createdAt > fiveMinutes) {
      return new Response(
        JSON.stringify({ 
          message: 'Skipped - subscriber created more than 5 minutes ago',
          created_at: subscriber.created_at
        }),
        { headers: { 'Content-Type': 'application/json' } }
      )
    }

    const confirmationUrl = `${SITE_URL}/confirm?token=${subscriber.confirmation_token}`
    
    const emailHtml = generateConfirmationEmail(
      subscriber.name || subscriber.email,
      confirmationUrl
    )

    // Send email via Resend
    const resendResponse = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${RESEND_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: FROM_EMAIL,
        to: subscriber.email,
        subject: 'Confirm your Pulsed subscription',
        html: emailHtml,
      }),
    })

    if (!resendResponse.ok) {
      const errorText = await resendResponse.text()
      throw new Error(`Resend API error: ${errorText}`)
    }

    const resendData = await resendResponse.json()

    // Mark confirmation as sent in database
    const supabase = createClient(SUPABASE_URL, SUPABASE_SERVICE_KEY)
    await supabase
      .from('subscribers')
      .update({ confirmation_sent_at: new Date().toISOString() })
      .eq('id', subscriber.id)

    return new Response(
      JSON.stringify({ 
        success: true, 
        email: subscriber.email,
        messageId: resendData.id 
      }),
      { 
        headers: { 'Content-Type': 'application/json' },
        status: 200,
      }
    )

  } catch (error) {
    console.error('Error sending confirmation:', error)
    
    return new Response(
      JSON.stringify({ 
        success: false, 
        error: error instanceof Error ? error.message : 'Unknown error' 
      }),
      { 
        headers: { 'Content-Type': 'application/json' },
        status: 500,
      }
    )
  }
})

function generateConfirmationEmail(name: string, confirmationUrl: string): string {
  return `
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Confirm your subscription</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f5f5f5;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 40px 0;">
    <tr>
      <td align="center">
        <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
          
          <!-- Header -->
          <tr>
            <td style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 40px; text-align: center;">
              <h1 style="color: #ffffff; margin: 0; font-size: 32px; font-weight: 700;">
                🔔 Pulsed
              </h1>
              <p style="color: #ffffff; margin: 10px 0 0 0; font-size: 16px; opacity: 0.9;">
                Your Daily ML Digest
              </p>
            </td>
          </tr>
          
          <!-- Body -->
          <tr>
            <td style="padding: 40px 40px 20px 40px;">
              <h2 style="color: #1a202c; margin: 0 0 20px 0; font-size: 24px; font-weight: 600;">
                Hi ${name}! 👋
              </h2>
              <p style="color: #4a5568; margin: 0 0 20px 0; font-size: 16px; line-height: 1.6;">
                Thanks for subscribing to Pulsed! We're excited to deliver the latest and most important ML research directly to your inbox.
              </p>
              <p style="color: #4a5568; margin: 0 0 30px 0; font-size: 16px; line-height: 1.6;">
                To start receiving your daily digest, please confirm your email address by clicking the button below:
              </p>
              
              <!-- CTA Button -->
              <table width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td align="center" style="padding: 0 0 30px 0;">
                    <a href="${confirmationUrl}" 
                       style="display: inline-block; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #ffffff; text-decoration: none; padding: 16px 40px; border-radius: 6px; font-size: 16px; font-weight: 600; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.3);">
                      Confirm Subscription
                    </a>
                  </td>
                </tr>
              </table>
              
              <p style="color: #718096; margin: 0 0 10px 0; font-size: 14px; line-height: 1.6;">
                Or copy and paste this link into your browser:
              </p>
              <p style="color: #667eea; margin: 0 0 30px 0; font-size: 14px; word-break: break-all;">
                ${confirmationUrl}
              </p>
            </td>
          </tr>
          
          <!-- Features -->
          <tr>
            <td style="padding: 0 40px 40px 40px;">
              <div style="background-color: #f7fafc; padding: 20px; border-radius: 6px; border-left: 4px solid #667eea;">
                <p style="color: #1a202c; margin: 0 0 10px 0; font-size: 14px; font-weight: 600;">
                  What you'll get:
                </p>
                <ul style="color: #4a5568; margin: 0; padding-left: 20px; font-size: 14px; line-height: 1.8;">
                  <li>Curated ML papers and research</li>
                  <li>AI-powered summaries and key takeaways</li>
                  <li>Daily or weekly delivery (your choice)</li>
                  <li>Only important and relevant content</li>
                </ul>
              </div>
            </td>
          </tr>
          
          <!-- Footer -->
          <tr>
            <td style="background-color: #f7fafc; padding: 30px 40px; text-align: center; border-top: 1px solid #e2e8f0;">
              <p style="color: #718096; margin: 0 0 10px 0; font-size: 14px;">
                This confirmation link will expire in 7 days.
              </p>
              <p style="color: #a0aec0; margin: 0; font-size: 12px;">
                If you didn't subscribe to Pulsed, you can safely ignore this email.
              </p>
            </td>
          </tr>
          
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
  `.trim()
}
