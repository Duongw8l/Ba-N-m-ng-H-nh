import type { PreviewSummary } from '../../api/imports'

interface Card {
  label: string
  value: number
  className: string
}

export function SummaryCards({ summary }: { summary: PreviewSummary }) {
  const cards: Card[] = [
    { label: 'Tổng số dòng', value: summary.total_rows, className: 'text-slate-900' },
    { label: 'Dòng lỗi', value: summary.error_rows, className: 'text-red-700' },
    { label: 'Cảnh báo', value: summary.warning_rows, className: 'text-amber-700' },
    { label: 'Dòng mới', value: summary.new_rows, className: 'text-green-700' },
    { label: 'Dòng thay đổi', value: summary.changed_rows, className: 'text-blue-700' },
    { label: 'Giữ nguyên', value: summary.unchanged_rows, className: 'text-slate-600' },
  ]
  return (
    <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
      {cards.map((card) => (
        <div key={card.label} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
          <dt className="text-xs text-slate-500">{card.label}</dt>
          <dd className={`text-2xl font-semibold tabular-nums ${card.className}`}>{card.value}</dd>
        </div>
      ))}
    </dl>
  )
}
