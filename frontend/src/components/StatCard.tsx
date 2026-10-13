import type { ReactNode } from 'react'
import { Icon } from './Icon'
import type { IconName } from './Icon'

// Màu nhấn của biểu tượng; giá trị lớn vẫn do `valueClassName` quyết định (đỏ khi có cảnh báo...).
type Tone = 'brand' | 'good' | 'warn' | 'danger' | 'neutral'

const TONE_CLASS: Record<Tone, string> = {
  brand: 'bg-tint text-brand-700 dark:text-brand-300',
  good: 'bg-green-50 text-green-700',
  warn: 'bg-amber-50 text-amber-700',
  danger: 'bg-red-50 text-red-700',
  neutral: 'bg-slate-100 text-slate-500',
}

interface StatCardProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  valueClassName?: string
  icon?: IconName
  tone?: Tone
}

export function StatCard({
  label,
  value,
  hint,
  valueClassName = 'text-slate-900',
  icon,
  tone = 'brand',
}: StatCardProps) {
  return (
    <div className="card p-4 sm:p-5">
      <div className="flex items-start justify-between gap-3">
        <dt className="text-sm font-medium text-slate-500">{label}</dt>
        {icon && (
          <span
            className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${TONE_CLASS[tone]}`}
          >
            <Icon name={icon} className="h-5 w-5" />
          </span>
        )}
      </div>
      <dd className={`mt-2 text-3xl font-semibold tracking-tight tabular-nums ${valueClassName}`}>
        {value}
      </dd>
      {hint && <dd className="mt-1 text-sm text-slate-500">{hint}</dd>}
    </div>
  )
}

// Các ô số liệu nằm trong một danh sách mô tả (dl) để trình đọc màn hình đọc đúng cặp nhãn-giá trị.
export function StatGrid({ children }: { children: ReactNode }) {
  return <dl className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">{children}</dl>
}
