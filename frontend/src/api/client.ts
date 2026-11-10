/**
 * api/client.ts – Typed fetch client for the Resume Screener API.
 */

import type {
  AnalysisCreate,
  AnalysisDetail,
  AnalysisFilterParams,
  AnalysisListResponse,
  ResumeUploadResponse,
} from './types'

// Reads backend URL from environment
// Defaults to empty string in local development so Vite's dev proxy handles /api.
const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let errorMessage = `HTTP ${res.status}`
    try {
      const errorData = await res.json()
      if (errorData && typeof errorData.detail === 'string') {
        errorMessage = errorData.detail
      }
    } catch {
      // Non-JSON response body; fallback to status text
      errorMessage = res.statusText || errorMessage
    }
    throw new ApiError(res.status, errorMessage)
  }

  // 204 No Content has no body
  if (res.status === 204) {
    return undefined as unknown as T
  }

  return res.json() as Promise<T>
}

/**
 * Screen a candidate resume against a job description.
 */
export async function createAnalysis(payload: AnalysisCreate): Promise<AnalysisDetail> {
  const res = await fetch(`${API_BASE_URL}/api/analyses`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return handleResponse<AnalysisDetail>(res)
}

/**
 * List historical analyses with search and score range filters.
 */
export async function getAnalyses(
  params?: AnalysisFilterParams
): Promise<AnalysisListResponse> {
  const query = new URLSearchParams()

  if (params?.search && params.search.trim()) {
    query.set('search', params.search.trim())
  }
  if (params?.min_score !== undefined && params.min_score !== null) {
    query.set('min_score', String(params.min_score))
  }
  if (params?.max_score !== undefined && params.max_score !== null) {
    query.set('max_score', String(params.max_score))
  }
  if (params?.limit !== undefined) {
    query.set('limit', String(params.limit))
  }
  if (params?.offset !== undefined) {
    query.set('offset', String(params.offset))
  }

  const qs = query.toString()
  const url = qs ? `${API_BASE_URL}/api/analyses?${qs}` : `${API_BASE_URL}/api/analyses`

  const res = await fetch(url, { method: 'GET' })
  return handleResponse<AnalysisListResponse>(res)
}

/**
 * Retrieve a single detailed analysis record by primary key ID.
 */
export async function getAnalysisById(id: number): Promise<AnalysisDetail> {
  const res = await fetch(`${API_BASE_URL}/api/analyses/${id}`, { method: 'GET' })
  return handleResponse<AnalysisDetail>(res)
}

/**
 * Delete a past analysis record by ID.
 */
export async function deleteAnalysis(id: number): Promise<void> {
  const res = await fetch(`${API_BASE_URL}/api/analyses/${id}`, { method: 'DELETE' })
  return handleResponse<void>(res)
}

/**
 * Upload a resume file (.pdf, .docx, .txt) and return extracted text for preview.
 */
export async function uploadResumeFile(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const res = await fetch(`${API_BASE_URL}/api/analyses/upload`, {
    method: 'POST',
    body: formData,
  })
  return handleResponse<ResumeUploadResponse>(res)
}

