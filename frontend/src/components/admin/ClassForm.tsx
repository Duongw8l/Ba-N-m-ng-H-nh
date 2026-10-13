import { useState } from 'react'
import type { FormEvent } from 'react'
import type { Teacher } from '../../api/admin'
import { useCreateClass } from '../../hooks/useAdmin'
import { ErrorAlert, SuccessNote } from './shared'
import { TeacherSelect } from './TeacherSelect'

const GRADES = [10, 11, 12]

// Thêm lớp vào năm học. Tên lớp phải bắt đầu bằng số khối (ví dụ 11A9) và không trùng lớp khác.
export function ClassForm({ teachers }: { teachers: Teacher[] }) {
  const mutation = useCreateClass()
  const [grade, setGrade] = useState(10)
  const [name, setName] = useState('')
  const [teacherId, setTeacherId] = useState<number | null>(null)
  const [added, setAdded] = useState<string | null>(null)

  const trimmed = name.trim()
  const wrongPrefix = trimmed !== '' && !trimmed.startsWith(String(grade))
  const canSubmit = trimmed !== '' && !wrongPrefix && !mutation.isPending

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!canSubmit) return
    mutation.mutate(
      { grade_level: grade, name: trimmed, homeroom_teacher_id: teacherId },
      {
        onSuccess: (created) => {
          setAdded(`Đã thêm lớp ${created.name}.`)
          setName('')
          setTeacherId(null)
        },
      },
    )
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <div>
          <label htmlFor="lop-moi-khoi" className="label">
            Khối
          </label>
          <select
            id="lop-moi-khoi"
            value={grade}
            disabled={mutation.isPending}
            onChange={(event) => {
              setGrade(Number(event.target.value))
              setAdded(null)
            }}
            className="input mt-1"
          >
            {GRADES.map((value) => (
              <option key={value} value={value}>
                Khối {value}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="lop-moi-ten" className="label">
            Tên lớp
          </label>
          <input
            id="lop-moi-ten"
            type="text"
            value={name}
            maxLength={20}
            placeholder={`Ví dụ: ${grade}A9`}
            disabled={mutation.isPending}
            aria-invalid={wrongPrefix}
            onChange={(event) => {
              setName(event.target.value)
              setAdded(null)
              mutation.reset()
            }}
            className="input mt-1"
          />
          {wrongPrefix && (
            <p className="mt-1 text-xs text-red-700">Tên lớp khối {grade} phải bắt đầu bằng {grade}.</p>
          )}
        </div>
        <TeacherSelect
          id="lop-moi-gvcn"
          label="Giáo viên chủ nhiệm (có thể để trống)"
          teachers={teachers}
          value={teacherId}
          homeroomOnly
          emptyLabel="— Chưa có —"
          disabled={mutation.isPending}
          onChange={setTeacherId}
        />
      </div>
      <button type="submit" disabled={!canSubmit} className="btn-primary">
        {mutation.isPending ? 'Đang thêm…' : 'Thêm lớp'}
      </button>
      {added && <SuccessNote>{added}</SuccessNote>}
      {mutation.isError && <ErrorAlert error={mutation.error} />}
    </form>
  )
}
