import type { AbsenceLimits } from '../api/analytics'

interface AbsenceMeterProps {
  total: number
  limits: AbsenceLimits
}

// Thanh số buổi nghỉ so với ngưỡng nhắc và số buổi tối đa; hai ngưỡng lấy từ API (settings). Độ dài
// thanh chỉ là hình ảnh; con số và nhãn chữ mới là thông tin.
export function AbsenceMeter({ total, limits }: AbsenceMeterProps) {
  const scale = Math.max(limits.maximum, total)
  const percent = (value: number) => `${Math.min(100, (value / scale) * 100)}%`
  const over = total > limits.maximum
  const warn = total >= limits.notice
  const color = over ? 'bg-red-600' : warn ? 'bg-amber-500' : 'bg-brand-500'
  const status = over
    ? 'Đã quá số buổi nghỉ tối đa'
    : warn
      ? 'Đã tới ngưỡng cần nhắc'
      : 'Dưới ngưỡng cần nhắc'

  return (
    <div>
      <div
        role="meter"
        aria-label="Số buổi nghỉ trong năm học"
        aria-valuemin={0}
        aria-valuemax={scale}
        aria-valuenow={total}
        aria-valuetext={`${total} buổi, ${status}`}
        className="relative h-2.5 w-full rounded-full bg-slate-100"
      >
        <div className={`h-full rounded-full ${color}`} style={{ width: percent(total) }} />
        <span
          aria-hidden="true"
          className="absolute top-[-4px] h-[18px] w-0.5 rounded-full bg-amber-600"
          style={{ left: percent(limits.notice) }}
        />
        <span
          aria-hidden="true"
          className="absolute top-[-4px] h-[18px] w-0.5 rounded-full bg-red-600"
          style={{ left: percent(limits.maximum) }}
        />
      </div>
      <p className="mt-2 text-xs text-slate-600">
        {total} buổi · nhắc từ {limits.notice} buổi · tối đa {limits.maximum} buổi. {status}.
      </p>
    </div>
  )
}
