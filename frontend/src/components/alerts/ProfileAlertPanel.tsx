import type { ProfileAlert } from '../../api/warning'
import { Panel } from '../Panel'
import { formatProbability, formatScore } from '../../lib/format'
import { AlertActions, ReasonList, RiskBadge, StatusBadge } from './AlertParts'

interface ProfileAlertPanelProps {
  alert: ProfileAlert | null
  canRecord: boolean
}

// Cảnh báo sớm hiện hành của một học sinh: mức, các lý do của luật, ba yếu tố của mô hình, nút ghi nhận.
export function ProfileAlertPanel({ alert, canRecord }: ProfileAlertPanelProps) {
  return (
    <Panel
      id="canh-bao-som"
      title="Cảnh báo sớm"
      description="Gợi ý để giáo viên quyết định có trao đổi với học sinh hay phụ huynh hay không; hệ thống không tự gửi cho ai."
    >
      {alert === null ? (
        <p className="text-sm text-slate-600">Chưa có cảnh báo cho học sinh này.</p>
      ) : alert.level === 'low' ? (
        <p className="text-sm text-slate-700">
          Hiện chưa có lý do nào cần hỗ trợ thêm (<RiskBadge level="low" />
          {alert.risk_score !== null && ` · mô hình ${formatProbability(alert.risk_score)}`}).
        </p>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <RiskBadge level={alert.level} />
            {alert.risk_score !== null && (
              <span className="text-sm text-slate-600">
                Mô hình dự báo nguy cơ {formatProbability(alert.risk_score)}
              </span>
            )}
            <StatusBadge status={alert.teacher_status} />
          </div>
          <div>
            <h3 className="text-sm font-medium">Lý do chính</h3>
            <div className="mt-1">
              <ReasonList reasons={alert.top_reasons} />
            </div>
          </div>
          {alert.rules.length > 3 && (
            <details className="text-sm">
              <summary className="cursor-pointer font-medium text-slate-700">
                Tất cả {alert.rules.length} lý do của luật
              </summary>
              <div className="mt-1">
                <ReasonList reasons={alert.rules.map((rule) => rule.message)} />
              </div>
            </details>
          )}
          {alert.model && alert.model.factors.length > 0 && (
            <details className="text-sm">
              <summary className="cursor-pointer font-medium text-slate-700">
                Vì sao mô hình dự báo như vậy (ba yếu tố rõ nhất)
              </summary>
              <ul className="mt-1 list-inside list-disc space-y-0.5 text-slate-800">
                {alert.model.factors.map((factor) => (
                  <li key={factor.feature}>
                    {factor.message}
                    <span className="sr-only"> (giá trị {formatScore(factor.value)})</span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {canRecord && <AlertActions alertId={alert.id} status={alert.teacher_status} />}
          {alert.as_of && (
            <p className="text-xs text-slate-500">Dữ liệu tính tới ngày {alert.as_of}.</p>
          )}
        </div>
      )}
    </Panel>
  )
}
