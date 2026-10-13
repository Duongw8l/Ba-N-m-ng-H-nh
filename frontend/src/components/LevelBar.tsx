import { formatPercent } from '../lib/format'
import { LEVEL_COLORS, LEVEL_LABELS } from '../lib/labels'

interface LevelBarProps {
  counts: Record<string, number>
  keys: readonly string[]
  total: number
}

// Thanh chia theo tỉ lệ các mức, kèm chú giải chữ có số đếm và phần trăm (không chỉ dựa vào màu).
// Tỉ lệ chỉ để hiển thị, tính từ số đếm và sĩ số do API trả.
export function LevelBar({ counts, keys, total }: LevelBarProps) {
  return (
    <div>
      <div
        className="flex h-2.5 w-full gap-0.5 overflow-hidden rounded-full bg-slate-100"
        role="img"
        aria-label={keys.map((key) => `${LEVEL_LABELS[key]}: ${counts[key] ?? 0}`).join(', ')}
      >
        {keys.map((key) => {
          const count = counts[key] ?? 0
          return count > 0 && total > 0 ? (
            <span
              key={key}
              style={{ width: `${(count / total) * 100}%`, backgroundColor: LEVEL_COLORS[key] }}
            />
          ) : null
        })}
      </div>
      <ul className="mt-2 grid grid-cols-2 gap-x-3 gap-y-1 text-xs text-slate-600">
        {keys.map((key) => (
          <li key={key} className="flex items-center gap-1.5">
            <span
              aria-hidden="true"
              className="inline-block h-2.5 w-2.5 shrink-0 rounded-sm"
              style={{ backgroundColor: LEVEL_COLORS[key] }}
            />
            <span>
              {LEVEL_LABELS[key]}: <strong className="tabular-nums">{counts[key] ?? 0}</strong>{' '}
              ({formatPercent(counts[key] ?? 0, total)})
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
