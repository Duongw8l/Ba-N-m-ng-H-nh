import type { ReactNode } from 'react'

interface StatCardProps {
  label: string
  value: ReactNode
  hint?: ReactNode
  valueClassName?: string
}

export function StatCard({ label, value, hint, valueClassName = 'text-slate-900' }: StatCardProps) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
      <dt className="text-sm text-slate-500">{label}</dt>
      <dd className={`mt-1 text-3xl font-semibold tabular-nums ${valueClassName}`}>{value}</dd>
      {hint && <dd className="mt-1 text-sm text-slate-500">{hint}</dd>}
    </div>
  )
}

// Các ô số liệu nằm trong một danh sách mô tả (dl) để trình đọc màn hình đọc đúng cặp nhãn-giá trị.
export function StatGrid({ children }: { children: ReactNode }) {
  return <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</dl>
}
