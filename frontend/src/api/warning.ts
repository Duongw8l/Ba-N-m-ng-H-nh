import { apiGet, apiPatch } from './client'

// Khớp schema của back-end (backend/app/warning/schemas.py). Cảnh báo chỉ là gợi ý để giáo viên
// quyết định; không tự gửi tới học sinh hay phụ huynh.
export type RiskLevel = 'high' | 'medium' | 'low'
export type TeacherStatus = 'new' | 'contacted' | 'false_alarm'

export interface AlertReason {
  code: string
  level: RiskLevel
  message: string
}

export interface ModelFactor {
  feature: string
  label: string
  value: number
  contribution: number
  message: string
}

export interface ModelInfo {
  version: string
  probability: number
  factors: ModelFactor[]
}

export interface AlertCounts {
  high: number
  medium: number
  low: number
}

interface AlertBase {
  id: number
  level: RiskLevel
  risk_score: number | null
  rules: AlertReason[]
  model: ModelInfo | null
  top_reasons: string[]
  teacher_status: TeacherStatus
  created_at: string
  as_of: string | null
}

export interface Alert extends AlertBase {
  student: { id: number; student_code: string; full_name: string }
  class_id: number
  class_name: string
}

export type ProfileAlert = AlertBase

export interface ClassAlerts {
  class_id: number
  class_name: string
  counts: AlertCounts
  alerts: Alert[]
}

export interface SchoolAlerts {
  counts: AlertCounts
  alerts: Alert[]
}

export function fetchClassAlerts(classId: number, signal?: AbortSignal) {
  return apiGet<ClassAlerts>(`/classes/${classId}/alerts`, signal)
}

export function fetchSchoolAlerts(level: RiskLevel, signal?: AbortSignal) {
  return apiGet<SchoolAlerts>(`/alerts?level=${level}`, signal)
}

export function updateAlert(alertId: number, status: TeacherStatus) {
  return apiPatch<Alert>(`/alerts/${alertId}`, { teacher_status: status })
}
