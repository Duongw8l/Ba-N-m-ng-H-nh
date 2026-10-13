import { AdminGate } from '../components/admin/shared'
import { ClassForm } from '../components/admin/ClassForm'
import { ClassTable } from '../components/admin/ClassTable'
import { SchoolYearForm } from '../components/admin/SchoolYearForm'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useSchool, useTeachers } from '../hooks/useAdmin'

// Năm học và các lớp (Admin): năm học duy nhất, thêm lớp, giáo viên chủ nhiệm. Phân công giảng dạy và
// danh sách học sinh của từng lớp nằm ở trang quản trị lớp. Chỉ hiện số đếm, không có tên học sinh.
export default function AdminSchoolPage() {
  const school = useSchool()
  const teachers = useTeachers()

  return (
    <AdminGate>
      {() => (
        <>
          <PageTitle
            title="Năm học & lớp"
            subtitle="Trường dùng một năm học. Mỗi giáo viên chỉ chủ nhiệm một lớp; giáo viên bộ môn được gán ở trang quản trị của từng lớp."
          />
          <QueryState query={school}>
            {(data) => (
              <>
                <Panel id="nam-hoc" title="Năm học">
                  <SchoolYearForm key={data.school_year?.id ?? 'moi'} year={data.school_year} />
                </Panel>
                <Panel id="cac-lop" title="Các lớp">
                  <QueryState query={teachers}>
                    {(teacherList) => (
                      <ClassTable
                        classes={data.classes}
                        teachers={teacherList}
                        subjectCount={data.subject_count}
                      />
                    )}
                  </QueryState>
                </Panel>
                {data.school_year && (
                  <Panel id="them-lop" title="Thêm lớp">
                    <QueryState query={teachers}>
                      {(teacherList) => <ClassForm teachers={teacherList} />}
                    </QueryState>
                  </Panel>
                )}
              </>
            )}
          </QueryState>
        </>
      )}
    </AdminGate>
  )
}
