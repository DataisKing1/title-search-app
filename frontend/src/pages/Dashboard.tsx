import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { searchesApi } from '../lib/api'
import { Search, FileText, Clock, CheckCircle, XCircle, Plus } from 'lucide-react'

export default function Dashboard() {
  const { data: recentSearches, isLoading } = useQuery({
    queryKey: ['searches', 'recent'],
    queryFn: () => searchesApi.list(1, 5),
  })

  const { data: statsData } = useQuery({
    queryKey: ['searches', 'stats'],
    queryFn: () => searchesApi.getStats(),
  })

  const stats = {
    total: statsData?.total || 0,
    completed: statsData?.completed || 0,
    inProgress: statsData?.in_progress || 0,
    failed: statsData?.failed || 0,
  }

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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <Link to="/searches/new" className="btn btn-primary flex items-center">
          <Plus className="h-5 w-5 mr-2" />
          New Search
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="flex items-center">
            <div className="p-3 bg-primary-100 rounded-lg">
              <Search className="h-6 w-6 text-primary-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Total Searches</p>
              <p className="text-2xl font-bold text-gray-900">{stats.total}</p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Completed</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.completed}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 bg-yellow-100 rounded-lg">
              <Clock className="h-6 w-6 text-yellow-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">In Progress</p>
              <p className="text-2xl font-bold text-gray-900">
                {stats.inProgress}
              </p>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center">
            <div className="p-3 bg-red-100 rounded-lg">
              <XCircle className="h-6 w-6 text-red-600" />
            </div>
            <div className="ml-4">
              <p className="text-sm text-gray-500">Failed</p>
              <p className="text-2xl font-bold text-gray-900">{stats.failed}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Searches */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-gray-900">
            Recent Searches
          </h2>
          <Link
            to="/searches"
            className="text-sm text-primary-600 hover:text-primary-700"
          >
            View all
          </Link>
        </div>

        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : recentSearches?.items?.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            No searches yet. Create your first search to get started.
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
                  <tr key={search.id} className="hover:bg-gray-50">
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
                          {search.property.street_address}
                        </p>
                        <p className="text-xs text-gray-500">
                          {search.property.city}, {search.property.county} County
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
                      <div className="w-full bg-gray-200 rounded-full h-2">
                        <div
                          className="bg-primary-600 h-2 rounded-full"
                          style={{ width: `${search.progress_percent}%` }}
                        />
                      </div>
                      <span className="text-xs text-gray-500">
                        {search.progress_percent}%
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(search.created_at).toLocaleDateString()}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}
