// Hiển thị số kiểu Việt Nam: điểm "6,5", số nguyên "1.234", phần trăm "12,5%".
// Đây chỉ là định dạng: mọi con số (ĐTB, mức, số đếm) do back-end tính (nguyên tắc 1).
const SCORE = new Intl.NumberFormat('vi-VN', { minimumFractionDigits: 1, maximumFractionDigits: 1 })
const INTEGER = new Intl.NumberFormat('vi-VN')
const PERCENT = new Intl.NumberFormat('vi-VN', { maximumFractionDigits: 1 })

export const EMPTY = '—'

export function formatScore(value: number | null | undefined): string {
  return value === null || value === undefined ? EMPTY : SCORE.format(value)
}

export function formatInt(value: number): string {
  return INTEGER.format(value)
}

// Tỉ lệ chỉ để hiển thị, từ số đếm và sĩ số do API trả (không phải số của Thông tư).
export function formatPercent(count: number, total: number): string {
  return total > 0 ? `${PERCENT.format((count / total) * 100)}%` : EMPTY
}

// "2027-03" thành "Tháng 3/2027".
export function formatMonth(month: string): string {
  const [year, number] = month.split('-')
  return `Tháng ${Number(number)}/${year}`
}

// "2027-03" thành "T3" cho trục biểu đồ hẹp.
export function formatMonthShort(month: string): string {
  return `T${Number(month.split('-')[1])}`
}
