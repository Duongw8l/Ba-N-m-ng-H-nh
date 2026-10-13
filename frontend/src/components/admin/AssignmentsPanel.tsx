import { useState } from 'react'
import type { AdminClass, Teacher } from '../../api/admin'
import {
  useClassAssignments,
  useCopyAssignments,
  useRemoveAssignment,
  useSetAssignment,
} from '../../hooks/useAdmin'
import { QueryState } from '../QueryState'
import { ErrorAlert, SuccessNote } from './shared'
import { TeacherSelect } from './TeacherSelect'

interface AssignmentsPanelProps {
  school: AdminClass
  sameGrade: AdminClass[] // các lớp cùng khối (không kể lớp này) để sao chép phân công
  teachers: Teacher[]
}

// Giáo viên phụ trách từng môn của lớp. Môn của lớp chính là các dòng phân công: môn chưa có giáo viên
// thì chưa ai nhập được điểm. Gỡ phân công bị từ chối khi lớp đã có điểm môn đó; khi đó chỉ đổi giáo viên.
export function AssignmentsPanel({ school, sameGrade, teachers }: AssignmentsPanelProps) {
  const query = useClassAssignments(school.id)
  const assign = useSetAssignment(school.id)
  const remove = useRemoveAssignment(school.id)
  const copy = useCopyAssignments(school.id)
  const [source, setSource] = useState<number | ''>('')
  const [copied, setCopied] = useState<string | null>(null)
  const busy = assign.isPending || remove.isPending || copy.isPending
  const error = assign.error ?? remove.error ?? copy.error

  function change(subjectId: number, teacherId: number | null) {
    assign.reset()
    remove.reset()
    copy.reset()
    setCopied(null)
    if (teacherId === null) remove.mutate(subjectId)
    else assign.mutate({ subjectId, teacherId })
  }

  return (
    <div className="space-y-4">
      {sameGrade.length > 0 && (
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-48">
            <label htmlFor="sao-chep-tu" className="label">
              Sao chép giáo viên từ lớp cùng khối
            </label>
            <select
              id="sao-chep-tu"
              value={source}
              disabled={busy}
              onChange={(event) =>
                setSource(event.target.value === '' ? '' : Number(event.target.value))
              }
              className="input mt-1"
            >
              <option value="">— Chọn lớp —</option>
              {sameGrade.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} ({item.assigned_subject_count} môn)
                </option>
              ))}
            </select>
          </div>
          <button
            type="button"
            disabled={busy || source === ''}
            onClick={() => {
              if (source === '') return
              assign.reset()
              remove.reset()
              copy.mutate(source, {
                onSuccess: (data) =>
                  setCopied(
                    data.copied > 0
                      ? `Đã sao chép ${data.copied} môn còn trống. Môn đã có giáo viên được giữ nguyên.`
                      : 'Không có môn nào để sao chép: mọi môn của lớp nguồn đã có giáo viên ở lớp này.',
                  ),
              })
            }}
            className="btn-secondary"
          >
            {copy.isPending ? 'Đang sao chép…' : 'Sao chép'}
          </button>
        </div>
      )}

      <QueryState query={query}>
        {(data) => (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th scope="col" className="py-2 pr-4 font-medium">
                    Môn
                  </th>
                  <th scope="col" className="hidden px-3 py-2 font-medium sm:table-cell">
                    Đánh giá
                  </th>
                  <th scope="col" className="py-2 pl-3 font-medium">
                    Giáo viên phụ trách
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 align-middle">
                {data.subjects.map((row) => (
                  <tr key={row.subject_id}>
                    <th scope="row" className="py-2 pr-4 text-left font-medium">
                      {row.subject_name}
                      {row.is_elective && (
                        <span className="badge-neutral ml-2 align-middle">Tự chọn</span>
                      )}
                    </th>
                    <td className="hidden px-3 py-2 text-slate-600 sm:table-cell">
                      {row.assessment_type === 'score' ? 'Cho điểm' : 'Nhận xét'}
                    </td>
                    <td className="min-w-44 py-2 pl-3 sm:min-w-64">
                      <TeacherSelect
                        id={`day-${row.subject_id}`}
                        label={`Giáo viên môn ${row.subject_name}`}
                        hideLabel
                        teachers={teachers}
                        value={row.teacher?.id ?? null}
                        extra={row.teacher}
                        emptyLabel="— Chưa phân công —"
                        disabled={busy}
                        onChange={(teacherId) => change(row.subject_id, teacherId)}
                      />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </QueryState>
      {copied && <SuccessNote>{copied}</SuccessNote>}
      {error && <ErrorAlert error={error} />}
    </div>
  )
}
