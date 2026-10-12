import { apiGet, apiPost, apiUpload } from './client'

// Khớp schema của back-end (backend/app/imports/schemas.py).
export type ImportKind = 'assessments' | 'attendance' | 'conduct'
export type ConductPeriod = 'hk1' | 'hk2' | 'year'
export type RowStatus = 'ok' | 'warning' | 'error'
export type RowAction = 'new' | 'changed' | 'unchanged'

export interface PreviewMessage {
  column: string | null
  message: string
}

export interface PreviewRow {
  line: number
  student_code: string
  full_name: string | null
  status: RowStatus
  action: RowAction | null
  values: Record<string, string | null>
  existing: Record<string, string | null>
  messages: PreviewMessage[]
}

export interface ImportField {
  name: string
  label: string
  required: boolean
  column: string | null
}

export interface PreviewSummary {
  total_rows: number
  error_rows: number
  warning_rows: number
  new_rows: number
  changed_rows: number
  unchanged_rows: number
  records_to_create: number
  records_to_update: number
  records_unchanged: number
  has_changes: boolean
}

export interface ImportPreview {
  job_id: string | null
  kind: ImportKind
  class_id: number
  subject: { id: number; name: string } | null
  semester: number | null
  period: ConductPeriod | null
  file_name: string
  header_line: number
  detected_columns: string[]
  fields: ImportField[]
  missing_required: string[]
  ignored_columns: string[]
  notes: string[]
  summary: PreviewSummary
  can_confirm: boolean
  expires_at: string | null
  rows: PreviewRow[]
  truncated: boolean
}

export interface ConfirmResult {
  job_id: string
  status: 'previewed' | 'confirmed'
  created: number
  updated: number
  unchanged: number
  already_confirmed: boolean
}

export interface MappingTemplate {
  name: string
  kind: ImportKind
  mapping: Record<string, string | null>
  header_row: number | null
}

export interface PreviewRequest {
  classId: number
  kind: ImportKind
  file: File
  subjectId?: number
  semester?: number
  period?: ConductPeriod
  allowPartial?: boolean
  // Tuỳ chọn khi chỉnh cột: ánh xạ tay, mẫu đã lưu, tên mẫu mới, dòng tiêu đề.
  mapping?: Record<string, string | null>
  mappingName?: string
  saveMappingAs?: string
  headerRow?: number
}

// Tải tệp lên và nhận bản xem trước. Chưa ghi gì vào dữ liệu của lớp.
export function uploadPreview(request: PreviewRequest): Promise<ImportPreview> {
  const form = new FormData()
  form.append('file', request.file)
  if (request.subjectId !== undefined) form.append('subject_id', String(request.subjectId))
  if (request.semester !== undefined) form.append('semester', String(request.semester))
  if (request.period !== undefined) form.append('period', request.period)
  if (request.allowPartial) form.append('allow_partial', 'true')
  if (request.mapping !== undefined) form.append('mapping', JSON.stringify(request.mapping))
  if (request.mappingName) form.append('mapping_name', request.mappingName)
  if (request.saveMappingAs) form.append('save_mapping_as', request.saveMappingAs)
  if (request.headerRow !== undefined) form.append('header_row', String(request.headerRow))
  return apiUpload<ImportPreview>(`/classes/${request.classId}/import/${request.kind}`, form)
}

export function confirmImport(jobId: string): Promise<ConfirmResult> {
  return apiPost<ConfirmResult>(`/imports/${jobId}/confirm`, undefined)
}

export function fetchMappingTemplates(
  kind: ImportKind,
  signal?: AbortSignal,
): Promise<MappingTemplate[]> {
  return apiGet<MappingTemplate[]>(`/imports/mappings?kind=${kind}`, signal)
}
