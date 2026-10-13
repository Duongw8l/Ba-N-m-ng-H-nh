import { Icon } from '../Icon'

const STEPS = ['Chọn tệp', 'Xem trước', 'Xác nhận']

// Chỉ báo bước của luồng nhập: 1 chọn tệp, 2 xem trước, 3 xác nhận; 4 là đã xong tất cả.
export function Stepper({ current }: { current: 1 | 2 | 3 | 4 }) {
  return (
    <ol aria-label="Các bước nhập dữ liệu" className="flex items-center gap-2 text-sm">
      {STEPS.map((label, index) => {
        const number = index + 1
        const done = number < current
        const active = number === current
        return (
          <li
            key={label}
            aria-current={active ? 'step' : undefined}
            className="flex flex-1 items-center gap-2 last:flex-none"
          >
            <span
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-semibold transition-colors ${
                done
                  ? 'bg-brand-700 text-white'
                  : active
                    ? 'bg-tint text-tint-text ring-2 ring-brand-500'
                    : 'bg-slate-200 text-slate-600'
              }`}
            >
              {done ? <Icon name="check" className="h-4 w-4" /> : number}
            </span>
            <span className={active ? 'font-semibold' : done ? 'text-slate-700' : 'text-slate-500'}>
              {label}
            </span>
            {index < STEPS.length - 1 && (
              <span
                aria-hidden="true"
                className={`h-px flex-1 ${done ? 'bg-brand-600' : 'bg-slate-200'}`}
              />
            )}
          </li>
        )
      })}
    </ol>
  )
}
