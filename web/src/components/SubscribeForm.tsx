'use client'

import { useState } from 'react'
import { supabase } from '@/lib/supabase'

export default function SubscribeForm() {
  const [email, setEmail] = useState('')
  const [name, setName] = useState('')
  const [frequency, setFrequency] = useState<'daily' | 'weekly'>('daily')
  const [status, setStatus] = useState<'idle' | 'loading' | 'success' | 'error'>('idle')
  const [message, setMessage] = useState('')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setStatus('loading')

    try {
      // Insert subscriber
      const { data, error } = await supabase
        .from('subscribers')
        .insert([
          {
            email: email.toLowerCase().trim(),
            name: name.trim() || null,
            digest_frequency: frequency,
            status: 'pending',
          }
        ])
        .select()
        .single()

      if (error) {
        if (error.code === '23505') {
          // Duplicate email
          setMessage('This email is already subscribed.')
          setStatus('error')
        } else {
          throw error
        }
        return
      }

      // Track analytics event
      await supabase.from('analytics_events').insert([
        {
          event_type: 'subscribe',
          subscriber_id: data.id,
          metadata: { source: 'website' }
        }
      ])

      setStatus('success')
      setMessage('Please check your email to confirm your subscription.')
      setEmail('')
      setName('')
    } catch (error) {
      console.error('Subscription error:', error)
      setStatus('error')
      setMessage('Something went wrong. Please try again.')
    }
  }

  if (status === 'success') {
    return (
      <div className="text-center py-6">
        <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
          <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        </div>
        <h3 className="text-xl font-medium text-gray-800 mb-2">Almost there!</h3>
        <p className="text-gray-600">{message}</p>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="email" className="block text-sm font-medium text-gray-700 mb-1">
          Email Address *
        </label>
        <input
          type="email"
          id="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          placeholder="you@example.com"
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
        />
      </div>

      <div>
        <label htmlFor="name" className="block text-sm font-medium text-gray-700 mb-1">
          Name (optional)
        </label>
        <input
          type="text"
          id="name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name"
          className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          Digest Frequency
        </label>
        <div className="flex space-x-4">
          <label className="flex items-center">
            <input
              type="radio"
              name="frequency"
              value="daily"
              checked={frequency === 'daily'}
              onChange={() => setFrequency('daily')}
              className="w-4 h-4 text-blue-600"
            />
            <span className="ml-2 text-gray-700">Daily</span>
          </label>
          <label className="flex items-center">
            <input
              type="radio"
              name="frequency"
              value="weekly"
              checked={frequency === 'weekly'}
              onChange={() => setFrequency('weekly')}
              className="w-4 h-4 text-blue-600"
            />
            <span className="ml-2 text-gray-700">Weekly</span>
          </label>
        </div>
      </div>

      {status === 'error' && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg text-sm">
          {message}
        </div>
      )}

      <button
        type="submit"
        disabled={status === 'loading'}
        className="w-full py-3 px-4 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {status === 'loading' ? (
          <span className="flex items-center justify-center">
            <svg className="animate-spin -ml-1 mr-2 h-5 w-5 text-white" fill="none" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
            </svg>
            Subscribing...
          </span>
        ) : (
          'Subscribe'
        )}
      </button>

      <p className="text-xs text-gray-500 text-center">
        We respect your privacy. Unsubscribe anytime.
      </p>
    </form>
  )
}
