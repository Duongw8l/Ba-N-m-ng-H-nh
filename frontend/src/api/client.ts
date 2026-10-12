// Gọi REST API của back-end. Đường dẫn tương đối /api/v1 đi qua proxy của Vite (khi phát triển)
// hoặc reverse proxy (khi triển khai), nên trình duyệt không cần CORS.
const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { Accept: 'application/json' },
    signal,
  })
  if (!response.ok) {
    throw new ApiError(response.status, `Yêu cầu tới máy chủ thất bại (HTTP ${response.status})`)
  }
  return (await response.json()) as T
}
