'use client'

import { Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import Link from 'next/link'

function ConfirmContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [message, setMessage] = useState('')

  useEffect(() => {
    async function confirmSubscription() {
      if (!token) {
        setStatus('error')
        setMessage('Invalid confirmation link.')
        return
      }

      try {
        const { data, error } = await supabase
          .rpc('confirm_subscription', { token })

        if (error) throw error

        if (data.success) {
          setStatus('success')
          setMessage(`Welcome! Your subscription for ${data.email} has been confirmed.`)
        } else {
          setStatus('error')
          setMessage(data.error || 'Could not confirm subscription.')
        }
      } catch (error) {
        console.error('Confirmation error:', error)
        setStatus('error')
        setMessage('Something went wrong. Please try again or contact support.')
      }
    }

    confirmSubscription()
  }, [token])

  return (
    <main className="min-h-screen bg-gray-50 flex items-center justify-center px-4">
      <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8 text-center">
        {status === 'loading' && (
          <>
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="animate-spin h-8 w-8 text-blue-600" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800">Confirming...</h1>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">Subscription Confirmed</h1>
            <p className="text-gray-600 mb-6">{message}</p>
            <p className="text-sm text-gray-500">
              You'll receive your first digest soon. Look out for emails from Pulsed.
            </p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </div>
            <h1 className="text-xl font-semibold text-gray-800 mb-2">Confirmation Failed</h1>
            <p className="text-gray-600 mb-6">{message}</p>
          </>
        )}

        <Link 
          href="/"
          className="inline-block mt-4 px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Back to Home
        </Link>
      </div>
    </main>
  )
}

export default function ConfirmPage() {
  return (
    <Suspense fallback={
      <main className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin h-8 w-8 border-4 border-blue-600 rounded-full border-t-transparent"></div>
      </main>
    }>
      <ConfirmContent />
    </Suspense>
  )
}
