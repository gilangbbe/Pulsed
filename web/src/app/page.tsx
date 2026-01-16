'use client'

import { useState } from 'react'
import Link from 'next/link'
import SubscribeForm from '@/components/SubscribeForm'
import DigestPreview from '@/components/DigestPreview'

export default function Home() {
  const [showPreview, setShowPreview] = useState(false)

  return (
    <main className="min-h-screen bg-gray-50">
      {/* Hero Section */}
      <div className="gradient-bg text-white">
        <div className="max-w-4xl mx-auto px-4 py-16 sm:py-24">
          <div className="text-center">
            <h1 className="text-4xl sm:text-5xl font-bold mb-4">
              Pulsed
            </h1>
            <p className="text-xl sm:text-2xl text-blue-100 mb-2">
              AI & Machine Learning News Digest
            </p>
            <p className="text-lg text-blue-200 max-w-2xl mx-auto">
              Stay ahead with curated insights from ArXiv, research papers, and industry news. 
              Our ML models filter and summarize the most important developments.
            </p>
          </div>
        </div>
      </div>

      {/* Subscribe Section */}
      <div className="max-w-xl mx-auto px-4 -mt-12">
        <div className="bg-white rounded-xl shadow-lg p-8">
          <h2 className="text-2xl font-semibold text-gray-800 text-center mb-6">
            Subscribe to the Digest
          </h2>
          <SubscribeForm />
        </div>
      </div>

      {/* Features Section */}
      <div className="max-w-4xl mx-auto px-4 py-16">
        <h2 className="text-2xl font-semibold text-gray-800 text-center mb-12">
          How It Works
        </h2>
        
        <div className="grid md:grid-cols-3 gap-8">
          <div className="text-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">Daily Collection</h3>
            <p className="text-gray-600">
              We gather papers and articles from ArXiv, research blogs, and ML communities daily.
            </p>
          </div>
          
          <div className="text-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">ML Classification</h3>
            <p className="text-gray-600">
              Our classifier model identifies the most important and worth-reading content.
            </p>
          </div>
          
          <div className="text-center">
            <div className="w-16 h-16 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-4">
              <svg className="w-8 h-8 text-blue-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
              </svg>
            </div>
            <h3 className="text-lg font-medium text-gray-800 mb-2">Digest Delivery</h3>
            <p className="text-gray-600">
              Receive a summarized digest in your inbox with key takeaways and links.
            </p>
          </div>
        </div>
      </div>

      {/* Preview Section */}
      <div className="bg-gray-100 py-16">
        <div className="max-w-4xl mx-auto px-4">
          <div className="text-center mb-8">
            <h2 className="text-2xl font-semibold text-gray-800 mb-2">
              Sample Digest Preview
            </h2>
            <p className="text-gray-600">
              See what a typical digest looks like
            </p>
          </div>
          
          <button
            onClick={() => setShowPreview(!showPreview)}
            className="block mx-auto mb-8 px-6 py-3 bg-white border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 transition-colors"
          >
            {showPreview ? 'Hide Preview' : 'Show Preview'}
          </button>
          
          {showPreview && <DigestPreview />}
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 text-gray-400 py-12">
        <div className="max-w-4xl mx-auto px-4 text-center">
          <p className="text-lg font-medium text-white mb-2">Pulsed</p>
          <p className="text-sm mb-4">AI-powered news curation for ML practitioners</p>
          
          {/* Content Attribution Disclaimer */}
          <div className="bg-gray-700 rounded-lg p-4 mb-6 max-w-2xl mx-auto">
            <p className="text-xs text-gray-300 leading-relaxed">
              <strong className="text-white">Content Notice:</strong> Pulsed provides AI-generated summaries of publicly available content. 
              All original content belongs to their respective owners. 
              We aggregate content from academic sources (ArXiv, Semantic Scholar) and official company blogs 
              that permit educational and non-commercial use.
            </p>
            <p className="text-xs text-gray-400 mt-2">
              Pulsed is a free, non-commercial educational service.
            </p>
          </div>
          
          <div className="flex justify-center space-x-6 text-sm">
            <Link href="/unsubscribe" className="hover:text-white transition-colors">
              Unsubscribe
            </Link>
          </div>
          <p className="text-xs mt-8 text-gray-500">
            © {new Date().getFullYear()} Pulsed. All rights reserved.
          </p>
        </div>
      </footer>
    </main>
  )
}
