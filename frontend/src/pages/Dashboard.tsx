import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { searchesApi } from '../lib/api'
import {
  Search,
  Clock,
  CheckCircle,
  XCircle,
  Plus,
  FileText,
  AlertTriangle,
  TrendingUp,
  Calendar,
  Activity,
  RefreshCw,
  MapPin,
  ChevronRight
} from 'lucide-react'

interface DashboardStats {
  total: number
  completed: number
  in_progress: number
  failed: number
  documents_count?: number
  encumbrances_count?: number
  pending_review?: number
  this_week?: number
  this_month?: number
  by_county?: Record<string, number>
  by_status?: Record<string, number>
}

export default function Dashboard() {
  const { data: recentSearches, isLoading } = useQuery({
    queryKey: ['searches', 'recent'],
    queryFn: () => searchesApi.list(1, 5),
  })

  const { data: statsData, refetch: refetchStats } = useQuery<DashboardStats>({
    queryKey: ['searches', 'stats'],
    queryFn: () => searchesApi.getStats(),
    refetchInterval: 30000, // Refresh every 30 seconds
  })

  const stats = {
    total: statsData?.total || 0,
    completed: statsData?.completed || 0,
    inProgress: statsData?.in_progress || 0,
    failed: statsData?.failed || 0,
    documents: statsData?.documents_count || 0,
    encumbrances: statsData?.encumbrances_count || 0,
    pendingReview: statsData?.pending_review || 0,
    thisWeek: statsData?.this_week || 0,
    thisMonth: statsData?.this_month || 0,
    byCounty: statsData?.by_county || {},
    byStatus: statsData?.by_status || {},
  }

  // Calculate completion rate
  const completionRate = stats.total > 0
    ? Math.round((stats.completed / stats.total) * 100)
    : 0

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-5 w-5 text-green-500" />
      case 'failed':
        return <XCircle className="h-5 w-5 text-red-500" />
      default:
        return <Clock className="h-5 w-5 text-yellow-500" />
    }
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-800',
      queued: 'bg-blue-100 text-blue-800',
      scraping: 'bg-yellow-100 text-yellow-800',
      analyzing: 'bg-purple-100 text-purple-800',
      generating: 'bg-indigo-100 text-indigo-800',
      completed: 'bg-green-100 text-green-800',
      failed: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-600',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  // Get top counties
  const topCounties = Object.entries(stats.byCounty)
    .sort(([, a], [, b]) => b - a)
    .slice(0, 5)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
          <p className="text-sm text-gray-500 mt-1">
            Overview of your title search activity
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => refetchStats()}
            className="btn btn-secondary flex items-center"
          >
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </button>
          <Link to="/searches/new" className="btn btn-primary flex items-center">
            <Plus className="h-5 w-5 mr-2" />
            New Search
          </Link>
        </div>
      </div>

      {/* Primary Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card bg-gradient-to-br from-primary-50 to-white border border-primary-100">
          <div className="flex items-center">
            <div className="p-3 bg-primary-100 rounded-lg">
              <Search className="h-6 w-6 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Total Searches</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center text-sm">
            <TrendingUp className="h-4 w-4 text-primary-500 mr-1" />
            <span className="text-gray-600">{stats.thisWeek} this week</span>
          </div>
        </div>

        <div className="card bg-gradient-to-br from-green-50 to-white border border-green-100">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Completed</p>
              <p className="text-2xl font-bold text-gray-900">{stats.completed}</p>
            </div>
          </div>
          <div className="mt-3 flex items-center text-sm">
            <span className="text-green-600 font-medium">{completionRate}%</span>
            <span className="text-gray-500 ml-1">success rate</span>
          </div>
        </div>

        <div className="card bg-gradient-to-br from-yellow-50 to-white border border-yellow-100">
          <div className="flex items-center">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <Clock className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">In Progress</p>
              <p className="text-2xl font-bold text-gray-900">{stats.inProgress}</p>
            </div>
          </div>
          <div className="mt-3">
            {stats.inProgress > 0 && (
              <Link to="/searches?status=in_progress" className="text-sm text-yellow-600 hover:text-yellow-700 flex items-center">
                View active searches
                <ChevronRight className="h-4 w-4 ml-1" />
              </Link>
            )}
          </div>
        </div>

        <div className="card bg-gradient-to-br from-red-50 to-white border border-red-100">
          <div className="flex items-center">
            <div className="p-3 bg-red-100 rounded-lg">
              <XCircle className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Failed</p>
              <p className="text-2xl font-bold text-gray-900">{stats.failed}</p>
            </div>
          </div>
          <div className="mt-3">
            {stats.failed > 0 && (
              <Link to="/searches?status=failed" className="text-sm text-red-600 hover:text-red-700 flex items-center">
                Review failed
                <ChevronRight className="h-4 w-4 ml-1" />
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* Secondary Stats Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="p-2 bg-blue-100 rounded-lg">
                <FileText className="h-5 w-5 text-blue-600" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-gray-500">Documents</p>
                <p className="text-xl font-bold text-gray-900">{stats.documents}</p>
              </div>
            </div>
            <Link to="/searches" className="text-blue-600 hover:text-blue-700">
              <ChevronRight className="h-5 w-5" />
            </Link>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="p-2 bg-orange-100 rounded-lg">
                <AlertTriangle className="h-5 w-5 text-orange-600" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-gray-500">Encumbrances</p>
                <p className="text-xl font-bold text-gray-900">{stats.encumbrances}</p>
              </div>
            </div>
            <span className="text-xs text-orange-600 bg-orange-50 px-2 py-1 rounded-full">
              Active liens/mortgages
            </span>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Activity className="h-5 w-5 text-purple-600" />
              </div>
              <div className="ml-3">
                <p className="text-sm text-gray-500">Pending Review</p>
                <p className="text-xl font-bold text-gray-900">{stats.pendingReview}</p>
              </div>
            </div>
            {stats.pendingReview > 0 && (
              <span className="text-xs text-purple-600 bg-purple-50 px-2 py-1 rounded-full">
                Needs attention
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Searches - Takes 2 columns */}
        <div className="lg:col-span-2 card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Recent Searches</h2>
            <Link
              to="/searches"
              className="text-sm text-primary-600 hover:text-primary-700 flex items-center"
            >
              View all
              <ChevronRight className="h-4 w-4 ml-1" />
            </Link>
          </div>

          {isLoading ? (
            <div className="text-center py-8 text-gray-500">
              <RefreshCw className="h-8 w-8 animate-spin mx-auto text-gray-400" />
              <p className="mt-2">Loading...</p>
            </div>
          ) : recentSearches?.items?.length === 0 ? (
            <div className="text-center py-8">
              <Search className="h-12 w-12 mx-auto text-gray-300" />
              <p className="mt-3 text-gray-500">No searches yet.</p>
              <Link
                to="/searches/new"
                className="mt-3 inline-flex items-center text-primary-600 hover:text-primary-700"
              >
                <Plus className="h-4 w-4 mr-1" />
                Create your first search
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Reference
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Property
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Progress
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {recentSearches?.items?.map((search: any) => (
                    <tr key={search.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3">
                        <Link
                          to={`/searches/${search.id}`}
                          className="text-primary-600 hover:text-primary-700 font-medium"
                        >
                          {search.reference_number}
                        </Link>
                      </td>
                      <td className="px-4 py-3">
                        <div>
                          <p className="text-sm text-gray-900">
                            {search.property?.street_address || 'N/A'}
                          </p>
                          <p className="text-xs text-gray-500 flex items-center">
                            <MapPin className="h-3 w-3 mr-1" />
                            {search.property?.city}, {search.property?.county} County
                          </p>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${getStatusBadge(
                            search.status
                          )}`}
                        >
                          {getStatusIcon(search.status)}
                          <span className="ml-1 capitalize">{search.status}</span>
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center">
                          <div className="flex-1 bg-gray-200 rounded-full h-2 mr-2">
                            <div
                              className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                              style={{ width: `${search.progress_percent}%` }}
                            />
                          </div>
                          <span className="text-xs text-gray-500 w-8">
                            {search.progress_percent}%
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        <div className="flex items-center">
                          <Calendar className="h-4 w-4 mr-1 text-gray-400" />
                          {new Date(search.created_at).toLocaleDateString()}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Right Sidebar - Quick Stats & Actions */}
        <div className="space-y-6">
          {/* Quick Actions */}
          <div className="card">
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
              Quick Actions
            </h3>
            <div className="space-y-2">
              <Link
                to="/searches/new"
                className="flex items-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="p-2 bg-primary-100 rounded-lg">
                  <Plus className="h-4 w-4 text-primary-600" />
                </div>
                <span className="ml-3 text-sm font-medium text-gray-900">New Search</span>
              </Link>
              <Link
                to="/batch"
                className="flex items-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="p-2 bg-blue-100 rounded-lg">
                  <FileText className="h-4 w-4 text-blue-600" />
                </div>
                <span className="ml-3 text-sm font-medium text-gray-900">Batch Upload</span>
              </Link>
              <Link
                to="/reports"
                className="flex items-center p-3 rounded-lg bg-gray-50 hover:bg-gray-100 transition-colors"
              >
                <div className="p-2 bg-green-100 rounded-lg">
                  <TrendingUp className="h-4 w-4 text-green-600" />
                </div>
                <span className="ml-3 text-sm font-medium text-gray-900">View Reports</span>
              </Link>
            </div>
          </div>

          {/* County Distribution */}
          {topCounties.length > 0 && (
            <div className="card">
              <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
                Searches by County
              </h3>
              <div className="space-y-3">
                {topCounties.map(([county, count]) => (
                  <div key={county} className="flex items-center justify-between">
                    <div className="flex items-center">
                      <MapPin className="h-4 w-4 text-gray-400 mr-2" />
                      <span className="text-sm text-gray-700">{county}</span>
                    </div>
                    <span className="text-sm font-medium text-gray-900">{count}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* This Month Summary */}
          <div className="card bg-gradient-to-br from-indigo-50 to-white border border-indigo-100">
            <h3 className="text-sm font-semibold text-gray-900 uppercase tracking-wide mb-4">
              This Month
            </h3>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-3xl font-bold text-indigo-600">{stats.thisMonth}</p>
                <p className="text-sm text-gray-500">searches completed</p>
              </div>
              <div className="p-3 bg-indigo-100 rounded-full">
                <Calendar className="h-8 w-8 text-indigo-600" />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
