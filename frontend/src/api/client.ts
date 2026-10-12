// Gọi REST API của back-end. Đường dẫn tương đối /api/v1 đi qua proxy của Vite (khi phát triển)
// hoặc reverse proxy (khi triển khai), nên trình duyệt không cần CORS.
import { getToken } from '../auth/tokenStore'

const API_BASE = '/api/v1'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

interface RequestOptions {
  signal?: AbortSignal
  // false: không gửi token (đăng nhập) và gặp 401 thì không coi là hết phiên.
  authenticated?: boolean
}

// AuthProvider đăng ký: gọi khi một yêu cầu CÓ token bị trả 401 (token hết hạn hoặc không còn hợp lệ).
let onUnauthorized: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null): void {
  onUnauthorized = handler
}

// Lấy thông điệp tiếng Việt do back-end trả ({"detail": "..."}); không có thì dùng câu chung.
async function errorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json()
    if (typeof body === 'object' && body !== null && 'detail' in body) {
      const { detail } = body
      if (typeof detail === 'string') return detail
    }
  } catch {
    // Thân phản hồi không phải JSON.
  }
  return `Yêu cầu tới máy chủ thất bại (HTTP ${response.status})`
}

async function request<T>(
  method: 'GET' | 'POST',
  path: string,
  body: unknown,
  options: RequestOptions,
): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = options.authenticated === false ? null : getToken()
  if (token) headers.Authorization = `Bearer ${token}`
  // FormData: không tự đặt Content-Type, để trình duyệt thêm ranh giới (boundary) của multipart.
  const isForm = body instanceof FormData
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json'

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    signal: options.signal,
  })
  if (!response.ok) {
    if (response.status === 401 && token) onUnauthorized?.()
    throw new ApiError(response.status, await errorMessage(response))
  }
  return (await response.json()) as T
}

export function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>('GET', path, undefined, { signal })
}

export function apiPost<T>(path: string, body: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>('POST', path, body, options)
}

// Tải tệp lên (multipart/form-data).
export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>('POST', path, form, {})
}
