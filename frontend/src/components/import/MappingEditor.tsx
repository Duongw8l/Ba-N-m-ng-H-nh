import { useState } from 'react'
import type { ImportPreview, MappingTemplate } from '../../api/imports'

export interface MappingChoice {
  mapping: Record<string, string | null>
  saveMappingAs?: string
  headerRow?: number
}

interface MappingEditorProps {
  preview: ImportPreview
  templates: MappingTemplate[]
  pending: boolean
  onApply: (choice: MappingChoice) => void
  onUseTemplate: (name: string) => void
}

const NONE = ''

// Chọn cột của tệp cho từng trường. Mở sẵn khi còn thiếu cột bắt buộc; nơi gọi đặt `key` theo kết quả
// xem trước để ô chọn được khởi tạo lại mỗi khi back-end trả ánh xạ mới.
export function MappingEditor({
  preview,
  templates,
  pending,
  onApply,
  onUseTemplate,
}: MappingEditorProps) {
  const [mapping, setMapping] = useState<Record<string, string>>(() =>
    Object.fromEntries(preview.fields.map((field) => [field.name, field.column ?? NONE])),
  )
  const [saveAs, setSaveAs] = useState('')
  const [headerRow, setHeaderRow] = useState('')
  const missing = preview.missing_required.length > 0

  function apply() {
    const row = Number.parseInt(headerRow, 10)
    onApply({
      // Chuỗi rỗng là bỏ chọn: gửi null để back-end hiểu là "không dùng cột nào cho trường này".
      mapping: Object.fromEntries(
        Object.entries(mapping).map(([field, column]) => [field, column === NONE ? null : column]),
      ),
      saveMappingAs: saveAs.trim() || undefined,
      headerRow: Number.isInteger(row) && row >= 1 ? row : undefined,
    })
  }

  return (
    <details
      open={missing}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"
    >
      <summary className="cursor-pointer font-medium">
        Cột của tệp
        {missing && (
          <span className="ml-2 rounded-full bg-red-100 px-2 py-0.5 text-sm text-red-700">
            Còn thiếu {preview.missing_required.length} cột bắt buộc
          </span>
        )}
      </summary>

      <div className="mt-4 space-y-4">
        {missing && (
          <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
            Chưa nhận ra cột: {preview.missing_required.join(', ')}. Hãy chọn cột tương ứng của
            tệp bên dưới rồi bấm “Áp dụng”.
          </p>
        )}
        <p className="text-sm text-slate-500">
          Dòng tiêu đề được dò ở dòng {preview.header_line} của tệp.
          {preview.ignored_columns.length > 0 &&
            ` Cột không dùng: ${preview.ignored_columns.join(', ')}.`}
        </p>

        {templates.length > 0 && (
          <label className="block text-sm font-medium text-slate-700">
            Dùng mẫu đã lưu
            <select
              value=""
              disabled={pending}
              onChange={(event) => event.target.value && onUseTemplate(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base sm:max-w-xs"
            >
              <option value="">— chọn mẫu —</option>
              {templates.map((template) => (
                <option key={template.name} value={template.name}>
                  {template.name}
                </option>
              ))}
            </select>
          </label>
        )}

        <div className="grid gap-3 sm:grid-cols-2">
          {preview.fields.map((field) => (
            <label key={field.name} className="block text-sm font-medium text-slate-700">
              {field.label}
              {field.required && <span className="text-red-600"> *</span>}
              <select
                value={mapping[field.name] ?? NONE}
                onChange={(event) =>
                  setMapping((current) => ({ ...current, [field.name]: event.target.value }))
                }
                className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base"
              >
                <option value={NONE}>— không dùng —</option>
                {preview.detected_columns.map((column) => (
                  <option key={column} value={column}>
                    {column}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          <label className="block text-sm font-medium text-slate-700">
            Dòng tiêu đề (để trống: tự dò)
            <input
              type="number"
              min={1}
              max={50}
              value={headerRow}
              onChange={(event) => setHeaderRow(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Lưu cách chọn cột này thành mẫu (tuỳ chọn)
            <input
              type="text"
              maxLength={100}
              value={saveAs}
              onChange={(event) => setSaveAs(event.target.value)}
              placeholder="Ví dụ: Sổ điểm trường"
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base"
            />
          </label>
        </div>

        <button
          type="button"
          onClick={apply}
          disabled={pending}
          className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {pending ? 'Đang kiểm tra…' : 'Áp dụng'}
        </button>
      </div>
    </details>
  )
}
