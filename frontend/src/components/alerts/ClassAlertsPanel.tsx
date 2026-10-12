import { Link } from 'react-router-dom'
import { Panel } from '../Panel'
import { QueryState } from '../QueryState'
import { useClassAlerts } from '../../hooks/useAlerts'
import { formatProbability } from '../../lib/format'
import { AlertActions, ReasonList, RiskBadge, StatusBadge } from './AlertParts'

interface ClassAlertsPanelProps {
  classId: number
  // Chỉ GVCN của lớp được ghi nhận (BGH chỉ xem).
  canRecord: boolean
}

// Danh sách học sinh cần hỗ trợ của lớp: mức, ba lý do hàng đầu, trạng thái, nút ghi nhận.
export function ClassAlertsPanel({ classId, canRecord }: ClassAlertsPanelProps) {
  const alerts = useClassAlerts(classId)
  return (
    <Panel
      id="can-ho-tro"
      title="Học sinh cần hỗ trợ"
      description="Gợi ý từ các luật của Thông tư 22 và mô hình dự báo từ giữa học kỳ I, để giáo viên quyết định. Cảnh báo không tự gửi cho học sinh hay phụ huynh."
    >
      <QueryState query={alerts}>
        {(data) =>
          data.alerts.length === 0 ? (
            <p className="text-sm text-slate-600">Hiện chưa có học sinh nào cần hỗ trợ.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-max text-left text-sm">
                <thead className="border-b border-slate-200 text-slate-500">
                  <tr>
                    <th scope="col" className="py-2 pr-4 font-medium">
                      Học sinh
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Mức
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Lý do chính
                    </th>
                    <th scope="col" className="px-3 py-2 font-medium">
                      Ghi nhận
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 align-top">
                  {data.alerts.map((alert) => (
                    <tr key={alert.id}>
                      <th scope="row" className="py-2 pr-4 text-left font-normal">
                        <Link
                          to={`/classes/${classId}/students/${alert.student.id}`}
                          className="text-blue-700 hover:underline"
                        >
                          {alert.student.full_name}
                        </Link>
                        <span className="block font-mono text-xs text-slate-500">
                          {alert.student.student_code}
                        </span>
                      </th>
                      <td className="px-3 py-2">
                        <RiskBadge level={alert.level} />
                        {alert.risk_score !== null && (
                          <span className="mt-1 block text-xs text-slate-500">
                            Mô hình: {formatProbability(alert.risk_score)}
                          </span>
                        )}
                      </td>
                      <td className="max-w-xl px-3 py-2">
                        <ReasonList reasons={alert.top_reasons} />
                      </td>
                      <td className="px-3 py-2">
                        {canRecord ? (
                          <AlertActions alertId={alert.id} status={alert.teacher_status} />
                        ) : (
                          <StatusBadge status={alert.teacher_status} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        }
      </QueryState>
    </Panel>
  )
}
