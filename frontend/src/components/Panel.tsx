import type { ReactNode } from 'react'

interface PanelProps {
  id: string
  title: string
  description?: ReactNode
  // Nút hay liên kết ở góc phải tiêu đề (ví dụ "Xem tất cả").
  actions?: ReactNode
  children: ReactNode
}

// Khối nội dung có tiêu đề (gắn aria-labelledby để trình đọc màn hình nhảy theo vùng).
export function Panel({ id, title, description, actions, children }: PanelProps) {
  return (
    <section aria-labelledby={id} className="card min-w-0 p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <h2 id={id} className="text-base font-semibold tracking-tight">
            {title}
          </h2>
          {description && <p className="mt-1 text-sm text-slate-500">{description}</p>}
        </div>
        {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
      </div>
      <div className="mt-4">{children}</div>
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
    <div className="flex flex-wrap items-end justify-between gap-x-4 gap-y-3">
      <div className="min-w-0">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-3">{actions}</div>}
    </div>
  )
}
