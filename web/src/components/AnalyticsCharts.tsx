'use client'

import { useEffect, useState } from 'react'
import { supabase } from '@/lib/supabase'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

interface DailyStat {
  stat_date: string
  new_subscribers: number
  emails_sent: number
  emails_opened: number
  page_views: number
}

interface SourceBreakdown {
  source: string
  count: number
}

export default function AnalyticsCharts() {
  const [dailyStats, setDailyStats] = useState<DailyStat[]>([])
  const [sourceBreakdown, setSourceBreakdown] = useState<SourceBreakdown[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchData()
  }, [])

  async function fetchData() {
    setLoading(true)
    try {
      // Fetch daily stats for last 30 days
      const thirtyDaysAgo = new Date()
      thirtyDaysAgo.setDate(thirtyDaysAgo.getDate() - 30)

      const { data: statsData, error: statsError } = await supabase
        .from('daily_stats')
        .select('*')
        .gte('stat_date', thirtyDaysAgo.toISOString().split('T')[0])
        .order('stat_date', { ascending: true })

      if (!statsError && statsData) {
        setDailyStats(statsData)
      }

      // Fetch article source breakdown
      const { data: articlesData, error: articlesError } = await supabase
        .from('articles')
        .select('source')

      if (!articlesError && articlesData) {
        const sourceCounts: Record<string, number> = {}
        articlesData.forEach((article) => {
          const source = article.source || 'unknown'
          sourceCounts[source] = (sourceCounts[source] || 0) + 1
        })
        
        const breakdown = Object.entries(sourceCounts)
          .map(([source, count]) => ({ source, count }))
          .sort((a, b) => b.count - a.count)
        
        setSourceBreakdown(breakdown)
      }
    } catch (error) {
      console.error('Error fetching analytics:', error)
    } finally {
      setLoading(false)
    }
  }

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#EC4899']

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  if (loading) {
    return (
      <div className="grid md:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl shadow-sm p-6 h-80 animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-full bg-gray-100 rounded"></div>
        </div>
        <div className="bg-white rounded-xl shadow-sm p-6 h-80 animate-pulse">
          <div className="h-4 bg-gray-200 rounded w-1/3 mb-4"></div>
          <div className="h-full bg-gray-100 rounded"></div>
        </div>
      </div>
    )
  }

  // Generate sample data if no real data exists
  const chartData = dailyStats.length > 0 ? dailyStats : generateSampleData()

  return (
    <div className="grid md:grid-cols-2 gap-6">
      {/* Subscribers Growth Chart */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Subscriber Growth</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis 
              dataKey="stat_date" 
              tickFormatter={formatDate}
              stroke="#9CA3AF"
              fontSize={12}
            />
            <YAxis stroke="#9CA3AF" fontSize={12} />
            <Tooltip 
              labelFormatter={formatDate}
              contentStyle={{ 
                borderRadius: '8px', 
                border: '1px solid #E5E7EB',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
              }}
            />
            <Line 
              type="monotone" 
              dataKey="new_subscribers" 
              stroke="#3B82F6" 
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
              name="New Subscribers"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Email Performance Chart */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Email Performance</h3>
        <ResponsiveContainer width="100%" height={300}>
          <BarChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis 
              dataKey="stat_date" 
              tickFormatter={formatDate}
              stroke="#9CA3AF"
              fontSize={12}
            />
            <YAxis stroke="#9CA3AF" fontSize={12} />
            <Tooltip 
              labelFormatter={formatDate}
              contentStyle={{ 
                borderRadius: '8px', 
                border: '1px solid #E5E7EB',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
              }}
            />
            <Bar dataKey="emails_sent" fill="#3B82F6" name="Sent" radius={[4, 4, 0, 0]} />
            <Bar dataKey="emails_opened" fill="#10B981" name="Opened" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Article Sources Pie Chart */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Article Sources</h3>
        {sourceBreakdown.length > 0 ? (
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={sourceBreakdown}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ source, percent }) => `${source} (${(percent * 100).toFixed(0)}%)`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="count"
              >
                {sourceBreakdown.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        ) : (
          <div className="h-[300px] flex items-center justify-center text-gray-500">
            No article data available
          </div>
        )}
      </div>

      {/* Page Views Chart */}
      <div className="bg-white rounded-xl shadow-sm p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-4">Page Views</h3>
        <ResponsiveContainer width="100%" height={300}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#E5E7EB" />
            <XAxis 
              dataKey="stat_date" 
              tickFormatter={formatDate}
              stroke="#9CA3AF"
              fontSize={12}
            />
            <YAxis stroke="#9CA3AF" fontSize={12} />
            <Tooltip 
              labelFormatter={formatDate}
              contentStyle={{ 
                borderRadius: '8px', 
                border: '1px solid #E5E7EB',
                boxShadow: '0 2px 4px rgba(0,0,0,0.1)'
              }}
            />
            <Line 
              type="monotone" 
              dataKey="page_views" 
              stroke="#8B5CF6" 
              strokeWidth={2}
              dot={{ r: 4 }}
              activeDot={{ r: 6 }}
              name="Page Views"
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

// Generate sample data for demo purposes
function generateSampleData() {
  const data = []
  const today = new Date()
  
  for (let i = 30; i >= 0; i--) {
    const date = new Date(today)
    date.setDate(date.getDate() - i)
    
    data.push({
      stat_date: date.toISOString().split('T')[0],
      new_subscribers: Math.floor(Math.random() * 5) + 1,
      emails_sent: Math.floor(Math.random() * 20) + 10,
      emails_opened: Math.floor(Math.random() * 15) + 5,
      page_views: Math.floor(Math.random() * 50) + 20,
    })
  }
  
  return data
}
