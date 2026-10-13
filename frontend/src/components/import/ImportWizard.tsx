import { useMutation, useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiError } from '../../api/client'
import { confirmImport, fetchMappingTemplates, uploadPreview } from '../../api/imports'
import type {
  ConductPeriod,
  ConfirmResult,
  ImportKind,
  ImportPreview,
  PreviewRequest,
} from '../../api/imports'
import { useAuth } from '../../auth/context'
import { FilePicker } from './FilePicker'
import { KIND_LABELS, PERIOD_LABELS } from './format'
import { MappingEditor } from './MappingEditor'
import type { MappingChoice } from './MappingEditor'
import { PreviewTable } from './PreviewTable'
import { Stepper } from './Stepper'
import { SummaryCards } from './SummaryCards'

export interface SubjectOption {
  id: number
  name: string
}

interface ImportWizardProps {
  classId: number
  className: string
  kinds: ImportKind[]
  subjects: SubjectOption[]
  initialKind: ImportKind
  initialSubjectId: number | null
}

interface Settings {
  kind: ImportKind
  subjectId: number | null
  semester: number
  period: ConductPeriod
  allowPartial: boolean
}

const PERIODS: ConductPeriod[] = ['hk1', 'hk2', 'year']

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

function selectClass(): string {
  return 'input mt-1'
}

