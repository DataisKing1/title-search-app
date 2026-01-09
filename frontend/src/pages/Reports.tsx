import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { reportsApi } from '@/lib/api'
import { FileText, Download, CheckCircle, Clock, AlertTriangle } from 'lucide-react'
import { Report } from '@/lib/types'

export default function Reports() {
  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports'],
    queryFn: () => reportsApi.list(),
  })

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      draft: 'bg-gray-100 text-gray-800',
      review: 'bg-yellow-100 text-yellow-800',
      approved: 'bg-green-100 text-green-800',
      issued: 'bg-blue-100 text-blue-800',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'approved':
      case 'issued':
        return <CheckCircle className="h-4 w-4" />
      case 'review':
        return <Clock className="h-4 w-4" />
      default:
        return <AlertTriangle className="h-4 w-4" />
    }
  }

  const getRiskBadge = (score: number | null) => {
    if (score === null) return 'bg-gray-100 text-gray-600'
    if (score <= 30) return 'bg-green-100 text-green-800'
    if (score <= 60) return 'bg-yellow-100 text-yellow-800'
    return 'bg-red-100 text-red-800'
  }

  const getRiskLabel = (score: number | null) => {
    if (score === null) return 'N/A'
    if (score <= 30) return 'Low Risk'
    if (score <= 60) return 'Medium Risk'
    return 'High Risk'
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">Title Reports</h1>
      </div>

      {/* Reports List */}
      <div className="card">
        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : !reports || reports.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <FileText className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No reports yet.</p>
            <p className="text-sm mt-2">
              Reports are generated after title searches are completed.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Report #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Type
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Risk Score
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Created
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {reports.map((report: Report) => (
                  <tr key={report.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <Link
                        to={`/reports/${report.id}`}
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        {report.report_number}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                      {report.report_type}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusBadge(
                          report.status
                        )}`}
                      >
                        {getStatusIcon(report.status)}
                        {report.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex px-2.5 py-0.5 rounded-full text-xs font-medium ${getRiskBadge(
                          report.risk_score
                        )}`}
                      >
                        {report.risk_score !== null
                          ? `${report.risk_score} - ${getRiskLabel(report.risk_score)}`
                          : 'N/A'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(report.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      {report.pdf_generated_at && (
                        <a
                          href={`/api/reports/${report.id}/download`}
                          className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700"
                        >
                          <Download className="h-4 w-4 mr-1" />
                          PDF
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
    </div>
  )
}
