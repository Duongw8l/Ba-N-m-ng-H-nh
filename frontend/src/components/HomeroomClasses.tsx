import { Link } from 'react-router-dom'
import type { ClassRef } from '../api/auth'
import { useClassAlerts } from '../hooks/useAlerts'
import { Icon } from './Icon'

function AlertSummary({ classId }: { classId: number }) {
  const alerts = useClassAlerts(classId)
  if (alerts.isPending) {
    return <span className="block text-sm text-slate-500">Cảnh báo sớm: đang tải…</span>
  }
  if (alerts.isError) {
    return <span className="block text-sm text-slate-500">Cảnh báo sớm: chưa tải được</span>
  }
  const { high, medium } = alerts.data.counts
  return (
    <span className="block text-sm text-slate-600">
      Cảnh báo sớm:{' '}
      <strong className={high > 0 ? 'text-red-700' : 'text-slate-900'}>{high}</strong> mức cao,{' '}
      <strong className="text-slate-900">{medium}</strong> mức trung bình
    </span>
  )
}

// GVCN: mỗi lớp chủ nhiệm một thẻ có số cảnh báo và các lối tắt thường dùng.
export function HomeroomClasses({ classes }: { classes: ClassRef[] }) {
  return (
    <section aria-labelledby="lop-chu-nhiem" className="space-y-3">
      <h2 id="lop-chu-nhiem" className="text-base font-semibold tracking-tight">
        Lớp chủ nhiệm
      </h2>
      <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {classes.map((item) => (
          <li key={item.id} className="card p-5">
            <div className="flex items-start gap-4">
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-brand-400 to-brand-700 text-white shadow-sm">
                <Icon name="users" className="h-6 w-6" />
              </span>
              <div className="min-w-0">
                <span className="block text-xl font-semibold tracking-tight">{item.name}</span>
                <span className="block text-sm text-slate-500">Khối {item.grade_level}</span>
              </div>
            </div>
            <div className="mt-3">
              <AlertSummary classId={item.id} />
            </div>
            <span className="mt-4 flex flex-wrap gap-2">
              <Link
                to={`/classes/${item.id}`}
                aria-label={`Dashboard lớp ${item.name}`}
                className="btn-primary btn-sm"
              >
                Dashboard lớp
              </Link>
              <Link
                to={`/classes/${item.id}/import?kind=attendance`}
                aria-label={`Nhập điểm danh lớp ${item.name}`}
                className="btn-secondary btn-sm"
              >
                Nhập điểm danh
              </Link>
              <Link
                to={`/classes/${item.id}/import?kind=conduct`}
                aria-label={`Nhập rèn luyện lớp ${item.name}`}
                className="btn-secondary btn-sm"
              >
                Nhập rèn luyện
              </Link>
            </span>
          </li>
        ))}
      </ul>
    </section>
  )
}
