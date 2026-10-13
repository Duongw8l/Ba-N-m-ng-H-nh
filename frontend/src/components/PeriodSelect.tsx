import type { Period } from '../api/analytics'
import { PERIOD_LABELS } from '../lib/labels'

interface PeriodSelectProps {
  value: Period
  options: readonly Period[]
  onChange: (period: Period) => void
}

// Chọn kỳ xem (học kỳ I, II, cả năm) dạng nút phân đoạn; giá trị nằm trong ?semester= của URL.
export function PeriodSelect({ value, options, onChange }: PeriodSelectProps) {
  return (
    <div className="flex items-center gap-2">
      <span id="ky-xem" className="text-sm font-medium text-slate-500">
        Kỳ xem
      </span>
      <div
        role="radiogroup"
        aria-labelledby="ky-xem"
        className="flex rounded-xl border border-slate-200 bg-slate-100/70 p-0.5"
      >
        {options.map((option) => {
          const active = option === value
          return (
            <button
              key={option}
              type="button"
              role="radio"
              aria-checked={active}
              onClick={() => onChange(option)}
              className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
                active
                  ? 'bg-surface text-brand-700 shadow-sm dark:text-brand-300'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              {PERIOD_LABELS[option]}
            </button>
          )
        })}
      </div>
    </div>
  )
}
