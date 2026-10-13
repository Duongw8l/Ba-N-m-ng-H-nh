import type { Teacher, TeacherRef } from '../../api/admin'

interface TeacherSelectProps {
  id: string
  label: string
  teachers: Teacher[]
  value: number | null
  onChange: (teacherId: number | null) => void
  disabled?: boolean
  // Tên lớp đang sửa: giáo viên đang chủ nhiệm đúng lớp này không bị coi là "đã bận".
  currentClass?: string
  // Chọn GVCN thì loại giáo viên đang chủ nhiệm lớp khác; chọn người dạy thì không.
  homeroomOnly?: boolean
  emptyLabel: string
  hideLabel?: boolean
  // Giáo viên đang được chọn nhưng không còn trong danh sách (đã bị khoá): vẫn hiện để không bị trống.
  extra?: TeacherRef | null
}

// Ô chọn giáo viên. Với GVCN, giáo viên đang chủ nhiệm lớp khác bị tắt và ghi rõ lớp nào (mỗi giáo
// viên chỉ chủ nhiệm một lớp), tránh bấm rồi mới bị back-end từ chối.
export function TeacherSelect({
  id,
  label,
  teachers,
  value,
  onChange,
  disabled,
  currentClass,
  homeroomOnly = false,
  emptyLabel,
  hideLabel = false,
  extra = null,
}: TeacherSelectProps) {
  return (
    <div>
      <label htmlFor={id} className={hideLabel ? 'sr-only' : 'label'}>
        {label}
      </label>
      <select
        id={id}
        value={value ?? ''}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value === '' ? null : Number(event.target.value))}
        className={`input ${hideLabel ? '' : 'mt-1'}`}
      >
        <option value="">{emptyLabel}</option>
        {extra && !teachers.some((teacher) => teacher.id === extra.id) && (
          <option value={extra.id}>{extra.full_name} (đã bị khoá)</option>
        )}
        {teachers.map((teacher) => {
          const busy =
            homeroomOnly && teacher.homeroom_class !== null && teacher.homeroom_class !== currentClass
          return (
            <option key={teacher.id} value={teacher.id} disabled={busy && teacher.id !== value}>
              {teacher.full_name}
              {busy ? ` (đang chủ nhiệm ${teacher.homeroom_class})` : ''}
            </option>
          )
        })}
      </select>
    </div>
  )
}
