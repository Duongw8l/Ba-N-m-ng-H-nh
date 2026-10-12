// Hiển thị giá trị của bản xem trước theo kiểu Việt Nam (điểm "6,5", ngày dd/mm/yyyy, nhãn tiếng Việt).
import type { ConductPeriod, ImportKind } from '../../api/imports'

export const KIND_LABELS: Record<ImportKind, string> = {
  assessments: 'Điểm',
  attendance: 'Điểm danh',
  conduct: 'Rèn luyện',
}

export const PERIOD_LABELS: Record<ConductPeriod, string> = {
  hk1: 'Học kỳ I',
  hk2: 'Học kỳ II',
  year: 'Cả năm',
}

const VALUE_LABELS: Record<string, Record<string, string>> = {
  status: {
    present: 'Có mặt',
    absent_excused: 'Nghỉ có phép',
    absent_unexcused: 'Nghỉ không phép',
    late: 'Muộn',
  },
  level: { good: 'Tốt', fair: 'Khá', pass: 'Đạt', fail: 'Chưa đạt' },
  comment_result: { pass: 'Đạt', fail: 'Chưa đạt' },
}

const SCORE_FIELD = /^(tx\d+|midterm|final)$/
const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

export function formatValue(field: string, value: string | null | undefined): string {
  if (value === null || value === undefined || value === '') return '—'
  if (SCORE_FIELD.test(field)) return value.replace('.', ',')
  if (field === 'date') {
    const match = ISO_DATE.exec(value)
    return match ? `${match[3]}/${match[2]}/${match[1]}` : value
  }
  return VALUE_LABELS[field]?.[value] ?? value
}
