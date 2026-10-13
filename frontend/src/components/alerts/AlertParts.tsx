import type { RiskLevel, TeacherStatus } from '../../api/warning'
import { RISK_LABELS, RISK_STYLES, TEACHER_STATUS_LABELS } from '../../lib/labels'
import { useUpdateAlert } from '../../hooks/useAlerts'
import { ApiError } from '../../api/client'

export function RiskBadge({ level }: { level: RiskLevel }) {
  return (
    <span className={RISK_STYLES[level]}>{RISK_LABELS[level]}</span>
  )
}

export function StatusBadge({ status }: { status: TeacherStatus }) {
  if (status === 'new') return <span className="text-xs text-slate-500">Chưa xử lý</span>
  return (
    <span className="badge-info">{TEACHER_STATUS_LABELS[status]}</span>
  )
}

export function ReasonList({ reasons }: { reasons: string[] }) {
  if (reasons.length === 0) {
    return <p className="text-sm text-slate-500">Không có lý do nào cần nêu.</p>
  }
  return (
    <ul className="list-inside list-disc space-y-0.5 text-sm text-slate-800">
      {reasons.map((reason) => (
        <li key={reason}>{reason}</li>
      ))}
    </ul>
  )
}

interface AlertActionsProps {
  alertId: number
  status: TeacherStatus
}

// Nút ghi nhận của GVCN. Chỉ dựng khi người dùng là GVCN của lớp; back-end vẫn kiểm lại quyền.
export function AlertActions({ alertId, status }: AlertActionsProps) {
  const update = useUpdateAlert()
  const choices: { value: TeacherStatus; label: string }[] = [
    { value: 'contacted', label: 'Đã trao đổi' },
    { value: 'false_alarm', label: 'Báo nhầm' },
  ]
  const error =
    update.error instanceof ApiError
      ? update.error.message
      : update.isError
        ? 'Không ghi nhận được. Hãy thử lại.'
        : null

  return (
    <div className="space-y-1">
      <div className="flex flex-wrap gap-2">
        {choices.map((choice) => (
          <button
            key={choice.value}
            type="button"
            aria-pressed={status === choice.value}
            disabled={update.isPending}
            onClick={() =>
              update.mutate({
                alertId,
                // Bấm lại đúng trạng thái đang chọn thì bỏ ghi nhận.
                status: status === choice.value ? 'new' : choice.value,
              })
            }
            className={`rounded-lg border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-60 ${
              status === choice.value
                ? 'border-brand-700 bg-brand-700 text-white'
                : 'border-slate-300 hover:bg-slate-100'
            }`}
          >
            {choice.label}
          </button>
        ))}
      </div>
      {error && (
        <p role="alert" className="text-xs text-red-700">
          {error}
        </p>
      )}
    </div>
  )
}
