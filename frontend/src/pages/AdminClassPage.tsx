import { Link, useParams } from 'react-router-dom'
import { AdminGate } from '../components/admin/shared'
import { AssignmentsPanel } from '../components/admin/AssignmentsPanel'
import { RemoveStudentForm } from '../components/admin/RemoveStudentForm'
import { ImportWizard } from '../components/import/ImportWizard'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useRefreshAdmin, useSchool, useTeachers } from '../hooks/useAdmin'

// Quản trị một lớp (Admin): phân công giảng dạy, nhập danh sách học sinh từ tệp, gỡ học sinh nhập nhầm.
// Chỉ hiện sĩ số, không có tên học sinh (D-039).
export default function AdminClassPage() {
  const params = useParams()
  const classId = Number(params.classId)
  const school = useSchool()
  const teachers = useTeachers()
  const refresh = useRefreshAdmin()

  return (
    <AdminGate>
      {() => (
        <QueryState query={school}>
          {(data) => {
            const current = data.classes.find((item) => item.id === classId)
            if (!current) {
              return (
                <>
                  <PageTitle title="Không tìm thấy lớp" />
                  <p className="card p-6 text-slate-600">
                    Lớp này không còn hoặc chưa tồn tại.{' '}
                    <Link to="/admin/school" className="link">
                      Về danh sách lớp
                    </Link>
                  </p>
                </>
              )
            }
            const sameGrade = data.classes.filter(
              (item) => item.grade_level === current.grade_level && item.id !== current.id,
            )
            return (
              <>
                <PageTitle
                  title={`Lớp ${current.name}`}
                  subtitle={`Khối ${current.grade_level} · ${current.student_count} học sinh · Chủ nhiệm: ${
                    current.homeroom_teacher?.full_name ?? 'chưa có'
                  }`}
                  actions={
                    <Link to="/admin/school" className="link text-sm">
                      ← Năm học & lớp
                    </Link>
                  }
                />
                <Panel
                  id="phan-cong"
                  title="Phân công giảng dạy"
                  description="Môn của lớp là các dòng phân công. Môn chưa có giáo viên thì chưa ai nhập được điểm."
                >
                  <QueryState query={teachers}>
                    {(teacherList) => (
                      <AssignmentsPanel
                        school={current}
                        sameGrade={sameGrade}
                        teachers={teacherList}
                      />
                    )}
                  </QueryState>
                </Panel>
                <Panel id="danh-sach-hoc-sinh" title="Danh sách học sinh">
                  <ImportWizard
                    key={current.id}
                    classId={current.id}
                    className={current.name}
                    kinds={['roster']}
                    subjects={[]}
                    initialKind="roster"
                    initialSubjectId={null}
                    home={{ to: '/admin/school', label: 'Về danh sách lớp' }}
                    onConfirmed={() => void refresh()}
                  />
                </Panel>
                <Panel
                  id="go-hoc-sinh"
                  title="Gỡ học sinh khỏi lớp"
                  description="Dùng khi nhập nhầm. Chỉ gỡ được học sinh chưa có điểm, điểm danh, rèn luyện hay cảnh báo."
                >
                  <RemoveStudentForm classId={current.id} className={current.name} />
                </Panel>
              </>
            )
          }}
        </QueryState>
      )}
    </AdminGate>
  )
}
