import { useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import { Icon } from '../Icon'

interface FilePickerProps {
  file: File | null
  onPick: (file: File) => void
  disabled?: boolean
  // Mặc định cho nhập dữ liệu lớp học; trang văn bản quy định dùng loại tệp khác.
  accept?: string
  hint?: string
}

// Vùng kéo thả tệp (sự kiện kéo thả có sẵn của trình duyệt) kèm nút chọn tệp.
export function FilePicker({
  file,
  onPick,
  disabled = false,
  accept = '.xlsx,.csv',
  hint = 'Chỉ nhận .xlsx hoặc .csv (UTF-8), tối đa 5 MB',
}: FilePickerProps) {
  const [dragging, setDragging] = useState(false)

  function onDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    const dropped = event.dataTransfer.files[0]
    if (!disabled && dropped) onPick(dropped)
  }

  function onChange(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0]
    if (picked) onPick(picked)
    event.target.value = '' // cho phép chọn lại đúng tệp đó sau khi sửa tệp
  }

  return (
    <label
      onDragOver={(event) => {
        event.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      className={`flex cursor-pointer flex-col items-center justify-center gap-1.5 rounded-2xl border-2 border-dashed px-4 py-10 text-center transition-colors ${
        dragging ? 'border-brand-600 bg-tint' : 'border-slate-300 bg-slate-50/60 hover:border-brand-400 hover:bg-tint'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
      <span className="flex h-12 w-12 items-center justify-center rounded-2xl bg-tint text-brand-700 dark:text-brand-300">
        <Icon name={file ? 'file' : 'upload'} className="h-6 w-6" />
      </span>
      <span className="font-medium text-slate-800">
        {file ? file.name : 'Kéo thả tệp vào đây hoặc bấm để chọn tệp'}
      </span>
      <span className="text-sm text-slate-500">
        {file
          ? `${(file.size / 1024).toLocaleString('vi-VN', { maximumFractionDigits: 1 })} KB · bấm để chọn tệp khác`
          : hint}
      </span>
      <input
        type="file"
        accept={accept}
        disabled={disabled}
        onChange={onChange}
        className="sr-only"
      />
    </label>
  )
}
