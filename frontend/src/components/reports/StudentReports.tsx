import { useState } from 'react'
import type { ReportJob, ReportList, ReportTarget } from '../../api/reports'
import { useGenerateReport, useStartClassJob } from '../../hooks/useReports'
import { formatInt } from '../../lib/format'
import { ErrorAlert } from '../admin/shared'
import { Icon } from '../Icon'
import { JOB_ERRORS, STATE_BADGES, STATE_LABELS, stateOf } from './options'
import { ReportEditor } from './ReportEditor'

interface JobStatusProps {
  job: ReportJob
}

// Tiến độ lần sinh cả lớp gần nhất: thanh tiến độ khi đang chạy, lý do khi dừng giữa chừng.
function JobStatus({ job }: JobStatusProps) {
  if (job.status === 'running') {
    const percent = job.total > 0 ? Math.round((job.done / job.total) * 100) : 0
    return (
      <div aria-live="polite" className="space-y-1.5">
        <p className="text-sm font-medium">
          Đang sinh nhận xét: {formatInt(job.done)}/{formatInt(job.total)} học sinh
        </p>
        <div
          role="progressbar"
          aria-label="Tiến độ sinh nhận xét"
          aria-valuemin={0}
          aria-valuemax={job.total}
          aria-valuenow={job.done}
          className="h-2.5 overflow-hidden rounded-full bg-slate-200"
        >
          <div
            className="h-full rounded-full bg-brand-600 transition-[width] duration-500"
            style={{ width: `${percent}%` }}
          />
        </div>
        <p className="text-xs text-slate-500">
          Việc chạy nền: bạn có thể làm việc khác hoặc đóng trang, nhận xét đã viết xong được giữ
          lại.
        </p>
      </div>
    )
  }
  if (job.status === 'stopped') {
    return (
      <p
        role="status"
        className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
      >
        <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
        <span>
          Lần sinh gần nhất dừng ở {formatInt(job.done)}/{formatInt(job.total)} học sinh.{' '}
          {JOB_ERRORS[job.error_code ?? ''] ?? 'Phần đã viết được giữ lại.'}
        </span>
      </p>
    )
  }
  return null
}

interface StudentReportsProps {
  target: ReportTarget
  list: ReportList
  initialStudentId: number | null
}

// Nhận xét từng học sinh của một lớp: sinh cả lớp (chạy nền), mở từng em để sửa và duyệt.
export function StudentReports({ target, list, initialStudentId }: StudentReportsProps) {
  const start = useStartClassJob(target)
  const generate = useGenerateReport(target)
  const [openId, setOpenId] = useState<number | null>(initialStudentId)
  const [warnings, setWarnings] = useState<Record<number, string[]>>({})

  const items = list.items
  const written = items.filter((item) => item.report !== null)
  const approved = written.filter((item) => item.report?.status === 'approved').length
  const manual = written.filter((item) => item.report?.needs_manual).length
  const missing = items.length - written.length
  const running = list.job?.status === 'running'
  const generatingId = generate.isPending ? generate.variables.studentId : undefined

  const startLabel =
    written.length === 0
      ? 'Sinh nhận xét cả lớp'
      : list.job?.status === 'stopped'
        ? `Tiếp tục (còn ${formatInt(missing)} em)`
        : `Sinh cho ${formatInt(missing)} em còn thiếu`

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-600" aria-live="polite">
          <strong className="tabular-nums">{formatInt(written.length)}</strong>/
          {formatInt(items.length)} em đã có nhận xét · {formatInt(approved)} đã duyệt
          {manual > 0 && <> · {formatInt(manual)} cần tự viết</>}
        </p>
        <button
          type="button"
          onClick={() => start.mutate()}
          disabled={start.isPending || running || missing === 0}
          className="btn-primary"
        >
          <Icon name="sparkles" className="h-4 w-4" />
          {running
            ? 'Đang sinh…'
            : missing === 0
              ? 'Đã có đủ cho cả lớp'
              : start.isPending
                ? 'Đang bắt đầu…'
                : startLabel}
        </button>
      </div>
      {list.job && <JobStatus job={list.job} />}
      {start.isError && <ErrorAlert error={start.error} />}
      {generate.isError && <ErrorAlert error={generate.error} />}

      <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200">
        {items.map(({ student, report }) => {
          if (student === null) return null
          const state = stateOf(report)
          const open = openId === student.id && report !== null
          return (
            <li key={student.id} className="px-4 py-3">
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-medium">{student.full_name}</p>
                  <p className="text-xs text-slate-500">Mã {student.student_code}</p>
                </div>
                <span className={STATE_BADGES[state]}>{STATE_LABELS[state]}</span>
                {report !== null ? (
                  <button
                    type="button"
                    onClick={() => setOpenId(open ? null : student.id)}
                    aria-expanded={open}
                    aria-label={`${open ? 'Đóng' : 'Mở'} nhận xét của ${student.full_name}`}
                    className="btn-secondary btn-sm"
                  >
                    {open ? 'Đóng' : 'Mở'}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() =>
                      generate.mutate(
                        { studentId: student.id },
                        { onSuccess: () => setOpenId(student.id) },
                      )
                    }
                    disabled={generate.isPending || running}
                    aria-label={`Sinh nhận xét cho ${student.full_name}`}
                    className="btn-secondary btn-sm"
                  >
                    {generatingId === student.id ? 'Đang sinh…' : 'Sinh nhận xét'}
                  </button>
                )}
              </div>
              {open && report !== null && (
                <div className="mt-3 rounded-xl bg-slate-50 p-4 ring-1 ring-slate-200">
                  <ReportEditor
                    key={`${report.id}-${report.updated_at}`}
                    report={report}
                    warnings={warnings[report.id] ?? []}
                    onWarnings={(next) => setWarnings((all) => ({ ...all, [report.id]: next }))}
                  />
                </div>
              )}
            </li>
          )
        })}
      </ul>
    </div>
  )
}
