import type { ReactNode } from 'react'

interface PanelProps {
  id: string
  title: string
  description?: ReactNode
  children: ReactNode
}

// Khối nội dung có tiêu đề (gắn aria-labelledby để trình đọc màn hình nhảy theo vùng).
export function Panel({ id, title, description, children }: PanelProps) {
  return (
    <section
      aria-labelledby={id}
      className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
    >
      <h2 id={id} className="text-lg font-medium">
        {title}
      </h2>
      {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
      <div className="mt-3">{children}</div>
    </section>
  )
}

export function PageTitle({
  title,
  subtitle,
  actions,
}: {
  title: string
  subtitle?: ReactNode
  actions?: ReactNode
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
