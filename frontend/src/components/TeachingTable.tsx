import { Link } from 'react-router-dom'
import type { TeachingItem } from '../api/auth'

export function TeachingTable({ items }: { items: TeachingItem[] }) {
  return (
    <section
      aria-labelledby="lop-mon-dang-day"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 id="lop-mon-dang-day" className="text-lg font-medium">
        Lớp và môn đang dạy
      </h2>
      <table className="mt-3 w-full text-left text-sm">
        <thead className="text-slate-500">
          <tr>
            <th scope="col" className="py-2 font-medium">
              Lớp
            </th>
            <th scope="col" className="py-2 font-medium">
              Môn
            </th>
            <th scope="col" className="py-2 text-right font-medium">
              <span className="sr-only">Thao tác</span>
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {items.map((item) => (
            <tr key={`${item.class_id}-${item.subject_id}`}>
              <td className="py-2">{item.class_name}</td>
              <td className="py-2">{item.subject_name}</td>
              <td className="space-x-4 py-2 text-right">
                <Link
                  to={`/classes/${item.class_id}/subjects/${item.subject_id}`}
                  aria-label={`Bảng điểm ${item.subject_name} lớp ${item.class_name}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  Bảng điểm
                </Link>
                <Link
                  to={`/classes/${item.class_id}/import?kind=assessments&subject=${item.subject_id}`}
                  aria-label={`Nhập điểm ${item.subject_name} lớp ${item.class_name}`}
                  className="font-medium text-blue-700 hover:underline"
                >
                  Nhập điểm
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
