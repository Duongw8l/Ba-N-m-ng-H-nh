import { useState } from 'react'
import type { FormEvent } from 'react'
import { useRemoveStudent } from '../../hooks/useAdmin'
import { ErrorAlert, SuccessNote } from './shared'

// Gỡ một học sinh nhập nhầm khỏi lớp, theo mã do Admin gõ vào. Quản trị viên không xem được danh sách
// hay dữ liệu học sinh (D-039), nên không có nút "gỡ" cạnh từng tên; back-end chỉ gỡ khi em chưa có
// điểm, điểm danh, rèn luyện hay cảnh báo, và không nêu nội dung dữ liệu khi từ chối.
export function RemoveStudentForm({ classId, className }: { classId: number; className: string }) {
  const mutation = useRemoveStudent(classId)
  const [code, setCode] = useState('')
  const [confirming, setConfirming] = useState(false)
  const [done, setDone] = useState<string | null>(null)

  const trimmed = code.trim().toUpperCase()

  function submit(event: FormEvent) {
    event.preventDefault()
    if (trimmed === '' || mutation.isPending) return
    if (!confirming) {
      setConfirming(true)
      return
    }
    mutation.mutate(trimmed, {
      onSuccess: () => {
        setDone(`Đã gỡ học sinh ${trimmed} khỏi lớp ${className}.`)
        setCode('')
      },
      onSettled: () => setConfirming(false),
    })
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div className="max-w-sm">
        <label htmlFor="go-ma-hs" className="label">
          Mã học sinh cần gỡ
        </label>
        <input
          id="go-ma-hs"
          type="text"
          value={code}
          maxLength={20}
          disabled={mutation.isPending}
          onChange={(event) => {
            setCode(event.target.value)
            setConfirming(false)
            setDone(null)
            mutation.reset()
          }}
          placeholder="Ví dụ: HS1109001"
          autoComplete="off"
          className="input mt-1 font-mono"
        />
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={trimmed === '' || mutation.isPending}
          className={confirming ? 'btn-primary' : 'btn-secondary'}
        >
          {mutation.isPending
            ? 'Đang gỡ…'
            : confirming
              ? `Xác nhận gỡ ${trimmed} khỏi lớp ${className}`
              : 'Gỡ khỏi lớp'}
        </button>
        {confirming && !mutation.isPending && (
          <button type="button" onClick={() => setConfirming(false)} className="btn-secondary">
            Huỷ
          </button>
        )}
      </div>
      {done && <SuccessNote>{done}</SuccessNote>}
      {mutation.isError && <ErrorAlert error={mutation.error} />}
    </form>
  )
}
