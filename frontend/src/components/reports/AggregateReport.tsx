import { useState } from 'react'
import type { Report, ReportTarget } from '../../api/reports'
import { useGenerateReport } from '../../hooks/useReports'
import { ErrorAlert } from '../admin/shared'
import { Icon } from '../Icon'
import { stateOf, STATE_BADGES, STATE_LABELS } from './options'
import { ReportEditor } from './ReportEditor'

interface AggregateReportProps {
  target: ReportTarget
  report: Report | null
  scopeLabel: string // ví dụ "lớp 11A2" hoặc "khối 11"
}

// Báo cáo tổng hợp một lớp hoặc một khối (không nêu tên học sinh): sinh, sửa, duyệt, xuất PDF.
export function AggregateReport({ target, report, scopeLabel }: AggregateReportProps) {
  const generate = useGenerateReport(target)
  const [warnings, setWarnings] = useState<string[]>([])
  const state = stateOf(report)

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-slate-600">
          Báo cáo {scopeLabel}
          <span className={STATE_BADGES[state]}>{STATE_LABELS[state]}</span>
        </p>
        {report === null && (
          <button
            type="button"
            onClick={() => generate.mutate({})}
            disabled={generate.isPending}
            className="btn-primary"
          >
            <Icon name="sparkles" className="h-4 w-4" />
            {generate.isPending ? 'Đang sinh…' : `Sinh báo cáo ${scopeLabel}`}
          </button>
        )}
      </div>
      {generate.isError && <ErrorAlert error={generate.error} />}
      {report !== null && (
        <div className="rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
          <ReportEditor
            key={`${report.id}-${report.updated_at}`}
            report={report}
            warnings={warnings}
            onWarnings={setWarnings}
          />
        </div>
      )}
    </div>
  )
}
