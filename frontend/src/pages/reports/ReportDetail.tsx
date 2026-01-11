import { useParams, Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { reportsApi, searchesApi } from '../../lib/api'
import toast from 'react-hot-toast'
import {
  ArrowLeft,
  Download,
  CheckCircle,
  FileText,
  AlertTriangle,
  Clock,
  Home,
  User,
  Calendar,
  FileCheck,
  ChevronDown,
  ChevronUp,
} from 'lucide-react'
import { useState } from 'react'
import { useAuthStore } from '../../store/auth'

interface ScheduleAProperty {
  street_address: string
  city: string
  county: string
  state: string
  zip_code: string
  parcel_number: string
  legal_description: string
}

interface ScheduleAVesting {
  current_owner: string
  vesting_type: string
  vesting_instrument: string
  vesting_date: string
}

interface ScheduleA {
  effective_date: string
  property: ScheduleAProperty
  vesting: ScheduleAVesting
}

interface ScheduleB1Item {
  number: number
  type: string
  holder: string
  amount: string
  instrument_number: string
  recording_date: string
  description: string
  action_required: string
}

interface ScheduleB2Item {
  number: number
  type: string
  description: string
  instrument_number: string
  recording_date: string
  affects: string
}

interface ReportDetail {
  id: number
  search_id: number
  report_number: string
  report_type: string
  status: 'draft' | 'review' | 'approved' | 'issued'
  effective_date: string | null
  expiration_date: string | null
  risk_score: number | null
  risk_assessment_summary: string | null
  pdf_generated_at: string | null
  created_at: string
  updated_at: string
  schedule_a: ScheduleA | null
  schedule_b1: ScheduleB1Item[] | null
  schedule_b2: ScheduleB2Item[] | null
  chain_of_title_narrative: string | null
  ai_recommendations: Array<{ type: string; description: string }> | null
}

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const token = useAuthStore((state) => state.token)

  const [expandedSections, setExpandedSections] = useState({
    scheduleA: true,
    scheduleB1: true,
    scheduleB2: true,
    chainNarrative: false,
    riskAssessment: true,
  })

  const { data: report, isLoading, error } = useQuery<ReportDetail>({
    queryKey: ['report', id],
    queryFn: () => reportsApi.get(Number(id)),
  })

  const approveMutation = useMutation({
    mutationFn: () => reportsApi.approve(Number(id)),
    onSuccess: () => {
      toast.success('Report approved successfully')
      queryClient.invalidateQueries({ queryKey: ['report', id] })
    },
    onError: () => {
      toast.error('Failed to approve report')
    },
  })

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({ ...prev, [section]: !prev[section] }))
  }

  const getStatusBadge = (status: string) => {
    const styles = {
      draft: 'bg-gray-100 text-gray-800',
      review: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      issued: 'bg-blue-100 text-blue-800',
    }
    const icons = {
      draft: <FileText className="h-4 w-4" />,
      review: <Clock className="h-4 w-4" />,
      approved: <CheckCircle className="h-4 w-4" />,
      issued: <FileCheck className="h-4 w-4" />,
    }
    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${styles[status as keyof typeof styles] || styles.draft}`}>
        {icons[status as keyof typeof icons]}
        {status.charAt(0).toUpperCase() + status.slice(1)}
      </span>
    )
  }

  const getRiskBadge = (score: number | null) => {
    if (score === null) return null
    let color = 'bg-green-100 text-green-800'
    let label = 'Low Risk'

    if (score >= 80) {
      color = 'bg-red-100 text-red-800'
      label = 'Critical'
    } else if (score >= 60) {
      color = 'bg-red-100 text-red-800'
      label = 'High Risk'
    } else if (score >= 40) {
      color = 'bg-orange-100 text-orange-800'
      label = 'Elevated'
    } else if (score >= 20) {
      color = 'bg-yellow-100 text-yellow-800'
      label = 'Moderate'
    }

    return (
      <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium ${color}`}>
        <AlertTriangle className="h-4 w-4" />
        {label} ({score}/100)
      </span>
    )
  }

  const handleDownload = () => {
    if (!token) {
      toast.error('Please log in to download')
      return
    }
    // Open download URL in new tab with auth
    const downloadUrl = `${reportsApi.downloadUrl(Number(id))}?token=${token}`
    window.open(downloadUrl, '_blank')
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error || !report) {
    return (
      <div className="text-center py-12">
        <p className="text-red-600">Failed to load report</p>
        <Link to="/reports" className="text-primary-600 hover:underline mt-2 inline-block">
          Back to Reports
        </Link>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link
            to="/reports"
            className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <ArrowLeft className="h-5 w-5 text-gray-500" />
          </Link>
          <div>
            <h1 className="text-2xl font-bold text-gray-900">
              Title Report {report.report_number}
            </h1>
            <p className="text-gray-500">
              Search #{report.search_id} | Created {new Date(report.created_at).toLocaleDateString()}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {getStatusBadge(report.status)}
          {getRiskBadge(report.risk_score)}
        </div>
      </div>

      {/* Action Buttons */}
      <div className="flex gap-3">
        {report.pdf_generated_at && (
          <button
            onClick={handleDownload}
            className="btn-primary flex items-center gap-2"
          >
            <Download className="h-4 w-4" />
            Download PDF
          </button>
        )}
        {(report.status === 'draft' || report.status === 'review') && (
          <button
            onClick={() => approveMutation.mutate()}
            disabled={approveMutation.isPending}
            className="btn-secondary flex items-center gap-2"
          >
            <CheckCircle className="h-4 w-4" />
            {approveMutation.isPending ? 'Approving...' : 'Approve Report'}
          </button>
        )}
        <Link
          to={`/searches/${report.search_id}`}
          className="btn-outline flex items-center gap-2"
        >
          View Search
        </Link>
      </div>

      {/* Schedule A - Property Information */}
      {report.schedule_a && (
        <div className="card">
          <button
            onClick={() => toggleSection('scheduleA')}
            className="w-full flex items-center justify-between text-left"
          >
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <Home className="h-5 w-5 text-primary-600" />
              Schedule A - Property & Vesting
            </h2>
            {expandedSections.scheduleA ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </button>

          {expandedSections.scheduleA && (
            <div className="mt-4 grid grid-cols-1 md:grid-cols-2 gap-6">
              {/* Property Info */}
              <div className="space-y-3">
                <h3 className="font-medium text-gray-900 border-b pb-2">Property Information</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Address:</span>
                    <span className="font-medium">{report.schedule_a.property.street_address}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">City, State, Zip:</span>
                    <span className="font-medium">
                      {report.schedule_a.property.city}, {report.schedule_a.property.state} {report.schedule_a.property.zip_code}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">County:</span>
                    <span className="font-medium">{report.schedule_a.property.county}</span>
                  </div>
                  {report.schedule_a.property.parcel_number && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Parcel Number:</span>
                      <span className="font-medium">{report.schedule_a.property.parcel_number}</span>
                    </div>
                  )}
                </div>
              </div>

              {/* Vesting Info */}
              <div className="space-y-3">
                <h3 className="font-medium text-gray-900 border-b pb-2">Vesting Information</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500">Current Owner:</span>
                    <span className="font-medium">{report.schedule_a.vesting.current_owner || 'Unknown'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Vesting Type:</span>
                    <span className="font-medium">{report.schedule_a.vesting.vesting_type || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">Vesting Date:</span>
                    <span className="font-medium">{report.schedule_a.vesting.vesting_date || 'N/A'}</span>
                  </div>
                  {report.schedule_a.vesting.vesting_instrument && (
                    <div className="flex justify-between">
                      <span className="text-gray-500">Instrument:</span>
                      <span className="font-medium">{report.schedule_a.vesting.vesting_instrument}</span>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Schedule B-1 - Requirements */}
      <div className="card">
        <button
          onClick={() => toggleSection('scheduleB1')}
          className="w-full flex items-center justify-between text-left"
        >
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="h-5 w-5 text-orange-600" />
            Schedule B-1 - Requirements ({report.schedule_b1?.length || 0})
          </h2>
          {expandedSections.scheduleB1 ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>

        {expandedSections.scheduleB1 && (
          <div className="mt-4">
            {report.schedule_b1 && report.schedule_b1.length > 0 ? (
              <div className="space-y-4">
                {report.schedule_b1.map((item) => (
                  <div key={item.number} className="border rounded-lg p-4 bg-orange-50 border-orange-200">
                    <div className="flex items-start justify-between">
                      <div>
                        <span className="font-semibold text-gray-900">{item.number}. {item.type}</span>
                        <p className="text-sm text-gray-600 mt-1">Holder: {item.holder}</p>
                      </div>
                      <span className="text-lg font-bold text-orange-700">{item.amount}</span>
                    </div>
                    {item.instrument_number && (
                      <p className="text-sm text-gray-500 mt-2">
                        Instrument: {item.instrument_number} | Recorded: {item.recording_date}
                      </p>
                    )}
                    <div className="mt-3 p-2 bg-white rounded border border-orange-200">
                      <p className="text-sm font-medium text-orange-800">Action Required:</p>
                      <p className="text-sm text-gray-700">{item.action_required}</p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No requirements identified - title appears clear of liens.</p>
            )}
          </div>
        )}
      </div>

      {/* Schedule B-2 - Exceptions */}
      <div className="card">
        <button
          onClick={() => toggleSection('scheduleB2')}
          className="w-full flex items-center justify-between text-left"
        >
          <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
            <FileText className="h-5 w-5 text-blue-600" />
            Schedule B-2 - Exceptions ({report.schedule_b2?.length || 0})
          </h2>
          {expandedSections.scheduleB2 ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
        </button>

        {expandedSections.scheduleB2 && (
          <div className="mt-4">
            {report.schedule_b2 && report.schedule_b2.length > 0 ? (
              <div className="space-y-3">
                {report.schedule_b2.map((item) => (
                  <div key={item.number} className="border rounded-lg p-3 bg-gray-50">
                    <div className="flex items-start gap-3">
                      <span className="font-semibold text-gray-700 min-w-[24px]">{item.number}.</span>
                      <div className="flex-1">
                        <p className="text-gray-900">{item.description}</p>
                        {item.instrument_number && (
                          <p className="text-sm text-gray-500 mt-1">
                            {item.type} - Instrument: {item.instrument_number}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 italic">No exceptions identified.</p>
            )}
          </div>
        )}
      </div>

      {/* Chain of Title Narrative */}
      {report.chain_of_title_narrative && (
        <div className="card">
          <button
            onClick={() => toggleSection('chainNarrative')}
            className="w-full flex items-center justify-between text-left"
          >
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <User className="h-5 w-5 text-purple-600" />
              Chain of Title Narrative
            </h2>
            {expandedSections.chainNarrative ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </button>

          {expandedSections.chainNarrative && (
            <div className="mt-4">
              <pre className="whitespace-pre-wrap font-mono text-sm bg-gray-50 p-4 rounded-lg overflow-x-auto">
                {report.chain_of_title_narrative}
              </pre>
            </div>
          )}
        </div>
      )}

      {/* Risk Assessment */}
      {report.risk_assessment_summary && (
        <div className="card">
          <button
            onClick={() => toggleSection('riskAssessment')}
            className="w-full flex items-center justify-between text-left"
          >
            <h2 className="text-lg font-semibold text-gray-900 flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-red-600" />
              Risk Assessment
            </h2>
            {expandedSections.riskAssessment ? <ChevronUp className="h-5 w-5" /> : <ChevronDown className="h-5 w-5" />}
          </button>

          {expandedSections.riskAssessment && (
            <div className="mt-4">
              <div className={`p-4 rounded-lg ${
                (report.risk_score || 0) >= 60 ? 'bg-red-50 border border-red-200' :
                (report.risk_score || 0) >= 40 ? 'bg-orange-50 border border-orange-200' :
                (report.risk_score || 0) >= 20 ? 'bg-yellow-50 border border-yellow-200' :
                'bg-green-50 border border-green-200'
              }`}>
                <pre className="whitespace-pre-wrap text-sm">
                  {report.risk_assessment_summary}
                </pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
