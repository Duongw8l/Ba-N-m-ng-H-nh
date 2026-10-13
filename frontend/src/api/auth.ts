import { apiGet, apiPost } from './client'

// Khớp schema của back-end (backend/app/auth/schemas.py, backend/app/classes/schemas.py).
export type UserRole = 'teacher' | 'principal' | 'admin'

export interface AuthUser {
  id: number
  email: string
  full_name: string
  role: UserRole
}

export interface LoginResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
  user: AuthUser
}

export interface ClassRef {
  id: number
  name: string
  grade_level: number
}

export interface TeachingItem {
  class_id: number
  class_name: string
  grade_level: number
  subject_id: number
  subject_name: string
}

export interface Assignments {
  user: AuthUser
  homeroom_classes: ClassRef[]
  teaching: TeachingItem[]
  grades: number[]
}

export function login(email: string, password: string): Promise<LoginResponse> {
  return apiPost<LoginResponse>('/auth/login', { email, password }, { authenticated: false })
}

export function fetchAssignments(signal?: AbortSignal): Promise<Assignments> {
  return apiGet<Assignments>('/me/assignments', signal)
}

// Tự đổi mật khẩu của chính mình (mọi vai trò). Back-end trả {detail} khi xong.
export function changePassword(
  currentPassword: string,
  newPassword: string,
): Promise<{ detail: string }> {
  return apiPost<{ detail: string }>('/auth/change-password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}
