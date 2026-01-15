'use client'

import { useEffect, useState } from 'react'
import { supabase, DigestArticle } from '@/lib/supabase'

export default function DigestPreview() {
  const [articles, setArticles] = useState<DigestArticle[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function fetchPreview() {
      try {
        // Fetch articles
        const { data: articlesData, error: articlesError } = await supabase
          .from('articles')
          .select('*')
          .order('synced_at', { ascending: false })
          .limit(3)

        if (articlesError) throw articlesError
        
        if (!articlesData || articlesData.length === 0) {
          setArticles(getSampleArticles())
          setLoading(false)
          return
        }

        // Fetch predictions for these articles
        const articleIds = articlesData.map(a => a.id)
        const { data: predictionsData } = await supabase
          .from('predictions')
          .select('*')
          .in('article_id', articleIds)

        // Fetch summaries for these articles
        const { data: summariesData } = await supabase
          .from('summaries')
          .select('*')
          .in('article_id', articleIds)

        // Create lookup maps
        const predictionsMap = new Map(
          (predictionsData || []).map(p => [p.article_id, p])
        )
        const summariesMap = new Map(
          (summariesData || []).map(s => [s.article_id, s])
        )

        // Transform data
        const transformedArticles: DigestArticle[] = articlesData.map((article: any) => {
          const prediction = predictionsMap.get(article.id)
          const summary = summariesMap.get(article.id)
          
          return {
            ...article,
            predicted_label: prediction?.predicted_label,
            confidence: prediction?.confidence,
            summary_text: summary?.summary_text,
            key_takeaways: summary?.key_takeaways,
          }
        })

        setArticles(transformedArticles)
      } catch (error) {
        console.error('Error fetching preview:', error)
        // Use sample data if no articles exist
        setArticles(getSampleArticles())
      } finally {
        setLoading(false)
      }
    }

    fetchPreview()
  }, [])

  const getSampleArticles = (): DigestArticle[] => [
    {
      id: 'sample-1',
      title: 'Attention Is All You Need: A Deep Dive into Transformer Architecture',
      abstract: 'We propose a new simple network architecture, the Transformer, based solely on attention mechanisms.',
      url: 'https://arxiv.org/abs/1706.03762',
      source: 'arxiv',
      synced_at: new Date().toISOString(),
      predicted_label: 'important',
      confidence: 0.95,
      summary_text: 'This paper introduces the Transformer architecture which replaces recurrent layers with self-attention mechanisms, enabling better parallelization and achieving state-of-the-art results in machine translation.',
      key_takeaways: ['Self-attention replaces recurrence', 'Better parallelization', 'SOTA on translation benchmarks'],
    },
    {
      id: 'sample-2',
      title: 'GPT-4 Technical Report: Capabilities and Limitations',
      abstract: 'We report the development of GPT-4, a large-scale multimodal model.',
      url: 'https://openai.com/research/gpt-4',
      source: 'blog',
      synced_at: new Date().toISOString(),
      predicted_label: 'worth_learning',
      confidence: 0.88,
      summary_text: 'GPT-4 demonstrates human-level performance on various professional and academic benchmarks. The model shows significant improvements in reasoning and reduced hallucinations compared to GPT-3.5.',
      key_takeaways: ['Multimodal capabilities', 'Improved reasoning', 'Better factual accuracy'],
    },
  ]

  const getLabelBadge = (label?: string) => {
    const colors: Record<string, string> = {
      important: 'bg-red-100 text-red-800',
      worth_learning: 'bg-blue-100 text-blue-800',
      reference: 'bg-gray-100 text-gray-800',
      skip: 'bg-gray-100 text-gray-600',
    }
    return colors[label || ''] || 'bg-gray-100 text-gray-800'
  }

  const formatLabel = (label?: string) => {
    return label?.replace('_', ' ').replace(/\b\w/g, c => c.toUpperCase()) || 'Unknown'
  }

  if (loading) {
    return (
      <div className="bg-white rounded-xl shadow-lg p-8 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-6"></div>
        <div className="space-y-4">
          <div className="h-4 bg-gray-200 rounded w-full"></div>
          <div className="h-4 bg-gray-200 rounded w-5/6"></div>
          <div className="h-4 bg-gray-200 rounded w-4/6"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-lg overflow-hidden">
      {/* Email Header */}
      <div className="bg-gradient-to-r from-blue-800 to-blue-600 text-white px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl font-bold">Pulsed Daily Digest</h3>
            <p className="text-blue-200 text-sm">
              {new Date().toLocaleDateString('en-US', { 
                weekday: 'long', 
                year: 'numeric', 
                month: 'long', 
                day: 'numeric' 
              })}
            </p>
          </div>
          <div className="text-right">
            <p className="text-sm text-blue-200">{articles.length} articles</p>
          </div>
        </div>
      </div>

      {/* Articles */}
      <div className="p-6 space-y-6">
        {articles.map((article, index) => (
          <div key={article.id} className="border-b border-gray-100 pb-6 last:border-0 last:pb-0">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center text-blue-600 font-medium">
                {index + 1}
              </div>
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`px-2 py-1 rounded-full text-xs font-medium ${getLabelBadge(article.predicted_label)}`}>
                    {formatLabel(article.predicted_label)}
                  </span>
                  {article.confidence && (
                    <span className="text-xs text-gray-500">
                      {Math.round(article.confidence * 100)}% confident
                    </span>
                  )}
                  <span className="text-xs text-gray-400">• {article.source}</span>
                </div>
                
                <h4 className="text-lg font-medium text-gray-800 mb-2 hover:text-blue-600">
                  <a href={article.url || '#'} target="_blank" rel="noopener noreferrer">
                    {article.title}
                  </a>
                </h4>
                
                {article.summary_text && (
                  <p className="text-gray-600 text-sm mb-3">
                    {article.summary_text}
                  </p>
                )}
                
                {article.key_takeaways && article.key_takeaways.length > 0 && (
                  <div className="bg-gray-50 rounded-lg p-3">
                    <p className="text-xs font-medium text-gray-500 uppercase mb-2">Key Takeaways</p>
                    <ul className="space-y-1">
                      {article.key_takeaways.map((takeaway, i) => (
                        <li key={i} className="text-sm text-gray-700 flex items-start">
                          <span className="text-blue-500 mr-2">•</span>
                          {takeaway}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="bg-gray-50 px-6 py-4 text-center">
        <p className="text-sm text-gray-500">
          This is a preview of what your daily digest will look like.
        </p>
      </div>
    </div>
  )
}
