import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { searchesApi } from '../../lib/api'
import { Plus, Search, ChevronLeft, ChevronRight } from 'lucide-react'

export default function SearchList() {
  const [page, setPage] = useState(1)
  const [statusFilter, setStatusFilter] = useState<string>('')
  const [countyFilter, setCountyFilter] = useState('')

  const { data, isLoading } = useQuery({
    queryKey: ['searches', page, statusFilter, countyFilter],
    queryFn: () =>
      searchesApi.list(page, 20, statusFilter || undefined, countyFilter || undefined),
  })

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
        <h1 className="text-2xl font-bold text-gray-900">Title Searches</h1>
        <Link to="/searches/new" className="btn btn-primary flex items-center">
          <Plus className="h-5 w-5 mr-2" />
          New Search
        </Link>
      </div>

      {/* Filters */}
      <div className="card">
        <div className="flex flex-wrap gap-4">
          <div>
            <label className="label">Status</label>
            <select
              value={statusFilter}
              onChange={(e) => {
                setStatusFilter(e.target.value)
                setPage(1)
              }}
              className="input w-40"
            >
              <option value="">All Statuses</option>
              <option value="pending">Pending</option>
              <option value="queued">Queued</option>
              <option value="scraping">Scraping</option>
              <option value="analyzing">Analyzing</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          <div>
            <label className="label">County</label>
            <input
              type="text"
              value={countyFilter}
              onChange={(e) => {
                setCountyFilter(e.target.value)
                setPage(1)
              }}
              placeholder="Filter by county..."
              className="input w-48"
            />
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="card">
        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : data?.items?.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Search className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No searches found.</p>
          </div>
        ) : (
          <>
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
                      County
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Documents
                    </th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                      Created
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-200">
                  {data?.items?.map((search: any) => (
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
                        <p className="text-sm text-gray-900">
                          {search.property.street_address}
                        </p>
                        <p className="text-xs text-gray-500">
                          {search.property.city}, {search.property.state}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {search.property.county}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusBadge(
                            search.status
                          )}`}
                        >
                          {search.status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900">
                        {search.document_count}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-500">
                        {new Date(search.created_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {data && data.pages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <p className="text-sm text-gray-500">
                  Showing {(page - 1) * 20 + 1} to{' '}
                  {Math.min(page * 20, data.total)} of {data.total} results
                </p>
                <div className="flex gap-2">
                  <button
                    onClick={() => setPage(page - 1)}
                    disabled={page === 1}
                    className="btn btn-secondary disabled:opacity-50"
                  >
                    <ChevronLeft className="h-5 w-5" />
                  </button>
                  <span className="flex items-center px-3 text-sm">
                    Page {page} of {data.pages}
                  </span>
                  <button
                    onClick={() => setPage(page + 1)}
                    disabled={page >= data.pages}
                    className="btn btn-secondary disabled:opacity-50"
                  >
                    <ChevronRight className="h-5 w-5" />
                  </button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
