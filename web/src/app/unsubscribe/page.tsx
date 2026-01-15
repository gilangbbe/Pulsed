'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useState } from 'react'
import { supabase } from '@/lib/supabase'
import Link from 'next/link'

function UnsubscribeContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'pending' | 'loading' | 'success' | 'error'>('pending')
  const [message, setMessage] = useState('')

  const handleUnsubscribe = async () => {
    if (!token) {
      setStatus('error')
      setMessage('Invalid unsubscribe link.')
      return
    }

    setStatus('loading')

    try {
      const { data, error } = await supabase
        .rpc('unsubscribe', { token })

      if (error) throw error

      if (data.success) {
        setStatus('success')
        setMessage('You have been successfully unsubscribed.')
      } else {
        setStatus('error')
        setMessage(data.error || 'Could not process unsubscribe request.')
      }
    } catch (error) {
      console.error('Unsubscribe error:', error)
      setStatus('error')
      setMessage('Something went wrong. Please try again.')
    }
  }

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 text-center">
        {status === 'pending' && (
          <>
            <div className="w-16 h-16 bg-yellow-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">Unsubscribe from Pulsed</h1>
            <p className="text-gray-600 mb-6">
              Are you sure you want to unsubscribe? You will no longer receive the AI & ML news digest.
            </p>
            <div className="space-y-3">
              <button
                onClick={handleUnsubscribe}
                className="w-full px-6 py-3 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
              >
                Yes, Unsubscribe Me
              </button>
              <Link
                href="/"
                className="block w-full px-6 py-3 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
              >
                No, Keep My Subscription
              </Link>
            </div>
          </>
        )}

        {status === 'loading' && (
          <>
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800">Processing...</h1>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">Unsubscribed</h1>
            <p className="text-gray-600 mb-6">{message}</p>
            <p className="text-sm text-gray-500">
              We're sorry to see you go. You can always resubscribe from our homepage.
            </p>
            <Link
              href="/"
              className="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Back to Home
            </Link>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">Error</h1>
            <p className="text-gray-600 mb-6">{message}</p>
            <Link
              href="/"
              className="inline-block px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Back to Home
            </Link>
          </>
        )}
      </div>
    </main>
  )
}

export default function UnsubscribePage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-4 border-blue-600 rounded-full border-t-transparent"></div>
      </main>
    }>
      <UnsubscribeContent />
    </Suspense>
  )
}
