import { apiGet, apiPatch, apiUpload } from './client'

// Khớp schema của back-end (backend/app/rag/schemas.py).
export type RegulationStatus = 'active' | 'expired'

export interface RegulationDocument {
  id: number
  name: string
  file_name: string
  status: RegulationStatus
  status_label: string
  created_at: string
  expired_at: string | null
  article_count: number
  chunk_count: number
}

export interface SearchHit {
  document_id: number
  document_name: string
  article: string | null
  clause: string | null
  content: string
  similarity: number
}

export interface RegulationSearch {
  found: boolean
  message: string | null
  hits: SearchHit[]
  best_similarity: number | null
  min_similarity: number
}

export function fetchRegulations(signal?: AbortSignal): Promise<RegulationDocument[]> {
  return apiGet<RegulationDocument[]>('/admin/regulations', signal)
}

// Tải văn bản lên: back-end đọc, tách Điều/Khoản và tính vector trong cùng một yêu cầu (vài chục giây).
export function uploadRegulation(name: string, file: File): Promise<RegulationDocument> {
  const form = new FormData()
  form.append('name', name)
  form.append('file', file)
  return apiUpload<RegulationDocument>('/admin/regulations', form)
}

export function setRegulationStatus(
  id: number,
  status: RegulationStatus,
): Promise<RegulationDocument> {
  return apiPatch<RegulationDocument>(`/admin/regulations/${id}`, { status })
}

export function searchRegulations(
  question: string,
  signal?: AbortSignal,
): Promise<RegulationSearch> {
  return apiGet<RegulationSearch>(`/regulations/search?q=${encodeURIComponent(question)}`, signal)
}
