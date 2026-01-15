'use client'

import { useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { supabase } from '@/lib/supabase'
import AnalyticsCharts from '@/components/AnalyticsCharts'

interface AdminStats {
  total_subscribers: number
  pending_subscribers: number
  total_articles: number
  articles_today: number
  digests_sent: number
  total_email_opens: number
  subscribers_this_week: number
  open_rate: number
}

export default function AdminDashboard() {
  const router = useRouter()
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [password, setPassword] = useState('')
  const [authError, setAuthError] = useState('')
  const [stats, setStats] = useState<AdminStats | null>(null)
  const [loading, setLoading] = useState(false)

  // Simple password-based auth for admin
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Check password via API route
    try {
      const res = await fetch('/api/admin/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      })
      
      if (res.ok) {
        setIsAuthenticated(true)
        localStorage.setItem('admin_auth', 'true')
        fetchStats()
      } else {
        setAuthError('Invalid password')
      }
    } catch (error) {
      setAuthError('Authentication failed')
    }
  }

  const fetchStats = async () => {
    setLoading(true)
    try {
      const { data, error } = await supabase.rpc('get_admin_stats')
      if (error) throw error
      setStats(data)
    } catch (error) {
      console.error('Error fetching stats:', error)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // Check if already authenticated (simple session)
    if (localStorage.getItem('admin_auth') === 'true') {
      setIsAuthenticated(true)
      fetchStats()
    }
  }, [])

  const handleLogout = () => {
    localStorage.removeItem('admin_auth')
    setIsAuthenticated(false)
    setStats(null)
  }

  if (!isAuthenticated) {
    return (
      <main className="min-h-screen bg-gray-100 flex items-center justify-center px-4">
        <div className="max-w-md w-full bg-white rounded-xl shadow-lg p-8">
          <div className="text-center mb-6">
            <h1 className="text-2xl font-bold text-gray-800">Admin Dashboard</h1>
            <p className="text-gray-600 text-sm">Enter password to continue</p>
          </div>
          
          <form onSubmit={handleLogin} className="space-y-4">
            <div>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                autoFocus
              />
            </div>
            
            {authError && (
              <p className="text-red-600 text-sm text-center">{authError}</p>
            )}
            
            <button
              type="submit"
              className="w-full py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
            >
              Login
            </button>
          </form>
          
          <div className="mt-6 text-center">
            <Link href="/" className="text-sm text-blue-600 hover:underline">
              Back to Home
            </Link>
          </div>
        </div>
      </main>
    )
  }

  return (
    <main className="min-h-screen bg-gray-100">
      {/* Header */}
      <header className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-800">Pulsed Admin</h1>
            <p className="text-sm text-gray-500">Analytics Dashboard</p>
          </div>
          <div className="flex items-center gap-4">
            <Link 
              href="/"
              className="text-sm text-gray-600 hover:text-gray-800"
            >
              View Site
            </Link>
            <button
              onClick={handleLogout}
              className="text-sm text-red-600 hover:text-red-700"
            >
              Logout
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Stats Grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Active Subscribers"
            value={stats?.total_subscribers || 0}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
              </svg>
            }
            color="blue"
          />
          <StatCard
            title="New This Week"
            value={stats?.subscribers_this_week || 0}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
              </svg>
            }
            color="green"
          />
          <StatCard
            title="Open Rate"
            value={`${stats?.open_rate || 0}%`}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 19v-8.93a2 2 0 01.89-1.664l7-4.666a2 2 0 012.22 0l7 4.666A2 2 0 0121 10.07V19M3 19a2 2 0 002 2h14a2 2 0 002-2M3 19l6.75-4.5M21 19l-6.75-4.5M3 10l6.75 4.5M21 10l-6.75 4.5m0 0l-1.14.76a2 2 0 01-2.22 0l-1.14-.76" />
              </svg>
            }
            color="purple"
          />
          <StatCard
            title="Digests Sent"
            value={stats?.digests_sent || 0}
            icon={
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            }
            color="indigo"
          />
        </div>

        {/* Secondary Stats */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard
            title="Total Articles"
            value={stats?.total_articles || 0}
            small
          />
          <StatCard
            title="Articles Today"
            value={stats?.articles_today || 0}
            small
          />
          <StatCard
            title="Pending Confirm"
            value={stats?.pending_subscribers || 0}
            small
          />
          <StatCard
            title="Email Opens"
            value={stats?.total_email_opens || 0}
            small
          />
        </div>

        {/* Charts */}
        <AnalyticsCharts />

        {/* Quick Actions */}
        <div className="mt-8 bg-white rounded-xl shadow-sm p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-4">Quick Actions</h2>
          <div className="grid md:grid-cols-3 gap-4">
            <Link
              href="/admin/subscribers"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all"
            >
              <h3 className="font-medium text-gray-800">Manage Subscribers</h3>
              <p className="text-sm text-gray-500">View and manage all subscribers</p>
            </Link>
            <Link
              href="/admin/digests"
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all"
            >
              <h3 className="font-medium text-gray-800">Digest History</h3>
              <p className="text-sm text-gray-500">View past digests and performance</p>
            </Link>
            <button
              onClick={fetchStats}
              className="p-4 border border-gray-200 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-all text-left"
            >
              <h3 className="font-medium text-gray-800">Refresh Stats</h3>
              <p className="text-sm text-gray-500">Reload dashboard data</p>
            </button>
          </div>
        </div>
      </div>
    </main>
  )
}

interface StatCardProps {
  title: string
  value: number | string
  icon?: React.ReactNode
  color?: 'blue' | 'green' | 'purple' | 'indigo'
  small?: boolean
}

function StatCard({ title, value, icon, color = 'blue', small = false }: StatCardProps) {
  const colorClasses = {
    blue: 'bg-blue-100 text-blue-600',
    green: 'bg-green-100 text-green-600',
    purple: 'bg-purple-100 text-purple-600',
    indigo: 'bg-indigo-100 text-indigo-600',
  }

  if (small) {
    return (
      <div className="bg-white rounded-xl shadow-sm p-4">
        <p className="text-sm text-gray-500">{title}</p>
        <p className="text-2xl font-bold text-gray-800 mt-1">{value}</p>
      </div>
    )
  }

  return (
    <div className="bg-white rounded-xl shadow-sm p-6">
      <div className="flex items-center gap-4">
        {icon && (
          <div className={`p-3 rounded-full ${colorClasses[color]}`}>
            {icon}
          </div>
        )}
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-800">{value}</p>
        </div>
      </div>
    </div>
  )
}
