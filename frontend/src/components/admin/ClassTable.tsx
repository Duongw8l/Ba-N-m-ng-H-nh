import { useState } from 'react'
import { Link } from 'react-router-dom'
import type { AdminClass, Teacher } from '../../api/admin'
import { useDeleteClass, useUpdateClass } from '../../hooks/useAdmin'
import { ErrorAlert } from './shared'
import { TeacherSelect } from './TeacherSelect'

interface ClassTableProps {
  classes: AdminClass[]
  teachers: Teacher[]
  subjectCount: number
}

// Các lớp theo khối: đổi GVCN ngay trên dòng, vào trang quản trị lớp, xoá lớp đã trống (không còn học
// sinh và phân công).
export function ClassTable({ classes, teachers, subjectCount }: ClassTableProps) {
  const update = useUpdateClass()
  const remove = useDeleteClass()
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  if (classes.length === 0) {
    return <p className="text-sm text-slate-600">Chưa có lớp nào. Hãy thêm lớp ở phần bên dưới.</p>
  }

  const error = update.error ?? remove.error
  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="data-table min-w-max">
          <thead>
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">
                Lớp
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Giáo viên chủ nhiệm
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Sĩ số
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Môn đã phân công
              </th>
              <th scope="col" className="py-2 pl-3 font-medium">
                <span className="sr-only">Thao tác</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-middle">
            {classes.map((item) => {
              const empty = item.student_count === 0 && item.assigned_subject_count === 0
              const confirming = confirmingId === item.id
              const busy = update.isPending || remove.isPending
              return (
                <tr key={item.id}>
                  <th scope="row" className="py-2 pr-4 text-left font-medium">
                    {item.name}
                    <span className="ml-2 text-xs font-normal text-slate-500">
                      Khối {item.grade_level}
                    </span>
                  </th>
                  <td className="min-w-56 px-3 py-2">
                    <TeacherSelect
                      id={`gvcn-${item.id}`}
                      label={`Giáo viên chủ nhiệm lớp ${item.name}`}
                      hideLabel
                      teachers={teachers}
                      value={item.homeroom_teacher?.id ?? null}
                      currentClass={item.name}
                      homeroomOnly
                      extra={item.homeroom_teacher}
                      emptyLabel="— Chưa có —"
                      disabled={busy}
                      onChange={(teacherId) => {
                        update.reset()
                        update.mutate({ id: item.id, body: { homeroom_teacher_id: teacherId } })
                      }}
                    />
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{item.student_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {item.assigned_subject_count} / {subjectCount}
                  </td>
                  <td className="py-2 pl-3">
                    {confirming ? (
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="text-xs text-slate-600">Xoá lớp {item.name}?</span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() =>
                            remove.mutate(item.id, { onSettled: () => setConfirmingId(null) })
                          }
                          className="btn-primary btn-sm"
                        >
                          {remove.isPending ? 'Đang xoá…' : 'Xác nhận xoá'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setConfirmingId(null)}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Huỷ
                        </button>
                      </span>
                    ) : (
                      <span className="flex flex-wrap gap-2">
                        <Link
                          to={`/admin/classes/${item.id}`}
                          aria-label={`Quản lý lớp ${item.name}`}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Quản lý
                        </Link>
                        <button
                          type="button"
                          disabled={!empty}
                          title={empty ? undefined : 'Chỉ xoá được lớp chưa có học sinh và phân công'}
                          onClick={() => {
                            remove.reset()
                            setConfirmingId(item.id)
                          }}
                          aria-label={`Xoá lớp ${item.name}`}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Xoá
                        </button>
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {error && <ErrorAlert error={error} />}
    </div>
  )
}
