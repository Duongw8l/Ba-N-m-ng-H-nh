import type { Period } from '../api/analytics'
import { PERIOD_LABELS } from '../lib/labels'

interface PeriodSelectProps {
  value: Period
  options: readonly Period[]
  onChange: (period: Period) => void
}

export function PeriodSelect({ value, options, onChange }: PeriodSelectProps) {
  return (
    <label className="flex items-center gap-2 text-sm font-medium text-slate-700">
      Kỳ xem
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as Period)}
        className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-base"
      >
        {options.map((option) => (
          <option key={option} value={option}>
            {PERIOD_LABELS[option]}
          </option>
        ))}
      </select>
    </label>
  )
}
