import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error(
    'Missing Supabase environment variables. ' +
    'Make sure NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY are set in .env.local'
  )
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

// Types for database tables
export interface Subscriber {
  id: string
  email: string
  name?: string
  status: 'pending' | 'active' | 'unsubscribed' | 'bounced'
  digest_frequency: 'daily' | 'weekly'
  preferences: {
    categories: string[]
  }
  confirmation_token: string
  confirmed_at?: string
  unsubscribed_at?: string
  created_at: string
  updated_at: string
}

export interface Article {
  id: string
  title: string
  abstract?: string
  url?: string
  source?: string
  authors?: string[]
  published_date?: string
  fetched_date?: string
  synced_at: string
}

export interface Prediction {
  id: number
  article_id: string
  predicted_label: string
  confidence?: number
  model_version?: string
  created_at: string
}

export interface Summary {
  id: number
  article_id: string
  summary_text: string
  summary_type?: string
  key_takeaways?: string[]
  model_version?: string
  created_at: string
}

export interface DigestArticle extends Article {
  predicted_label?: string
  confidence?: number
  summary_text?: string
  key_takeaways?: string[]
}
