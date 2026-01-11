import { AlertTriangle, AlertCircle, Info, ChevronDown, ChevronUp } from 'lucide-react'
import { useState } from 'react'

interface ChainBreak {
  break_type: string
  severity: string
  description: string
  from_entry: number | null
  to_entry: number | null
  from_party: string | null
  to_party: string | null
  from_date: string | null
  to_date: string | null
  recommendation: string
}

interface OwnershipPeriod {
  name: string
  acquired_date: string | null
  sold_date: string | null
  acquired_from: string | null
  sold_to: string | null
}

interface ChainAnalysis {
  search_id: number
  is_clear: boolean
  total_breaks: number
  critical_breaks: number
  warning_breaks: number
  breaks: ChainBreak[]
  ownership_summary: OwnershipPeriod[]
  analysis_notes: string[]
}

interface ChainBreakAlertProps {
  analysis: ChainAnalysis | null | undefined
  isLoading?: boolean
}

export default function ChainBreakAlert({ analysis, isLoading }: ChainBreakAlertProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const [showOwnership, setShowOwnership] = useState(false)

  if (isLoading) {
    return (
      <div className="card bg-gray-50 border-gray-200 animate-pulse">
        <div className="h-6 bg-gray-200 rounded w-1/3 mb-4"></div>
        <div className="h-4 bg-gray-200 rounded w-2/3"></div>
      </div>
    )
  }

  if (!analysis) {
    return null
  }

  const getSeverityStyles = (severity: string) => {
    switch (severity) {
      case 'critical':
        return {
          bg: 'bg-red-50',
          border: 'border-red-200',
          icon: <AlertTriangle className="h-5 w-5 text-red-500" />,
          badge: 'bg-red-100 text-red-800',
          text: 'text-red-800',
        }
      case 'warning':
        return {
          bg: 'bg-yellow-50',
          border: 'border-yellow-200',
          icon: <AlertCircle className="h-5 w-5 text-yellow-500" />,
          badge: 'bg-yellow-100 text-yellow-800',
          text: 'text-yellow-800',
        }
      default:
        return {
          bg: 'bg-blue-50',
          border: 'border-blue-200',
          icon: <Info className="h-5 w-5 text-blue-500" />,
          badge: 'bg-blue-100 text-blue-800',
          text: 'text-blue-800',
        }
    }
  }

  const getBreakTypeLabel = (type: string) => {
    switch (type) {
      case 'missing_link':
        return 'Missing Link'
      case 'unknown_grantor':
        return 'Unknown Grantor'
      case 'time_gap':
        return 'Time Gap'
      default:
        return type.replace(/_/g, ' ')
    }
  }

  // Determine overall status
  const overallSeverity = analysis.critical_breaks > 0 ? 'critical' :
                          analysis.warning_breaks > 0 ? 'warning' : 'info'
  const overallStyles = getSeverityStyles(overallSeverity)

  return (
    <div className={`card ${overallStyles.bg} ${overallStyles.border} border-2`}>
      {/* Header */}
      <div
        className="flex items-center justify-between cursor-pointer"
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center gap-3">
          {analysis.is_clear ? (
            <div className="p-2 bg-green-100 rounded-full">
              <svg className="h-6 w-6 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
            </div>
          ) : (
            <div className={`p-2 ${analysis.critical_breaks > 0 ? 'bg-red-100' : 'bg-yellow-100'} rounded-full`}>
              <AlertTriangle className={`h-6 w-6 ${analysis.critical_breaks > 0 ? 'text-red-600' : 'text-yellow-600'}`} />
            </div>
          )}
          <div>
            <h2 className="text-lg font-bold text-gray-900">
              Chain of Title Analysis
            </h2>
            <p className={`text-sm ${analysis.is_clear ? 'text-green-700' : overallStyles.text}`}>
              {analysis.is_clear
                ? 'Chain appears complete - No critical breaks detected'
                : `${analysis.critical_breaks} Critical, ${analysis.warning_breaks} Warning`}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-4">
          {/* Status badges */}
          <div className="flex gap-2">
            {analysis.critical_breaks > 0 && (
              <span className="px-3 py-1 bg-red-500 text-white text-sm font-semibold rounded-full">
                {analysis.critical_breaks} Critical
              </span>
            )}
            {analysis.warning_breaks > 0 && (
              <span className="px-3 py-1 bg-yellow-500 text-white text-sm font-semibold rounded-full">
                {analysis.warning_breaks} Warning
              </span>
            )}
            {analysis.is_clear && (
              <span className="px-3 py-1 bg-green-500 text-white text-sm font-semibold rounded-full">
                Clear
              </span>
            )}
          </div>
          {isExpanded ? (
            <ChevronUp className="h-5 w-5 text-gray-500" />
          ) : (
            <ChevronDown className="h-5 w-5 text-gray-500" />
          )}
        </div>
      </div>

      {isExpanded && (
        <div className="mt-4 space-y-4">
          {/* Analysis Notes */}
          <div className="bg-white bg-opacity-60 rounded-lg p-4">
            <h3 className="font-semibold text-gray-900 mb-2">Analysis Summary</h3>
            <ul className="space-y-1">
              {analysis.analysis_notes.map((note, idx) => (
                <li key={idx} className="text-sm text-gray-700 flex items-start gap-2">
                  <span className="text-gray-400 mt-1">•</span>
                  <span>{note}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Breaks List */}
          {analysis.breaks.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold text-gray-900">Issues Found</h3>
              {analysis.breaks.map((brk, idx) => {
                const styles = getSeverityStyles(brk.severity)
                return (
                  <div
                    key={idx}
                    className={`${styles.bg} ${styles.border} border rounded-lg p-4`}
                  >
                    <div className="flex items-start gap-3">
                      {styles.icon}
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 text-xs font-semibold rounded ${styles.badge}`}>
                            {brk.severity.toUpperCase()}
                          </span>
                          <span className="text-sm font-medium text-gray-600">
                            {getBreakTypeLabel(brk.break_type)}
                          </span>
                        </div>
                        <p className="text-sm font-medium text-gray-900 mb-2">
                          {brk.description}
                        </p>

                        {/* Timeline info */}
                        {(brk.from_date || brk.to_date) && (
                          <div className="text-xs text-gray-500 mb-2">
                            {brk.from_date && (
                              <span>From: {new Date(brk.from_date).toLocaleDateString()}</span>
                            )}
                            {brk.from_date && brk.to_date && <span> → </span>}
                            {brk.to_date && (
                              <span>To: {new Date(brk.to_date).toLocaleDateString()}</span>
                            )}
                          </div>
                        )}

                        {/* Recommendation */}
                        <div className="bg-white bg-opacity-50 rounded p-2 mt-2">
                          <p className="text-xs font-semibold text-gray-600 uppercase mb-1">
                            Recommended Action
                          </p>
                          <p className="text-sm text-gray-700">
                            {brk.recommendation}
                          </p>
                        </div>
                      </div>
                    </div>
                  </div>
                )
              })}
            </div>
          )}

          {/* Ownership Summary */}
          {analysis.ownership_summary.length > 0 && (
            <div>
              <button
                onClick={() => setShowOwnership(!showOwnership)}
                className="flex items-center gap-2 text-sm font-semibold text-gray-700 hover:text-gray-900"
              >
                {showOwnership ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                Ownership Timeline ({analysis.ownership_summary.length} owners)
              </button>

              {showOwnership && (
                <div className="mt-3 bg-white bg-opacity-60 rounded-lg p-4">
                  <div className="space-y-3">
                    {analysis.ownership_summary.map((owner, idx) => (
                      <div key={idx} className="flex items-center gap-4 text-sm">
                        <div className="w-6 h-6 rounded-full bg-primary-100 border-2 border-primary-500 flex items-center justify-center">
                          <span className="text-xs font-semibold text-primary-700">{idx + 1}</span>
                        </div>
                        <div className="flex-1">
                          <p className="font-medium text-gray-900">{owner.name}</p>
                          <p className="text-xs text-gray-500">
                            {owner.acquired_date
                              ? `Acquired: ${new Date(owner.acquired_date).toLocaleDateString()}`
                              : 'Prior to search period'}
                            {owner.sold_date && ` • Sold: ${new Date(owner.sold_date).toLocaleDateString()}`}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
