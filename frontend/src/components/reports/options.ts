import type { Report, ReportType } from '../../api/reports'

export const TYPE_LABELS: Record<ReportType, string> = {
  subject_comment: 'Nhận xét môn',
  school_record: 'Nhận xét học bạ',
  contact_slip: 'Phiếu liên lạc',
  report: 'Báo cáo lớp / khối',
}

export const TYPE_HINTS: Record<ReportType, string> = {
  subject_comment: 'Nhận xét một môn của từng học sinh, do giáo viên bộ môn viết.',
  school_record: 'Nhận xét chung cuối học kỳ của từng học sinh, do giáo viên chủ nhiệm viết.',
  contact_slip: 'Phiếu gửi phụ huynh: bảng điểm, chuyên cần và nhận xét. Xuất PDF sau khi duyệt.',
  report: 'Báo cáo tổng hợp số liệu của một lớp hoặc một khối, không nêu tên học sinh.',
}

// Mã vi phạm của bộ kiểm tự động (backend/app/reports/checks.py) diễn đạt cho giáo viên.
export const CHECK_LABELS: Record<string, string> = {
  bad_format: 'phản hồi của AI không đúng định dạng',
  missing_section: 'thiếu một trong ba phần (điểm mạnh, cần cố gắng, gợi ý)',
  number_not_in_data: 'có số không nằm trong dữ liệu của hệ thống',
  banned_negative: 'có từ ngữ gắn nhãn tiêu cực',
  banned_comparison: 'có so sánh với bạn khác hoặc với lớp',
  banned_family: 'có nhắc tới hoàn cảnh gia đình',
  student_identity: 'có tên hoặc mã của học sinh',
  markdown: 'có định dạng không hợp lệ',
  too_short: 'quá ngắn',
  too_long: 'quá dài',
}

// Lý do một lần sinh cả lớp dừng giữa chừng (error_code của công việc).
export const JOB_ERRORS: Record<string, string> = {
  llm_error:
    'Mô hình AI không phản hồi hoặc đã hết hạn mức. Phần đã viết được giữ lại; hãy thử tiếp sau ít phút (gói miễn phí có thể phải chờ tới ngày mai).',
  interrupted: 'Quá trình bị gián đoạn (máy chủ khởi động lại). Phần đã viết được giữ lại.',
  forbidden: 'Quyền của tài khoản đã thay đổi nên việc sinh bị dừng.',
  unsafe_payload: 'Hệ thống chặn việc gửi dữ liệu cho AI vì còn thông tin nhận diện học sinh.',
  internal_error: 'Có lỗi bất ngờ trong máy chủ. Phần đã viết được giữ lại.',
}

// Trạng thái của một dòng trong danh sách: chưa có, bản nháp AI, chờ tự viết, đã duyệt.
export type RowState = 'none' | 'draft' | 'manual' | 'approved'

export function stateOf(report: Report | null): RowState {
  if (report === null) return 'none'
  if (report.status === 'approved') return 'approved'
  return report.needs_manual ? 'manual' : 'draft'
}

export const STATE_LABELS: Record<RowState, string> = {
  none: 'Chưa có',
  draft: 'Bản nháp',
  manual: 'Cần tự viết',
  approved: 'Đã duyệt',
}

export const STATE_BADGES: Record<RowState, string> = {
  none: 'badge-neutral',
  draft: 'badge-fair',
  manual: 'badge-pass',
  approved: 'badge-good',
}

export function describeChecks(notes: string[]): string {
  const labels = notes.map((code) => CHECK_LABELS[code]).filter((label) => label !== undefined)
  return labels.length > 0 ? labels.join('; ') : 'không đạt kiểm tra tự động'
}
