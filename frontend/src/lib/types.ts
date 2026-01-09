// Search types
export type SearchStatus =
  | 'pending'
  | 'queued'
  | 'scraping'
  | 'analyzing'
  | 'generating'
  | 'completed'
  | 'failed'
  | 'cancelled'

export type SearchPriority = 'low' | 'normal' | 'high' | 'urgent'

export interface Property {
  id: number
  street_address: string
  city: string
  county: string
  state: string
  zip_code: string | null
  parcel_number: string | null
  legal_description: string | null
}

export interface Search {
  id: number
  reference_number: string
  status: SearchStatus
  status_message: string | null
  progress_percent: number
  search_type: string
  search_years: number
  priority: SearchPriority
  property: Property
  document_count: number
  encumbrance_count: number
  created_at: string
  started_at: string | null
  completed_at: string | null
}

export interface SearchListResponse {
  items: Search[]
  total: number
  page: number
  page_size: number
  pages: number
}

// Document types
export type DocumentType =
  | 'deed'
  | 'mortgage'
  | 'deed_of_trust'
  | 'lien'
  | 'judgment'
  | 'easement'
  | 'plat'
  | 'survey'
  | 'tax_record'
  | 'court_filing'
  | 'ucc_filing'
  | 'lis_pendens'
  | 'bankruptcy'
  | 'release'
  | 'satisfaction'
  | 'assignment'
  | 'subordination'
  | 'other'

export type DocumentSource = 'county_recorder' | 'court_records' | 'commercial_api' | 'manual_upload'

export interface Document {
  id: number
  search_id: number
  document_type: DocumentType
  instrument_number: string | null
  recording_date: string | null
  grantor: string[]
  grantee: string[]
  source: DocumentSource
  file_name: string | null
  file_size: number | null
  ocr_confidence: number | null
  ai_summary: string | null
  needs_review: boolean
  created_at: string
}

// Report types
export type ReportStatus = 'draft' | 'review' | 'approved' | 'issued'

export interface Report {
  id: number
  search_id: number
  report_number: string
  report_type: string
  status: ReportStatus
  effective_date: string | null
  expiration_date: string | null
  risk_score: number | null
  risk_assessment_summary: string | null
  pdf_generated_at: string | null
  created_at: string
  updated_at: string
}

// Batch types
export type BatchStatus = 'pending' | 'processing' | 'completed' | 'partial' | 'failed' | 'cancelled'

export interface BatchItem {
  id: number
  row_number: number
  street_address: string | null
  city: string | null
  county: string | null
  parcel_number: string | null
  status: string
  error_message: string | null
  search_id: number | null
  processed_at: string | null
}

export interface Batch {
  id: number
  batch_number: string
  original_filename: string
  status: BatchStatus
  total_records: number
  processed_records: number
  successful_records: number
  failed_records: number
  created_at: string
  started_at: string | null
  completed_at: string | null
  items?: BatchItem[]
}

// County types
export interface County {
  id: number
  county_name: string
  state: string
  fips_code: string | null
  recorder_url: string | null
  scraping_enabled: boolean
  scraping_adapter: string | null
  is_healthy: boolean
  last_successful_scrape: string | null
  consecutive_failures: number
}

export interface CountyHealth {
  county_name: string
  is_healthy: boolean
  scraping_enabled: boolean
  last_successful_scrape: string | null
  last_failed_scrape: string | null
  consecutive_failures: number
  fallback_available: boolean
}
