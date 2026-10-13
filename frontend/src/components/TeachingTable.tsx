import { Link } from 'react-router-dom'
import type { TeachingItem } from '../api/auth'
import { Panel } from './Panel'

// Lớp và môn giáo viên đang dạy, mỗi dòng có lối tắt tới bảng điểm và nhập điểm.
export function TeachingTable({ items }: { items: TeachingItem[] }) {
  return (
    <Panel id="lop-mon-dang-day" title="Lớp và môn đang dạy">
      <div className="-mx-2 overflow-x-auto px-2">
        <table className="data-table min-w-max">
          <thead>
            <tr>
              <th scope="col" className="px-3 py-2.5 font-semibold">
                Lớp
              </th>
              <th scope="col" className="px-3 py-2.5 font-semibold">
                Môn
              </th>
              <th scope="col" className="px-3 py-2.5 text-right font-semibold">
                <span className="sr-only">Thao tác</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={`${item.class_id}-${item.subject_id}`}>
                <td className="px-3 py-2.5 font-medium">{item.class_name}</td>
                <td className="px-3 py-2.5">{item.subject_name}</td>
                <td className="space-x-4 px-3 py-2.5 text-right">
                  <Link
                    to={`/classes/${item.class_id}/subjects/${item.subject_id}`}
                    aria-label={`Bảng điểm ${item.subject_name} lớp ${item.class_name}`}
                    className="link"
                  >
                    Bảng điểm
                  </Link>
                  <Link
                    to={`/classes/${item.class_id}/import?kind=assessments&subject=${item.subject_id}`}
                    aria-label={`Nhập điểm ${item.subject_name} lớp ${item.class_name}`}
                    className="link"
                  >
                    Nhập điểm
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}
