import { useId, useState } from 'react'
import { downloadReportPdf } from '../../api/reports'
import type { Report } from '../../api/reports'
import { useRegenerateReport, useUpdateReport } from '../../hooks/useReports'
import { ErrorAlert } from '../admin/shared'
import { Icon } from '../Icon'
import { describeChecks } from './options'

const MAX_CHARS = 5000
const MAX_FEEDBACK = 300

interface ReportEditorProps {
  report: Report
  // Cảnh báo kiểm tự động cho lần lưu gần nhất (nằm ở cha để không mất khi danh sách tải lại).
  warnings: string[]
  onWarnings: (warnings: string[]) => void
}

function formatDate(iso: string | null): string {
  return iso === null ? '' : new Date(iso).toLocaleDateString('vi-VN')
}

// Soạn, sửa, duyệt, sinh lại và xuất PDF một bản nhận xét hoặc báo cáo. Cha đặt `key` theo
// `report.updated_at` nên khi máy chủ đổi nội dung (sinh lại, lưu) ô soạn tự lấy văn bản mới.
export function ReportEditor({ report, warnings, onWarnings }: ReportEditorProps) {
  const fieldId = useId()
  const update = useUpdateReport()
  const regenerate = useRegenerateReport()
  const [text, setText] = useState(report.text)
  const [feedbackOpen, setFeedbackOpen] = useState(false)
  const [feedback, setFeedback] = useState('')
  const [downloadError, setDownloadError] = useState<unknown>(null)
  const [downloading, setDownloading] = useState(false)

  const approved = report.status === 'approved'
  const dirty = text.trim() !== report.text.trim()
  const busy = update.isPending || regenerate.isPending
  const error: unknown = update.error ?? regenerate.error ?? downloadError

  function save(approve: boolean) {
    onWarnings([])
    setDownloadError(null)
    update.mutate(
      { id: report.id, body: { ...(dirty && { text }), ...(approve && { approve: true }) } },
      { onSuccess: (saved) => onWarnings(saved.warnings) },
    )
  }

  function rewrite() {
    onWarnings([])
    setDownloadError(null)
    regenerate.mutate(
      { id: report.id, feedback: feedback.trim() || undefined },
      {
        onSuccess: () => {
          setFeedback('')
          setFeedbackOpen(false)
        },
      },
    )
  }

  async function exportPdf() {
    setDownloading(true)
    setDownloadError(null)
    try {
      await downloadReportPdf(report.id)
    } catch (caught) {
      setDownloadError(caught)
    } finally {
      setDownloading(false)
    }
  }

  return (
    <div className="space-y-3">
      {report.needs_manual && (
        <p
          role="status"
          className="flex items-start gap-2 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
        >
          <Icon name="info" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            AI chưa viết được bản đạt kiểm tra tự động ({describeChecks(report.check_notes)}) sau{' '}
            {report.attempts} lần thử, nên bản này để trống cho thầy/cô tự viết. Bạn cũng có thể bấm
            “Sinh lại” để thử lần nữa.
          </span>
        </p>
      )}
      <div className="flex flex-wrap items-center gap-2">
        {approved ? (
          <span className="badge-good">Đã duyệt ngày {formatDate(report.approved_at)}</span>
        ) : (
          !report.needs_manual && <span className="badge-info">Bản nháp do AI tạo</span>
        )}
        {approved && dirty && (
          <span className="text-xs text-slate-500">
            Sửa nội dung sẽ đưa bản này về bản nháp, cần duyệt lại.
          </span>
        )}
      </div>

      <div>
        <label htmlFor={fieldId} className="label">
          Nội dung
        </label>
        <textarea
          id={fieldId}
          value={text}
          onChange={(event) => setText(event.target.value)}
          maxLength={MAX_CHARS}
          rows={7}
          className="input mt-1 resize-y leading-relaxed"
        />
        <p className="mt-1 text-right text-xs text-slate-500 tabular-nums">
          {text.length}/{MAX_CHARS}
        </p>
      </div>

      {warnings.length > 0 && (
        <div
          role="status"
          className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200"
        >
          <p className="font-medium">Văn bản vừa lưu có điểm cần xem lại:</p>
          <ul className="mt-1 list-disc space-y-0.5 pl-5">
            {warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
      {error ? <ErrorAlert error={error} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => save(true)}
          disabled={busy || text.trim() === '' || (approved && !dirty)}
          className="btn-primary btn-sm"
        >
          {approved && dirty ? 'Lưu và duyệt lại' : 'Duyệt'}
        </button>
        <button
          type="button"
          onClick={() => save(false)}
          disabled={busy || !dirty}
          className="btn-secondary btn-sm"
        >
          {approved ? 'Lưu (về bản nháp)' : 'Lưu nháp'}
        </button>
        <button
          type="button"
          onClick={() => setFeedbackOpen((open) => !open)}
          disabled={busy || approved}
          aria-expanded={feedbackOpen}
          title={approved ? 'Sửa nội dung để đưa về bản nháp rồi mới sinh lại được.' : undefined}
          className="btn-secondary btn-sm"
        >
          Sinh lại
        </button>
        <button
          type="button"
          onClick={() => void exportPdf()}
          disabled={!approved || dirty || downloading}
          title={approved ? undefined : 'Chỉ xuất được bản đã duyệt.'}
          className="btn-secondary btn-sm ml-auto"
        >
          {downloading ? 'Đang tạo PDF…' : 'Xuất PDF'}
        </button>
      </div>

      {feedbackOpen && !approved && (
        <div className="space-y-2 rounded-xl bg-slate-50 p-3 ring-1 ring-slate-200">
          <label htmlFor={`${fieldId}-gop-y`} className="label">
            Góp ý cho AI (không bắt buộc)
          </label>
          <input
            id={`${fieldId}-gop-y`}
            value={feedback}
            onChange={(event) => setFeedback(event.target.value)}
            maxLength={MAX_FEEDBACK}
            placeholder="Ví dụ: viết nhẹ nhàng hơn, nhấn mạnh sự tiến bộ"
            className="input"
          />
          <p className="text-xs text-slate-500">
            Đừng nêu họ tên học sinh. Văn bản hiện tại sẽ bị thay bằng bản AI viết lại.
          </p>
          <button type="button" onClick={rewrite} disabled={busy} className="btn-primary btn-sm">
            {regenerate.isPending ? 'Đang viết lại…' : 'Viết lại'}
          </button>
        </div>
      )}
    </div>
  )
}
