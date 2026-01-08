import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { searchesApi } from '../../lib/api'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  RefreshCw,
  XCircle,
  FileText,
  AlertTriangle,
  CheckCircle,
  Clock,
  MapPin,
  Calendar,
  Link as LinkIcon,
  Download,
  Shield,
  Users,
} from 'lucide-react'

interface SearchDocument {
  id: number
  document_type: string
  instrument_number: string | null
  recording_date: string | null
  grantor: string[]
  grantee: string[]
  source: string
  file_name: string | null
  ai_summary: string | null
  needs_review: boolean
}

interface ChainOfTitleEntry {
  id: number
  sequence_number: number
  transaction_type: string | null
  transaction_date: string | null
  grantor_names: string[]
  grantee_names: string[]
  consideration: number | null
  recording_reference: string | null
  description: string | null
}

interface EncumbranceEntry {
  id: number
  encumbrance_type: string
  status: string
  holder_name: string | null
  original_amount: number | null
  current_amount: number | null
  recorded_date: string | null
  risk_level: string
  requires_action: boolean
  description: string | null
}

export default function SearchDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data: search, isLoading, error } = useQuery({
    queryKey: ['search', id],
    queryFn: () => searchesApi.get(Number(id)),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (['pending', 'queued', 'scraping', 'analyzing', 'generating'].includes(status)) {
        return 5000
      }
      return false
    },
  })

  const { data: documents } = useQuery({
    queryKey: ['search', id, 'documents'],
    queryFn: () => searchesApi.getDocuments(Number(id)),
    enabled: !!search,
  })

  const { data: chainOfTitle } = useQuery({
    queryKey: ['search', id, 'chain-of-title'],
    queryFn: () => searchesApi.getChainOfTitle(Number(id)),
    enabled: !!search,
  })

  const { data: encumbrances } = useQuery({
    queryKey: ['search', id, 'encumbrances'],
    queryFn: () => searchesApi.getEncumbrances(Number(id)),
    enabled: !!search,
  })

  const cancelMutation = useMutation({
    mutationFn: () => searchesApi.cancel(Number(id)),
    onSuccess: () => {
      toast.success('Search cancelled')
      queryClient.invalidateQueries({ queryKey: ['search', id] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel search')
    },
  })

  const retryMutation = useMutation({
    mutationFn: () => searchesApi.retry(Number(id)),
    onSuccess: () => {
      toast.success('Search retry initiated')
      queryClient.invalidateQueries({ queryKey: ['search', id] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to retry search')
    },
  })

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-6 w-6 text-green-500" />
      case 'failed':
        return <XCircle className="h-6 w-6 text-red-500" />
      case 'cancelled':
        return <XCircle className="h-6 w-6 text-gray-400" />
      default:
        return <Clock className="h-6 w-6 text-yellow-500 animate-pulse" />
    }
  }

  const getStatusColor = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-800 border-gray-200',
      queued: 'bg-blue-100 text-blue-800 border-blue-200',
      scraping: 'bg-yellow-100 text-yellow-800 border-yellow-200',
      analyzing: 'bg-purple-100 text-purple-800 border-purple-200',
      generating: 'bg-indigo-100 text-indigo-800 border-indigo-200',
      completed: 'bg-green-100 text-green-800 border-green-200',
      failed: 'bg-red-100 text-red-800 border-red-200',
      cancelled: 'bg-gray-100 text-gray-600 border-gray-200',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  const getRiskBadge = (level: string) => {
    const colors: Record<string, string> = {
      low: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      high: 'bg-orange-100 text-orange-800',
      critical: 'bg-red-100 text-red-800',
    }
    return colors[level] || 'bg-gray-100 text-gray-800'
  }

  const formatCurrency = (amount: number | null) => {
    if (amount === null) return '-'
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 0,
    }).format(amount)
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error || !search) {
    return (
      <div className="text-center py-12">
        <AlertTriangle className="h-12 w-12 mx-auto text-red-500 mb-4" />
        <h2 className="text-lg font-semibold text-gray-900">Search not found</h2>
        <Link to="/searches" className="text-primary-600 hover:text-primary-700 mt-2 inline-block">
          Back to searches
        </Link>
      </div>
    )
  }

  const isInProgress = ['pending', 'queued', 'scraping', 'analyzing', 'generating'].includes(search.status)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link to="/searches" className="p-2 hover:bg-gray-100 rounded-lg">
            <ArrowLeft className="h-5 w-5" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              {search.reference_number}
            </h1>
            <p className="text-sm text-gray-500">
              Created {new Date(search.created_at).toLocaleString()}
            </p>
          </div>
        </div>

        <div className="flex gap-2">
          {search.status === 'failed' && (
            <button
              onClick={() => retryMutation.mutate()}
              disabled={retryMutation.isPending}
              className="btn btn-secondary flex items-center"
            >
              <RefreshCw className="h-4 w-4 mr-2" />
              Retry
            </button>
          )}
          {isInProgress && (
            <button
              onClick={() => cancelMutation.mutate()}
              disabled={cancelMutation.isPending}
              className="btn btn-danger flex items-center"
            >
              <XCircle className="h-4 w-4 mr-2" />
              Cancel
            </button>
          )}
        </div>
      </div>

      {/* Status Card */}
      <div className={`card border-2 ${getStatusColor(search.status)}`}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {getStatusIcon(search.status)}
            <div>
              <h2 className="text-lg font-semibold capitalize">{search.status}</h2>
              <p className="text-sm opacity-75">
                {search.status_message || 'Processing...'}
              </p>
            </div>
          </div>
          <div className="text-right">
            <p className="text-2xl font-bold">{search.progress_percent}%</p>
            <p className="text-sm opacity-75">Progress</p>
          </div>
        </div>

        <div className="mt-4">
          <div className="w-full bg-white bg-opacity-50 rounded-full h-3">
            <div
              className="bg-current h-3 rounded-full transition-all duration-500"
              style={{ width: `${search.progress_percent}%` }}
            />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Property Information */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <MapPin className="h-5 w-5 mr-2 text-gray-400" />
            Property Information
          </h2>

          <dl className="space-y-3">
            <div>
              <dt className="text-sm text-gray-500">Address</dt>
              <dd className="text-sm font-medium text-gray-900">
                {search.property.street_address}
              </dd>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">City</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.property.city}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">State</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.property.state}
                </dd>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">County</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.property.county}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">ZIP Code</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.property.zip_code || '-'}
                </dd>
              </div>
            </div>
            {search.property.parcel_number && (
              <div>
                <dt className="text-sm text-gray-500">Parcel Number</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.property.parcel_number}
                </dd>
              </div>
            )}
          </dl>
        </div>

        {/* Search Details */}
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
            <Calendar className="h-5 w-5 mr-2 text-gray-400" />
            Search Details
          </h2>

          <dl className="space-y-3">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">Search Type</dt>
                <dd className="text-sm font-medium text-gray-900 capitalize">
                  {search.search_type}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Search Years</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.search_years} years
                </dd>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">Priority</dt>
                <dd className="text-sm font-medium text-gray-900 capitalize">
                  {search.priority}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Documents Found</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {documents?.length || 0}
                </dd>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <dt className="text-sm text-gray-500">Encumbrances</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {encumbrances?.length || 0}
                </dd>
              </div>
              <div>
                <dt className="text-sm text-gray-500">Started</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {search.started_at
                    ? new Date(search.started_at).toLocaleString()
                    : '-'}
                </dd>
              </div>
            </div>
            {search.completed_at && (
              <div>
                <dt className="text-sm text-gray-500">Completed</dt>
                <dd className="text-sm font-medium text-gray-900">
                  {new Date(search.completed_at).toLocaleString()}
                </dd>
              </div>
            )}
          </dl>
        </div>
      </div>

      {/* Documents Section */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <FileText className="h-5 w-5 mr-2 text-gray-400" />
          Documents ({documents?.length || 0})
        </h2>

        {!documents || documents.length === 0 ? (
          <p className="text-sm text-gray-500">
            {isInProgress ? 'Documents will appear here as they are discovered.' : 'No documents found.'}
          </p>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Instrument #</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Grantor</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Grantee</th>
                  <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {documents.map((doc: SearchDocument) => (
                  <tr key={doc.id} className="hover:bg-gray-50">
                    <td className="px-4 py-2">
                      <span className="text-sm font-medium capitalize">
                        {doc.document_type.replace(/_/g, ' ')}
                      </span>
                      {doc.needs_review && (
                        <span className="ml-2 inline-flex px-2 py-0.5 rounded-full text-xs bg-yellow-100 text-yellow-800">
                          Review
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {doc.instrument_number || '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {doc.recording_date ? new Date(doc.recording_date).toLocaleDateString() : '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {doc.grantor?.join(', ') || '-'}
                    </td>
                    <td className="px-4 py-2 text-sm text-gray-600">
                      {doc.grantee?.join(', ') || '-'}
                    </td>
                    <td className="px-4 py-2">
                      {doc.file_name && (
                        <a
                          href={`/api/documents/${doc.id}/download`}
                          className="text-primary-600 hover:text-primary-700"
                        >
                          <Download className="h-4 w-4" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Chain of Title Section */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <LinkIcon className="h-5 w-5 mr-2 text-gray-400" />
          Chain of Title ({chainOfTitle?.length || 0})
        </h2>

        {!chainOfTitle || chainOfTitle.length === 0 ? (
          <p className="text-sm text-gray-500">
            {isInProgress ? 'Chain of title will be built after document analysis.' : 'No chain of title entries found.'}
          </p>
        ) : (
          <div className="space-y-4">
            {chainOfTitle.map((entry: ChainOfTitleEntry, index: number) => (
              <div key={entry.id} className="relative pl-8 pb-4">
                {/* Timeline connector */}
                {index < chainOfTitle.length - 1 && (
                  <div className="absolute left-3 top-6 bottom-0 w-0.5 bg-gray-200"></div>
                )}
                {/* Timeline dot */}
                <div className="absolute left-0 top-1 w-6 h-6 rounded-full bg-primary-100 border-2 border-primary-500 flex items-center justify-center">
                  <span className="text-xs font-medium text-primary-600">{entry.sequence_number}</span>
                </div>

                <div className="bg-gray-50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900 capitalize">
                      {entry.transaction_type?.replace(/_/g, ' ') || 'Transaction'}
                    </span>
                    <span className="text-sm text-gray-500">
                      {entry.transaction_date ? new Date(entry.transaction_date).toLocaleDateString() : '-'}
                    </span>
                  </div>
                  <div className="grid grid-cols-2 gap-4 text-sm">
                    <div>
                      <span className="text-gray-500">From: </span>
                      <span className="text-gray-900">{entry.grantor_names?.join(', ') || '-'}</span>
                    </div>
                    <div>
                      <span className="text-gray-500">To: </span>
                      <span className="text-gray-900">{entry.grantee_names?.join(', ') || '-'}</span>
                    </div>
                  </div>
                  {entry.consideration && (
                    <div className="mt-2 text-sm">
                      <span className="text-gray-500">Consideration: </span>
                      <span className="text-gray-900 font-medium">{formatCurrency(entry.consideration)}</span>
                    </div>
                  )}
                  {entry.recording_reference && (
                    <div className="mt-1 text-xs text-gray-500">
                      Ref: {entry.recording_reference}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Encumbrances Section */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4 flex items-center">
          <Shield className="h-5 w-5 mr-2 text-gray-400" />
          Encumbrances ({encumbrances?.length || 0})
        </h2>

        {!encumbrances || encumbrances.length === 0 ? (
          <p className="text-sm text-gray-500">
            {isInProgress ? 'Encumbrances will be identified during analysis.' : 'No encumbrances found.'}
          </p>
        ) : (
          <div className="space-y-4">
            {encumbrances.map((enc: EncumbranceEntry) => (
              <div key={enc.id} className="border rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-gray-900 capitalize">
                      {enc.encumbrance_type.replace(/_/g, ' ')}
                    </span>
                    <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${getRiskBadge(enc.risk_level)}`}>
                      {enc.risk_level}
                    </span>
                  </div>
                  <span className={`inline-flex px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                    enc.status === 'active' ? 'bg-red-100 text-red-800' :
                    enc.status === 'released' ? 'bg-green-100 text-green-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {enc.status}
                  </span>
                </div>

                <div className="grid grid-cols-2 gap-4 text-sm">
                  {enc.holder_name && (
                    <div>
                      <span className="text-gray-500">Holder: </span>
                      <span className="text-gray-900">{enc.holder_name}</span>
                    </div>
                  )}
                  {enc.recorded_date && (
                    <div>
                      <span className="text-gray-500">Recorded: </span>
                      <span className="text-gray-900">{new Date(enc.recorded_date).toLocaleDateString()}</span>
                    </div>
                  )}
                  {enc.original_amount && (
                    <div>
                      <span className="text-gray-500">Amount: </span>
                      <span className="text-gray-900">{formatCurrency(enc.original_amount)}</span>
                    </div>
                  )}
                  {enc.current_amount && enc.current_amount !== enc.original_amount && (
                    <div>
                      <span className="text-gray-500">Current: </span>
                      <span className="text-gray-900">{formatCurrency(enc.current_amount)}</span>
                    </div>
                  )}
                </div>

                {enc.description && (
                  <p className="mt-2 text-sm text-gray-600">{enc.description}</p>
                )}

                {enc.requires_action && (
                  <div className="mt-2 flex items-center text-sm text-orange-600">
                    <AlertTriangle className="h-4 w-4 mr-1" />
                    Action required before closing
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
