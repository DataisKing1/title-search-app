import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { searchesApi, getErrorMessage } from '@/lib/api'
import toast from 'react-hot-toast'
import { ArrowLeft } from 'lucide-react'
import { Link } from 'react-router-dom'

const COLORADO_COUNTIES = [
  'Adams', 'Alamosa', 'Arapahoe', 'Archuleta', 'Baca', 'Bent', 'Boulder',
  'Broomfield', 'Chaffee', 'Cheyenne', 'Clear Creek', 'Conejos', 'Costilla',
  'Crowley', 'Custer', 'Delta', 'Denver', 'Dolores', 'Douglas', 'Eagle',
  'El Paso', 'Elbert', 'Fremont', 'Garfield', 'Gilpin', 'Grand', 'Gunnison',
  'Hinsdale', 'Huerfano', 'Jackson', 'Jefferson', 'Kiowa', 'Kit Carson',
  'La Plata', 'Lake', 'Larimer', 'Las Animas', 'Lincoln', 'Logan', 'Mesa',
  'Mineral', 'Moffat', 'Montezuma', 'Montrose', 'Morgan', 'Otero', 'Ouray',
  'Park', 'Phillips', 'Pitkin', 'Prowers', 'Pueblo', 'Rio Blanco', 'Rio Grande',
  'Routt', 'Saguache', 'San Juan', 'San Miguel', 'Sedgwick', 'Summit', 'Teller',
  'Washington', 'Weld', 'Yuma'
]

export default function NewSearch() {
  const navigate = useNavigate()
  const [formData, setFormData] = useState({
    street_address: '',
    city: '',
    county: '',
    state: 'CO',
    zip_code: '',
    parcel_number: '',
    search_type: 'full',
    search_years: 40,
    priority: 'normal',
  })

  const [errors, setErrors] = useState<Record<string, string>>({})

  const createMutation = useMutation({
    mutationFn: searchesApi.create,
    onSuccess: (data) => {
      toast.success('Search created successfully!')
      navigate(`/searches/${data.id}`)
    },
    onError: (error) => {
      const message = getErrorMessage(error, 'Failed to create search')
      toast.error(message)
    },
  })

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {}

    // Street address validation
    if (!formData.street_address.trim()) {
      newErrors.street_address = 'Street address is required'
    } else if (formData.street_address.trim().length < 5) {
      newErrors.street_address = 'Street address must be at least 5 characters'
    }

    // City validation
    if (!formData.city.trim()) {
      newErrors.city = 'City is required'
    } else if (formData.city.trim().length < 2) {
      newErrors.city = 'City must be at least 2 characters'
    }

    // County validation
    if (!formData.county) {
      newErrors.county = 'County is required'
    }

    // ZIP code validation (if provided)
    if (formData.zip_code && !/^\d{5}(-\d{4})?$/.test(formData.zip_code)) {
      newErrors.zip_code = 'Invalid ZIP code format (e.g., 80202 or 80202-1234)'
    }

    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      toast.error('Please fix the form errors')
      return
    }

    createMutation.mutate(formData)
  }

  const handleChange = (
    e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>
  ) => {
    const { name, value } = e.target
    setFormData((prev) => ({
      ...prev,
      [name]: name === 'search_years' ? parseInt(value) : value,
    }))
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link to="/searches" className="p-2 hover:bg-gray-100 rounded-lg">
          <ArrowLeft className="h-5 w-5" />
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">New Title Search</h1>
      </div>

      <form onSubmit={handleSubmit} className="max-w-2xl">
        {/* Property Information */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Property Information
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="md:col-span-2">
              <label className="label">Street Address *</label>
              <input
                type="text"
                name="street_address"
                value={formData.street_address}
                onChange={handleChange}
                required
                className={`input ${errors.street_address ? 'border-red-500' : ''}`}
                placeholder="123 Main Street"
              />
              {errors.street_address && (
                <p className="text-red-500 text-sm mt-1">{errors.street_address}</p>
              )}
            </div>

            <div>
              <label className="label">City *</label>
              <input
                type="text"
                name="city"
                value={formData.city}
                onChange={handleChange}
                required
                className={`input ${errors.city ? 'border-red-500' : ''}`}
                placeholder="Denver"
              />
              {errors.city && (
                <p className="text-red-500 text-sm mt-1">{errors.city}</p>
              )}
            </div>

            <div>
              <label className="label">County *</label>
              <select
                name="county"
                value={formData.county}
                onChange={handleChange}
                required
                className={`input ${errors.county ? 'border-red-500' : ''}`}
              >
                <option value="">Select County</option>
                {COLORADO_COUNTIES.map((county) => (
                  <option key={county} value={county}>
                    {county}
                  </option>
                ))}
              </select>
              {errors.county && (
                <p className="text-red-500 text-sm mt-1">{errors.county}</p>
              )}
            </div>

            <div>
              <label className="label">State</label>
              <input
                type="text"
                name="state"
                value={formData.state}
                disabled
                className="input bg-gray-50"
              />
            </div>

            <div>
              <label className="label">ZIP Code</label>
              <input
                type="text"
                name="zip_code"
                value={formData.zip_code}
                onChange={handleChange}
                className={`input ${errors.zip_code ? 'border-red-500' : ''}`}
                placeholder="80202"
              />
              {errors.zip_code && (
                <p className="text-red-500 text-sm mt-1">{errors.zip_code}</p>
              )}
            </div>

            <div className="md:col-span-2">
              <label className="label">Parcel/APN Number (if known)</label>
              <input
                type="text"
                name="parcel_number"
                value={formData.parcel_number}
                onChange={handleChange}
                className="input"
                placeholder="123-45-678"
              />
            </div>
          </div>
        </div>

        {/* Search Options */}
        <div className="card mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">
            Search Options
          </h2>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="label">Search Type</label>
              <select
                name="search_type"
                value={formData.search_type}
                onChange={handleChange}
                className="input"
              >
                <option value="full">Full Search</option>
                <option value="limited">Limited Search</option>
                <option value="update">Update/Bring Down</option>
              </select>
            </div>

            <div>
              <label className="label">Search Years</label>
              <select
                name="search_years"
                value={formData.search_years}
                onChange={handleChange}
                className="input"
              >
                <option value={20}>20 Years</option>
                <option value={30}>30 Years</option>
                <option value={40}>40 Years</option>
                <option value={50}>50 Years</option>
                <option value={60}>60 Years</option>
              </select>
            </div>

            <div>
              <label className="label">Priority</label>
              <select
                name="priority"
                value={formData.priority}
                onChange={handleChange}
                className="input"
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
            </div>
          </div>
        </div>

        {/* Submit */}
        <div className="flex gap-4">
          <button
            type="submit"
            disabled={createMutation.isPending}
            className="btn btn-primary disabled:opacity-50"
          >
            {createMutation.isPending ? 'Creating...' : 'Create Search'}
          </button>
          <Link to="/searches" className="btn btn-secondary">
            Cancel
          </Link>
        </div>
      </form>
    </div>
  )
}
