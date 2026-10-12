import { Link } from 'react-router-dom'
import type { ClassRef } from '../api/auth'

export function HomeroomClasses({ classes }: { classes: ClassRef[] }) {
  return (
    <section
      aria-labelledby="lop-chu-nhiem"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 id="lop-chu-nhiem" className="text-lg font-medium">
        Lớp chủ nhiệm
      </h2>
      <ul className="mt-3 grid gap-3 sm:grid-cols-2">
        {classes.map((item) => (
          <li key={item.id} className="rounded-lg border border-slate-200 p-4">
            <span className="block text-xl font-semibold">{item.name}</span>
            <span className="block text-sm text-slate-500">Khối {item.grade_level}</span>
            <span className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm font-medium">
              <Link
                to={`/classes/${item.id}/import?kind=attendance`}
                aria-label={`Nhập điểm danh lớp ${item.name}`}
                className="text-blue-700 hover:underline"
              >
                Nhập điểm danh
              </Link>
              <Link
                to={`/classes/${item.id}/import?kind=conduct`}
                aria-label={`Nhập rèn luyện lớp ${item.name}`}
                className="text-blue-700 hover:underline"
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
