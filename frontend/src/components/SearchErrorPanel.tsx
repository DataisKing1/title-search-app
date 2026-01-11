import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { searchesApi, getErrorMessage } from '../lib/api'
import {
  AlertTriangle,
  RefreshCw,
  CheckCircle,
  XCircle,
  ChevronDown,
  ChevronUp,
  AlertCircle,
  Clock,
  Lightbulb,
  FileText,
} from 'lucide-react'

interface ErrorEntry {
  timestamp: string
  task: string
  error: string
  category?: string
  severity?: string
  is_transient?: boolean
  recommended_action?: string
}

interface RecoveryAction {
  action: string
  label: string
  description: string
}

interface ErrorPanelProps {
  searchId: number
  status: string
  onRetry?: () => void
}

export default function SearchErrorPanel({ searchId, status, onRetry }: ErrorPanelProps) {
  const queryClient = useQueryClient()
  const [showFullLog, setShowFullLog] = useState(false)

  const { data: errorData, isLoading } = useQuery({
    queryKey: ['search-errors', searchId],
    queryFn: () => searchesApi.getErrors(searchId),
    enabled: status === 'failed',
  })

  const retryMutation = useMutation({
    mutationFn: () => searchesApi.retry(searchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search', searchId] })
      queryClient.invalidateQueries({ queryKey: ['search-errors', searchId] })
      onRetry?.()
    },
  })

  const markPartialMutation = useMutation({
    mutationFn: () => searchesApi.markPartialComplete(searchId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['search', searchId] })
      queryClient.invalidateQueries({ queryKey: ['search-errors', searchId] })
    },
  })

  if (status !== 'failed') {
    return null
  }

  if (isLoading) {
    return (
      <div className="card bg-red-50 border border-red-200">
        <div className="flex items-center justify-center py-4">
          <RefreshCw className="h-5 w-5 animate-spin text-red-500" />
          <span className="ml-2 text-red-700">Loading error details...</span>
        </div>
      </div>
    )
  }

  const errorLog: ErrorEntry[] = errorData?.error_log || []
  const recovery = errorData?.recovery || {}
  const suggestions: string[] = recovery.suggestions || []
  const recoveryActions: RecoveryAction[] = recovery.recovery_actions || []
  const errorSummary = recovery.error_summary || {}

  const getCategoryIcon = (category: string) => {
    switch (category) {
      case 'network':
      case 'timeout':
        return <Clock className="h-4 w-4 text-yellow-500" />
      case 'rate_limit':
        return <AlertTriangle className="h-4 w-4 text-orange-500" />
      case 'auth':
      case 'scraping':
        return <XCircle className="h-4 w-4 text-red-500" />
      default:
        return <AlertCircle className="h-4 w-4 text-red-500" />
    }
  }

  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      low: 'bg-green-100 text-green-800',
      medium: 'bg-yellow-100 text-yellow-800',
      high: 'bg-orange-100 text-orange-800',
      critical: 'bg-red-100 text-red-800',
    }
    return colors[severity] || 'bg-gray-100 text-gray-800'
  }

  const handleAction = (action: string) => {
    switch (action) {
      case 'retry':
        retryMutation.mutate()
        break
      case 'partial_complete':
        markPartialMutation.mutate()
        break
      case 'cancel':
        // Could add cancel mutation here
        break
      case 'manual_upload':
        // Navigate to document upload
        break
    }
  }

  const latestError = errorLog[errorLog.length - 1]

  return (
    <div className="card bg-red-50 border border-red-200">
      <div className="flex items-start">
        <div className="flex-shrink-0">
          <AlertTriangle className="h-6 w-6 text-red-500" />
        </div>
        <div className="ml-4 flex-1">
          <h3 className="text-lg font-medium text-red-800">Search Failed</h3>
          <p className="mt-1 text-sm text-red-700">
            {errorData?.status_message || 'An error occurred during the search.'}
          </p>

          {/* Error Summary */}
          {errorSummary.total_errors > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                {errorSummary.total_errors} error{errorSummary.total_errors > 1 ? 's' : ''}
              </span>
              {errorSummary.consecutive_failures > 1 && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800">
                  {errorSummary.consecutive_failures} consecutive failures
                </span>
              )}
              <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                Retry #{errorData?.retry_count || 0}
              </span>
              {recovery.progress_saved > 0 && (
                <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                  {recovery.progress_saved}% progress saved
                </span>
              )}
            </div>
          )}

          {/* Suggestions */}
          {suggestions.length > 0 && (
            <div className="mt-4 bg-white rounded-lg p-3 border border-red-100">
              <div className="flex items-center text-sm font-medium text-gray-900 mb-2">
                <Lightbulb className="h-4 w-4 text-yellow-500 mr-2" />
                Suggestions
              </div>
              <ul className="list-disc list-inside text-sm text-gray-700 space-y-1">
                {suggestions.map((suggestion, index) => (
                  <li key={index}>{suggestion}</li>
                ))}
              </ul>
            </div>
          )}

          {/* Recovery Actions */}
          {recoveryActions.length > 0 && (
            <div className="mt-4">
              <div className="text-sm font-medium text-gray-900 mb-2">Recovery Options</div>
              <div className="flex flex-wrap gap-2">
                {recoveryActions.map((action) => (
                  <button
                    key={action.action}
                    onClick={() => handleAction(action.action)}
                    disabled={retryMutation.isPending || markPartialMutation.isPending}
                    className={`inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-colors ${
                      action.action === 'retry'
                        ? 'bg-red-600 text-white hover:bg-red-700 disabled:bg-red-400'
                        : action.action === 'partial_complete'
                        ? 'bg-yellow-500 text-white hover:bg-yellow-600 disabled:bg-yellow-400'
                        : 'bg-white text-gray-700 border border-gray-300 hover:bg-gray-50'
                    }`}
                    title={action.description}
                  >
                    {action.action === 'retry' && (
                      <RefreshCw className={`h-4 w-4 mr-2 ${retryMutation.isPending ? 'animate-spin' : ''}`} />
                    )}
                    {action.action === 'partial_complete' && (
                      <CheckCircle className="h-4 w-4 mr-2" />
                    )}
                    {action.action === 'manual_upload' && (
                      <FileText className="h-4 w-4 mr-2" />
                    )}
                    {action.action === 'cancel' && (
                      <XCircle className="h-4 w-4 mr-2" />
                    )}
                    {action.label}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Error Log */}
          {errorLog.length > 0 && (
            <div className="mt-4">
              <button
                onClick={() => setShowFullLog(!showFullLog)}
                className="flex items-center text-sm text-gray-700 hover:text-gray-900"
              >
                {showFullLog ? (
                  <ChevronUp className="h-4 w-4 mr-1" />
                ) : (
                  <ChevronDown className="h-4 w-4 mr-1" />
                )}
                {showFullLog ? 'Hide' : 'Show'} Error Log ({errorLog.length} entries)
              </button>

              {showFullLog && (
                <div className="mt-2 bg-white rounded-lg border border-red-100 overflow-hidden">
                  <div className="max-h-64 overflow-y-auto">
                    {errorLog.map((entry, index) => (
                      <div
                        key={index}
                        className={`p-3 ${index > 0 ? 'border-t border-gray-100' : ''}`}
                      >
                        <div className="flex items-start justify-between">
                          <div className="flex items-center">
                            {getCategoryIcon(entry.category || 'unknown')}
                            <span className="ml-2 text-sm font-medium text-gray-900">
                              {entry.task}
                            </span>
                            {entry.severity && (
                              <span
                                className={`ml-2 px-2 py-0.5 text-xs rounded-full ${getSeverityBadge(
                                  entry.severity
                                )}`}
                              >
                                {entry.severity}
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-gray-500">
                            {new Date(entry.timestamp).toLocaleString()}
                          </span>
                        </div>
                        <p className="mt-1 text-sm text-gray-600 break-words">
                          {entry.error}
                        </p>
                        {entry.is_transient !== undefined && (
                          <div className="mt-1 text-xs text-gray-500">
                            {entry.is_transient ? (
                              <span className="text-green-600">Transient - may succeed on retry</span>
                            ) : (
                              <span className="text-red-600">Persistent - may require manual action</span>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Error mutations feedback */}
          {retryMutation.isError && (
            <div className="mt-3 text-sm text-red-600">
              {getErrorMessage(retryMutation.error, 'Failed to retry search')}
            </div>
          )}
          {markPartialMutation.isError && (
            <div className="mt-3 text-sm text-red-600">
              {getErrorMessage(markPartialMutation.error, 'Failed to mark as partial')}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
