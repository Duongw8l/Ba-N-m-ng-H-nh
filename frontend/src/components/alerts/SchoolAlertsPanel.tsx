import { Link } from 'react-router-dom'
import { QueryState } from '../QueryState'
import { useSchoolAlerts } from '../../hooks/useAlerts'
import { formatProbability } from '../../lib/format'
import { ReasonList, StatusBadge } from './AlertParts'

// Cảnh báo mức Cao của toàn trường, cho BGH (chỉ xem; GVCN của từng lớp ghi nhận).
export function SchoolAlertsPanel() {
  const alerts = useSchoolAlerts('high')
  return (
    <section
      aria-labelledby="canh-bao-cao"
      className="card p-6"
    >
      <h2 id="canh-bao-cao" className="text-lg font-medium">
        Học sinh cần hỗ trợ ngay (mức cao, toàn trường)
      </h2>
      <p className="mt-1 text-sm text-slate-500">
        Gợi ý từ luật Thông tư 22 và mô hình dự báo; giáo viên chủ nhiệm của từng lớp quyết định và
        ghi nhận.
      </p>
      <div className="mt-3">
        <QueryState query={alerts}>
          {(data) =>
            data.alerts.length === 0 ? (
              <p className="text-sm text-slate-600">Hiện không có cảnh báo mức cao.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="data-table min-w-max">
                  <thead>
                    <tr>
                      <th scope="col" className="py-2 pr-4 font-medium">
                        Lớp
                      </th>
                      <th scope="col" className="px-3 py-2 font-medium">
                        Học sinh
                      </th>
                      <th scope="col" className="px-3 py-2 font-medium">
                        Lý do chính
                      </th>
                      <th scope="col" className="px-3 py-2 font-medium">
                        Trạng thái
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-100 align-top">
                    {data.alerts.map((alert) => (
                      <tr key={alert.id}>
                        <th scope="row" className="py-2 pr-4 text-left font-normal">
                          <Link
                            to={`/classes/${alert.class_id}`}
                            className="link"
                          >
                            {alert.class_name}
                          </Link>
                        </th>
                        <td className="px-3 py-2">
                          <Link
                            to={`/classes/${alert.class_id}/students/${alert.student.id}`}
                            className="link"
                          >
                            {alert.student.full_name}
                          </Link>
                          {alert.risk_score !== null && (
                            <span className="block text-xs text-slate-500">
                              Mô hình: {formatProbability(alert.risk_score)}
                            </span>
                          )}
                        </td>
                        <td className="max-w-xl px-3 py-2">
                          <ReasonList reasons={alert.top_reasons} />
                        </td>
                        <td className="px-3 py-2">
                          <StatusBadge status={alert.teacher_status} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )
          }
        </QueryState>
      </div>
    </section>
  )
}
