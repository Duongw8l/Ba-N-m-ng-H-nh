import type { ImportField, PreviewRow, RowAction } from '../../api/imports'
import { formatValue } from './format'

const ACTION_BADGES: Record<RowAction, { label: string; className: string }> = {
  new: { label: 'Mới', className: 'bg-green-100 text-green-800' },
  changed: { label: 'Đổi', className: 'bg-blue-100 text-blue-800' },
  unchanged: { label: 'Giữ nguyên', className: 'bg-slate-100 text-slate-600' },
}

function RowBadge({ row }: { row: PreviewRow }) {
  if (row.status === 'error') {
    return <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-800">Lỗi</span>
  }
  const action = row.action ? ACTION_BADGES[row.action] : null
  return (
    <span className="flex flex-wrap gap-1">
      {action && (
        <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${action.className}`}>
          {action.label}
        </span>
      )}
      {row.status === 'warning' && (
        <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
          Cảnh báo
        </span>
      )}
    </span>
  )
}

const ROW_TONES = {
  ok: '',
  warning: 'bg-amber-50',
  error: 'bg-red-50',
} as const

interface PreviewTableProps {
  rows: PreviewRow[]
  fields: ImportField[]
}

// Các trường hiển thị thành cột (mã học sinh và họ tên đã có cột riêng).
const IDENTITY_FIELDS = new Set(['student_code', 'full_name'])

export function PreviewTable({ rows, fields }: PreviewTableProps) {
  const valueFields = fields.filter((field) => !IDENTITY_FIELDS.has(field.name))

  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200 bg-white shadow-sm">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
          <tr>
            <th scope="col" className="px-3 py-2 font-medium">
              Dòng
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Mã HS
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Họ và tên
            </th>
            {valueFields.map((field) => (
              <th key={field.name} scope="col" className="px-3 py-2 font-medium">
                {field.label}
              </th>
            ))}
            <th scope="col" className="px-3 py-2 font-medium">
              Kết quả
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Ghi chú
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row) => {
            const badColumns = new Set(row.messages.map((message) => message.column))
            return (
              <tr key={row.line} className={ROW_TONES[row.status]}>
                <td className="px-3 py-2 text-slate-500">{row.line}</td>
                <td className="px-3 py-2 font-mono">{row.student_code || '—'}</td>
                <td className="px-3 py-2">{row.full_name ?? '—'}</td>
                {valueFields.map((field) => {
                  const old = row.existing[field.name]
                  const hasOld = field.name in row.existing
                  const bad = field.column !== null && badColumns.has(field.column)
                  return (
                    <td
                      key={field.name}
                      className={`px-3 py-2 tabular-nums ${bad ? 'bg-red-200 font-medium text-red-900' : ''}`}
                    >
                      {hasOld ? (
                        <>
                          <span className="text-slate-400 line-through">
                            {formatValue(field.name, old)}
                          </span>{' '}
                          <span aria-hidden="true">→</span>{' '}
                          <span className="sr-only">đổi thành</span>
                          <span className="font-medium text-blue-800">
                            {formatValue(field.name, row.values[field.name])}
                          </span>
                        </>
                      ) : (
                        formatValue(field.name, row.values[field.name])
                      )}
                    </td>
                  )
                })}
                <td className="px-3 py-2">
                  <RowBadge row={row} />
                </td>
                <td className="px-3 py-2">
                  {row.messages.length > 0 && (
                    <ul className="space-y-0.5">
                      {row.messages.map((message) => (
                        <li
                          key={`${message.column ?? ''}-${message.message}`}
                          className={row.status === 'error' ? 'text-red-700' : 'text-amber-800'}
                        >
                          {message.column && <span className="font-medium">{message.column}: </span>}
                          {message.message}
                        </li>
                      ))}
                    </ul>
                  )}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
