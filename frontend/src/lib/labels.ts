// Nhãn tiếng Việt cho các giá trị mà back-end trả (mã tiếng Anh). Không ghi cứng ngưỡng điểm hay số
// buổi nghỉ trong nhãn: các ngưỡng lấy từ API (`thresholds`, `absence_limits`) khi cần hiện số.
import type { Period } from '../api/analytics'
import type { RiskLevel, TeacherStatus } from '../api/warning'

export const LEVEL_KEYS = ['good', 'fair', 'pass', 'fail'] as const

export const LEVEL_LABELS: Record<string, string> = {
  good: 'Tốt',
  fair: 'Khá',
  pass: 'Đạt',
  fail: 'Chưa đạt',
  incomplete: 'Chưa đủ dữ liệu',
  missing: 'Chưa có dữ liệu',
}

// Màu biểu đồ lấy từ biến CSS (index.css) nên tự đổi theo chế độ sáng/tối; luôn đi kèm nhãn chữ và số
// nên không chỉ dựa vào màu.
export const LEVEL_COLORS: Record<string, string> = {
  good: 'var(--chart-good)',
  fair: 'var(--chart-fair)',
  pass: 'var(--chart-pass)',
  fail: 'var(--chart-fail)',
  incomplete: 'var(--chart-neutral)',
  missing: 'var(--chart-muted)',
}

export const PERIOD_LABELS: Record<Period, string> = {
  '1': 'Học kỳ I',
  '2': 'Học kỳ II',
  year: 'Cả năm',
}

export const ATTENTION_LABELS: Record<string, string> = {
  absent_over_limit: 'Nghỉ quá số buổi tối đa',
  absent_notice: 'Nghỉ nhiều, cần nhắc',
  subject_below_fail: 'Có môn điểm quá thấp',
  level_fail: 'Kết quả học tập Chưa đạt',
}

export const PROMOTION_REASON_LABELS: Record<string, string> = {
  learning_fail: 'Kết quả học tập cả năm Chưa đạt',
  conduct_fail: 'Rèn luyện cả năm Chưa đạt',
  absent_over_limit: 'Nghỉ quá số buổi tối đa',
  missing_data: 'Thiếu dữ liệu để kết luận',
}

export const RETAKE_REASON_LABELS: Record<string, string> = {
  below_pass: 'ĐTB cả năm dưới mức Đạt',
  comment_fail: 'Nhận xét cả năm Chưa đạt',
}

export const COMMENT_LABELS: Record<string, string> = {
  pass: 'Đạt',
  fail: 'Chưa đạt',
}

export function levelLabel(level: string | null | undefined, fallback = 'Chưa có dữ liệu'): string {
  return level ? (LEVEL_LABELS[level] ?? level) : fallback
}

// Cảnh báo sớm (Giai đoạn 6). Từ ngữ trung tính: "cần hỗ trợ", không gắn nhãn học sinh.
export const RISK_LABELS: Record<RiskLevel, string> = {
  high: 'Mức cao',
  medium: 'Mức trung bình',
  low: 'Mức thấp',
}

// Lớp nhãn (huy hiệu) trong index.css.
export const RISK_STYLES: Record<RiskLevel, string> = {
  high: 'badge-high',
  medium: 'badge-medium',
  low: 'badge-low',
}

export const TEACHER_STATUS_LABELS: Record<TeacherStatus, string> = {
  new: 'Chưa xử lý',
  contacted: 'Đã trao đổi',
  false_alarm: 'Báo nhầm',
}