// Trình hướng dẫn nhập tệp: chọn loại và tệp, xem trước (chưa ghi gì), rồi xác nhận mới ghi.
// Tệp được giữ trong bộ nhớ trình duyệt để gửi lại khi đổi cài đặt hoặc cách chọn cột.
export function ImportWizard({
  classId,
  className,
  kinds,
  subjects,
  initialKind,
  initialSubjectId,
}: ImportWizardProps) {
  const { token } = useAuth()
  const [settings, setSettings] = useState<Settings>({
    kind: initialKind,
    subjectId: initialSubjectId ?? subjects[0]?.id ?? null,
    semester: 1,
    period: 'hk1',
    allowPartial: false,
  })
  const [file, setFile] = useState<File | null>(null)
  const [preview, setPreview] = useState<ImportPreview | null>(null)
  const [result, setResult] = useState<ConfirmResult | null>(null)
  const [onlyProblems, setOnlyProblems] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const templates = useQuery({
    queryKey: ['import-mappings', token, settings.kind],
    queryFn: ({ signal }) => fetchMappingTemplates(settings.kind, signal),
    enabled: token !== null,
  })

  const previewMutation = useMutation({
    mutationFn: uploadPreview,
    onSuccess: (data) => {
      setPreview(data)
      setOnlyProblems(data.summary.error_rows > 0)
      setError(null)
      // Mẫu có thể vừa được lưu cùng lần tải này.
      void templates.refetch()
    },
    onError: (caught) => setError(errorText(caught)),
  })

  const confirmMutation = useMutation({
    mutationFn: confirmImport,
    onSuccess: (data) => {
      setResult(data)
      setError(null)
    },
    onError: (caught) => setError(errorText(caught)),
  })

  function buildRequest(picked: File, current: Settings): PreviewRequest {
    const assessments = current.kind === 'assessments'
    return {
      classId,
      kind: current.kind,
      file: picked,
      subjectId: assessments ? (current.subjectId ?? undefined) : undefined,
      semester: assessments ? current.semester : undefined,
      period: current.kind === 'conduct' ? current.period : undefined,
      allowPartial: assessments && current.allowPartial,
    }
  }

  function reset(next?: Partial<Settings>) {
    setSettings((current) => ({ ...current, ...next }))
    setFile(null)
    setPreview(null)
    setResult(null)
    setError(null)
  }

  // Đổi môn, học kỳ, kỳ hoặc cho phép nhập dở: kết quả kiểm khác đi nên kiểm lại ngay với tệp đang chọn.
  function changeSettings(next: Partial<Settings>) {
    const updated = { ...settings, ...next }
    setSettings(updated)
    setResult(null)
    if (file) previewMutation.mutate(buildRequest(file, updated))
  }

  function pickFile(picked: File) {
    setFile(picked)
    setResult(null)
    previewMutation.mutate(buildRequest(picked, settings))
  }

  function applyMapping(choice: MappingChoice) {
    if (!file) return
    previewMutation.mutate({
      ...buildRequest(file, settings),
      mapping: choice.mapping,
      saveMappingAs: choice.saveMappingAs,
      headerRow: choice.headerRow,
    })
  }

  function applyTemplate(name: string) {
    if (!file) return
    previewMutation.mutate({ ...buildRequest(file, settings), mappingName: name })
  }

  const busy = previewMutation.isPending || confirmMutation.isPending

  if (result) {
    return (
      <div className="space-y-6">
        <Stepper current={4} />
        <section
          aria-labelledby="ket-qua-nhap"
          className="space-y-4 rounded-2xl border border-green-200 bg-green-50 p-6"
        >
          <h2 id="ket-qua-nhap" className="text-lg font-medium text-green-900">
            {result.already_confirmed ? 'Bản xem trước này đã được nhập trước đó' : 'Đã nhập xong'}
          </h2>
          <p className="text-green-900">
            Tạo mới <strong>{result.created}</strong> bản ghi, cập nhật{' '}
            <strong>{result.updated}</strong> bản ghi, giữ nguyên <strong>{result.unchanged}</strong>{' '}
            bản ghi.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => reset()}
              className="btn-primary"
            >
              Nhập tệp khác
            </button>
            <Link
              to="/"
              className="btn-secondary"
            >
              Về trang chủ
            </Link>
          </div>
        </section>
      </div>
    )
  }

  const shownRows = preview
    ? onlyProblems
      ? preview.rows.filter((row) => row.status !== 'ok')
      : preview.rows
    : []

  return (
    <div className="space-y-6">
      <Stepper current={confirmMutation.isPending ? 3 : preview ? 2 : 1} />
      <section
        aria-labelledby="chon-loai-nhap"
        className="card space-y-4 p-6"
      >
        <h2 id="chon-loai-nhap" className="text-lg font-medium">
          Nhập dữ liệu cho lớp {className}
        </h2>

        <div role="group" aria-label="Loại dữ liệu" className="flex flex-wrap gap-2">
          {kinds.map((kind) => (
            <button
              key={kind}
              type="button"
              aria-pressed={settings.kind === kind}
              disabled={busy}
              onClick={() => settings.kind !== kind && reset({ kind })}
              className={`rounded-xl border px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-60 ${
                settings.kind === kind
                  ? 'border-brand-700 bg-brand-700 text-white'
                  : 'border-slate-300 hover:bg-slate-100'
              }`}
            >
              {KIND_LABELS[kind]}
            </button>
          ))}
        </div>

        {settings.kind === 'assessments' && (
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-medium text-slate-700">
              Môn
              <select
                value={settings.subjectId ?? ''}
                disabled={busy}
                onChange={(event) => changeSettings({ subjectId: Number(event.target.value) })}
                className={selectClass()}
              >
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="block text-sm font-medium text-slate-700">
              Học kỳ
              <select
                value={settings.semester}
                disabled={busy}
                onChange={(event) => changeSettings({ semester: Number(event.target.value) })}
                className={selectClass()}
              >
                <option value={1}>Học kỳ I</option>
                <option value={2}>Học kỳ II</option>
              </select>
            </label>
            <label className="flex items-start gap-2 text-sm text-slate-700 sm:col-span-2">
              <input
                type="checkbox"
                checked={settings.allowPartial}
                disabled={busy}
                onChange={(event) => changeSettings({ allowPartial: event.target.checked })}
                className="mt-1"
              />
              <span>
                Cho phép nhập dở (thiếu một số đầu điểm). Mặc định thiếu đầu điểm là lỗi; ô trống
                không bao giờ xoá điểm đã có.
              </span>
            </label>
          </div>
        )}

        {settings.kind === 'conduct' && (
          <label className="block text-sm font-medium text-slate-700 sm:max-w-xs">
            Kỳ rèn luyện
            <select
              value={settings.period}
              disabled={busy}
              onChange={(event) => changeSettings({ period: event.target.value as ConductPeriod })}
              className={selectClass()}
            >
              {PERIODS.map((period) => (
                <option key={period} value={period}>
                  {PERIOD_LABELS[period]}
                </option>
              ))}
            </select>
          </label>
        )}

        <FilePicker file={file} onPick={pickFile} disabled={busy} />

        {previewMutation.isPending && (
          <p aria-live="polite" className="text-sm text-slate-600">
            Đang đọc và kiểm tra tệp…
          </p>
        )}
        {error !== null && (
          <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
            {error}
          </p>
        )}
      </section>

      {preview && (
        <section aria-labelledby="xem-truoc" className="space-y-4">
          <h2 id="xem-truoc" className="text-lg font-medium">
            Xem trước: {preview.file_name}
          </h2>
          {preview.notes.length > 0 && (
            <ul className="space-y-1 rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
              {preview.notes.map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          )}

          <MappingEditor
            key={`${preview.file_name}|${preview.header_line}|${preview.fields.map((f) => f.column).join('|')}`}
            preview={preview}
            templates={templates.data ?? []}
            pending={busy}
            onApply={applyMapping}
            onUseTemplate={applyTemplate}
          />

          {preview.missing_required.length === 0 && (
            <>
              <SummaryCards summary={preview.summary} />

              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={onlyProblems}
                  onChange={(event) => setOnlyProblems(event.target.checked)}
                />
                Chỉ hiện dòng lỗi và cảnh báo
              </label>

              {shownRows.length > 0 ? (
                <PreviewTable rows={shownRows} fields={preview.fields} />
              ) : (
                <p className="card p-4 text-sm text-slate-600">
                  Không có dòng nào để hiển thị.
                </p>
              )}
              {preview.truncated && (
                <p className="text-sm text-slate-500">
                  Chỉ hiện một phần các dòng bình thường; mọi dòng lỗi và cảnh báo luôn có đủ. Khi
                  xác nhận, hệ thống vẫn nhập toàn bộ tệp.
                </p>
              )}

              <div className="space-y-3 card p-4">
                {preview.summary.error_rows > 0 && (
                  <p role="alert" className="text-sm text-red-700">
                    Tệp còn {preview.summary.error_rows} dòng lỗi nên chưa thể nhập. Hãy sửa tệp rồi
                    tải lại; khi còn lỗi hệ thống không ghi gì (kể cả các dòng đúng).
                  </p>
                )}
                {preview.can_confirm && !preview.summary.has_changes && (
                  <p className="text-sm text-slate-600">
                    Mọi dữ liệu trong tệp đã có đúng như vậy trong hệ thống, không có gì để nhập.
                  </p>
                )}
                {preview.can_confirm && preview.summary.has_changes && (
                  <p className="text-sm text-slate-600">
                    Sẽ tạo mới {preview.summary.records_to_create} bản ghi và cập nhật{' '}
                    {preview.summary.records_to_update} bản ghi. Chưa có gì được ghi cho tới khi bạn
                    xác nhận.
                    {preview.expires_at &&
                      ` Bản xem trước hết hạn lúc ${new Date(preview.expires_at).toLocaleString('vi-VN')}.`}
                  </p>
                )}
                <button
                  type="button"
                  disabled={
                    busy ||
                    !preview.can_confirm ||
                    !preview.summary.has_changes ||
                    preview.job_id === null
                  }
                  onClick={() => preview.job_id && confirmMutation.mutate(preview.job_id)}
                  className="btn-primary"
                >
                  {confirmMutation.isPending ? 'Đang nhập…' : 'Xác nhận nhập'}
                </button>
              </div>
            </>
          )}
        </section>
      )}
    </div>
  )
}
