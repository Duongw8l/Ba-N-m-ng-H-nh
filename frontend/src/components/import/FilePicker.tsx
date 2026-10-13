import { useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'

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
      className={`flex cursor-pointer flex-col items-center justify-center gap-1 rounded-xl border-2 border-dashed px-4 py-8 text-center ${
        dragging ? 'border-blue-600 bg-blue-50' : 'border-slate-300 bg-white hover:bg-slate-50'
      } ${disabled ? 'cursor-not-allowed opacity-60' : ''}`}
    >
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
