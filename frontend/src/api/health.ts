import { apiGet } from './client'

// Khớp schema HealthResponse của back-end (backend/app/core/health.py).
export interface HealthResponse {
  status: 'ok'
  db: boolean
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/health', signal)
}
