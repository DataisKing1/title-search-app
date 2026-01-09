import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { batchApi } from '@/lib/api'
import toast from 'react-hot-toast'
import {
  Upload,
  FileText,
  CheckCircle,
  XCircle,
  Clock,
  Play,
  Trash2,
  AlertTriangle,
} from 'lucide-react'
import { Batch } from '@/lib/types'

export default function BatchUpload() {
  const queryClient = useQueryClient()
  const [selectedFile, setSelectedFile] = useState<File | null>(null)
  const [expandedBatch, setExpandedBatch] = useState<number | null>(null)

  const { data: batches, isLoading } = useQuery({
    queryKey: ['batches'],
    queryFn: async () => {
      // Note: We'd need a list endpoint for batches
      // For now, return empty array
      return [] as Batch[]
    },
  })

  const uploadMutation = useMutation({
    mutationFn: batchApi.upload,
    onSuccess: (data) => {
      toast.success(`Batch ${data.batch_number} uploaded successfully!`)
      setSelectedFile(null)
      queryClient.invalidateQueries({ queryKey: ['batches'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to upload batch')
    },
  })

  const processMutation = useMutation({
    mutationFn: batchApi.process,
    onSuccess: () => {
      toast.success('Batch processing started!')
      queryClient.invalidateQueries({ queryKey: ['batches'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to start processing')
    },
  })

  const cancelMutation = useMutation({
    mutationFn: batchApi.cancel,
    onSuccess: () => {
      toast.success('Batch cancelled')
      queryClient.invalidateQueries({ queryKey: ['batches'] })
    },
    onError: (error: any) => {
      toast.error(error.response?.data?.detail || 'Failed to cancel batch')
    },
  })

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      if (!file.name.endsWith('.csv')) {
        toast.error('Only CSV files are supported')
        return
      }
      setSelectedFile(file)
    }
  }

  const handleUpload = () => {
    if (selectedFile) {
      uploadMutation.mutate(selectedFile)
    }
  }

  const getStatusBadge = (status: string) => {
    const colors: Record<string, string> = {
      pending: 'bg-gray-100 text-gray-800',
      processing: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      partial: 'bg-yellow-100 text-yellow-800',
      failed: 'bg-red-100 text-red-800',
      cancelled: 'bg-gray-100 text-gray-600',
    }
    return colors[status] || 'bg-gray-100 text-gray-800'
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="h-4 w-4" />
      case 'failed':
        return <XCircle className="h-4 w-4" />
      case 'processing':
        return <Clock className="h-4 w-4 animate-spin" />
      case 'partial':
        return <AlertTriangle className="h-4 w-4" />
      default:
        return <Clock className="h-4 w-4" />
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Batch Upload</h1>
        <p className="text-sm text-gray-500 mt-1">
          Upload CSV files to create multiple title searches at once
        </p>
      </div>

      {/* Upload Section */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Upload CSV File
        </h2>

        <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center">
          <Upload className="h-12 w-12 mx-auto text-gray-400 mb-4" />
          <p className="text-sm text-gray-600 mb-4">
            Upload a CSV file with property information
          </p>

          <input
            type="file"
            accept=".csv"
            onChange={handleFileChange}
            className="hidden"
            id="csv-upload"
          />
          <label
            htmlFor="csv-upload"
            className="btn btn-secondary cursor-pointer inline-block"
          >
            Select CSV File
          </label>

          {selectedFile && (
            <div className="mt-4 p-4 bg-gray-50 rounded-lg inline-block">
              <div className="flex items-center gap-3">
                <FileText className="h-5 w-5 text-gray-400" />
                <span className="text-sm font-medium">{selectedFile.name}</span>
                <span className="text-xs text-gray-500">
                  ({(selectedFile.size / 1024).toFixed(1)} KB)
                </span>
              </div>
            </div>
          )}
        </div>

        {selectedFile && (
          <div className="mt-4 flex justify-end">
            <button
              onClick={handleUpload}
              disabled={uploadMutation.isPending}
              className="btn btn-primary disabled:opacity-50"
            >
              {uploadMutation.isPending ? 'Uploading...' : 'Upload & Process'}
            </button>
          </div>
        )}

        {/* CSV Format Instructions */}
        <div className="mt-6 p-4 bg-gray-50 rounded-lg">
          <h3 className="text-sm font-medium text-gray-900 mb-2">
            Required CSV Columns:
          </h3>
          <ul className="text-sm text-gray-600 space-y-1">
            <li>
              <code className="bg-white px-1 rounded">street_address</code> or{' '}
              <code className="bg-white px-1 rounded">address</code> - Property
              street address
            </li>
            <li>
              <code className="bg-white px-1 rounded">city</code> - City name
            </li>
            <li>
              <code className="bg-white px-1 rounded">county</code> - County
              name
            </li>
            <li>
              <code className="bg-white px-1 rounded">parcel_number</code> or{' '}
              <code className="bg-white px-1 rounded">apn</code> - (Optional)
              Parcel/APN number
            </li>
          </ul>
        </div>
      </div>

      {/* Batch History */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          Batch History
        </h2>

        {isLoading ? (
          <div className="text-center py-8 text-gray-500">Loading...</div>
        ) : !batches || batches.length === 0 ? (
          <div className="text-center py-8 text-gray-500">
            <Upload className="h-12 w-12 mx-auto mb-4 text-gray-300" />
            <p>No batch uploads yet.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Batch #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    File
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
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200">
                {batches.map((batch: Batch) => (
                  <tr key={batch.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3">
                      <button
                        onClick={() =>
                          setExpandedBatch(
                            expandedBatch === batch.id ? null : batch.id
                          )
                        }
                        className="text-primary-600 hover:text-primary-700 font-medium"
                      >
                        {batch.batch_number}
                      </button>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {batch.original_filename}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium capitalize ${getStatusBadge(
                          batch.status
                        )}`}
                      >
                        {getStatusIcon(batch.status)}
                        {batch.status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      {batch.successful_records}/{batch.total_records}
                      {batch.failed_records > 0 && (
                        <span className="text-red-500 ml-1">
                          ({batch.failed_records} failed)
                        </span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {new Date(batch.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        {batch.status === 'pending' && (
                          <>
                            <button
                              onClick={() => processMutation.mutate(batch.id)}
                              className="text-green-600 hover:text-green-700"
                              title="Start Processing"
                            >
                              <Play className="h-4 w-4" />
                            </button>
                            <button
                              onClick={() => cancelMutation.mutate(batch.id)}
                              className="text-red-600 hover:text-red-700"
                              title="Cancel"
                            >
                              <Trash2 className="h-4 w-4" />
                            </button>
                          </>
                        )}
                        {batch.status === 'processing' && (
                          <button
                            onClick={() => cancelMutation.mutate(batch.id)}
                            className="text-red-600 hover:text-red-700"
                            title="Cancel"
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                        )}
                      </div>
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
