import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { useUploadRegulation } from '../../hooks/useRegulations'
import { FilePicker } from '../import/FilePicker'

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

function nameFromFile(file: File): string {
  return file.name.replace(/\.[^.]+$/, '').replace(/[-_]+/g, ' ')
}

// Tải một văn bản mới: nhập tên hiển thị (hiện trong trích dẫn) và chọn tệp. Back-end đọc, tách theo
// Điều/Khoản và tính vector ngay trong yêu cầu nên có thể mất vài chục giây.
export function UploadForm() {
  const mutation = useUploadRegulation()
  const [name, setName] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [done, setDone] = useState<string | null>(null)

  const canSubmit = name.trim() !== '' && file !== null && !mutation.isPending

  function pick(picked: File) {
    setFile(picked)
    setDone(null)
    mutation.reset()
    if (name.trim() === '') setName(nameFromFile(picked))
  }

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!file || !canSubmit) return
    mutation.mutate(
      { name: name.trim(), file },
      {
        onSuccess: (document) => {
          setDone(
            `Đã nạp "${document.name}": ${document.article_count} điều, ${document.chunk_count} đoạn.`,
          )
          setName('')
          setFile(null)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div>
        <label htmlFor="ten-van-ban" className="block text-sm font-medium">
          Tên văn bản (hiện trong trích dẫn của Trợ lý AI)
        </label>
        <input
          id="ten-van-ban"
          type="text"
          value={name}
          maxLength={200}
          disabled={mutation.isPending}
          onChange={(event) => setName(event.target.value)}
          placeholder="Ví dụ: Thông tư 22/2021/TT-BGDĐT"
          className="input mt-1 max-w-xl"
        />
      </div>
      <FilePicker
        file={file}
        onPick={pick}
        disabled={mutation.isPending}
        accept=".pdf,.docx,.txt"
        hint="Nhận .pdf (có lớp chữ, không phải bản quét), .docx hoặc .txt (UTF-8), tối đa 20 MB"
      />
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={!canSubmit}
          className="btn-primary"
        >
          Tải lên và xử lý
        </button>
        {mutation.isPending && (
          <p aria-live="polite" className="text-sm text-slate-600">
            Đang xử lý… (đọc tệp, tách Điều/Khoản và tính vector, có thể mất vài chục giây)
          </p>
        )}
      </div>
      {done && (
        <p role="status" className="rounded-xl bg-green-50 p-3 text-sm text-green-800 ring-1 ring-green-200">
          {done}
        </p>
      )}
      {mutation.isError && (
        <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
          {errorText(mutation.error)}
        </p>
      )}
    </form>
  )
}
