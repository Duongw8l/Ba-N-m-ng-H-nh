import { useState } from 'react'
import type { FormEvent } from 'react'
import type { SchoolYear } from '../../api/admin'
import { useSaveSchoolYear } from '../../hooks/useAdmin'
import { ErrorAlert, SuccessNote } from './shared'

// Năm học bắt đầu vào tháng 9: từ tháng 8 trở đi là năm học của năm nay, trước đó là của năm ngoái.
function defaultYear(): { name: string; start: string; end: string } {
  const now = new Date()
  const first = now.getMonth() >= 7 ? now.getFullYear() : now.getFullYear() - 1
  return { name: `${first}-${first + 1}`, start: `${first}-09-05`, end: `${first + 1}-05-31` }
}

// Năm học duy nhất của trường (D-098): tạo lần đầu hoặc sửa. Không đổi được khoảng ngày để loại bỏ các
// ngày đã có điểm danh (back-end từ chối và nêu lý do).
export function SchoolYearForm({ year }: { year: SchoolYear | null }) {
  const mutation = useSaveSchoolYear()
  const fallback = defaultYear()
  const [name, setName] = useState(year?.name ?? fallback.name)
  const [start, setStart] = useState(year?.start_date ?? fallback.start)
  const [end, setEnd] = useState(year?.end_date ?? fallback.end)

  const valid = name.trim() !== '' && start !== '' && end !== '' && start < end
  const dirty =
    year === null || name.trim() !== year.name || start !== year.start_date || end !== year.end_date

  function submit(event: FormEvent) {
    event.preventDefault()
    if (valid && dirty && !mutation.isPending) {
      mutation.mutate({ name: name.trim(), start_date: start, end_date: end })
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      {year === null && (
        <p className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
          Chưa có năm học. Hãy tạo năm học trước, sau đó mới thêm được lớp.
        </p>
      )}
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="nam-hoc-ten" className="label">
            Tên năm học
          </label>
          <input
            id="nam-hoc-ten"
            type="text"
            value={name}
            maxLength={20}
            disabled={mutation.isPending}
            onChange={(event) => {
              setName(event.target.value)
              mutation.reset()
            }}
            className="input mt-1"
          />
        </div>
        <div>
          <label htmlFor="nam-hoc-bat-dau" className="label">
            Ngày bắt đầu
          </label>
          <input
            id="nam-hoc-bat-dau"
            type="date"
            value={start}
            disabled={mutation.isPending}
            onChange={(event) => {
              setStart(event.target.value)
              mutation.reset()
            }}
            className="input mt-1"
          />
        </div>
        <div>
          <label htmlFor="nam-hoc-ket-thuc" className="label">
            Ngày kết thúc
          </label>
          <input
            id="nam-hoc-ket-thuc"
            type="date"
            value={end}
            disabled={mutation.isPending}
            onChange={(event) => {
              setEnd(event.target.value)
              mutation.reset()
            }}
            className="input mt-1"
          />
        </div>
      </div>
      {start !== '' && end !== '' && start >= end && (
        <p className="text-sm text-red-700">Ngày bắt đầu phải trước ngày kết thúc.</p>
      )}
      <button type="submit" disabled={!valid || !dirty || mutation.isPending} className="btn-primary">
        {mutation.isPending ? 'Đang lưu…' : year === null ? 'Tạo năm học' : 'Lưu năm học'}
      </button>
      {mutation.isSuccess && <SuccessNote>Đã lưu năm học.</SuccessNote>}
      {mutation.isError && <ErrorAlert error={mutation.error} />}
    </form>
  )
}
