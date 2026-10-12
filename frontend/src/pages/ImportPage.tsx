import { Link, useParams, useSearchParams } from 'react-router-dom'
import type { ImportKind } from '../api/imports'
import { ImportWizard } from '../components/import/ImportWizard'
import { PageTitle } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useAssignments } from '../hooks/useAssignments'

const KINDS: ImportKind[] = ['assessments', 'attendance', 'conduct']

// Nhập điểm, điểm danh, rèn luyện từ tệp Excel/CSV cho một lớp (DESIGN mục 4). Quyền ghi hẹp hơn
// quyền xem: điểm do giáo viên được phân công đúng lớp-môn nhập; điểm danh và rèn luyện do GVCN.
// Back-end kiểm lại quyền ở mọi bước; trang này chỉ ẩn những gì người dùng chắc chắn không được làm.
export default function ImportPage() {
  const assignments = useAssignments()
  const params = useParams()
  const [searchParams] = useSearchParams()
  const classId = Number(params.classId)

  return (
    <QueryState query={assignments}>
      {(data) => {
        const subjects = data.teaching
          .filter((item) => item.class_id === classId)
          .map((item) => ({ id: item.subject_id, name: item.subject_name }))
        const homeroom = data.homeroom_classes.find((item) => item.id === classId)
        const className =
          homeroom?.name ?? data.teaching.find((item) => item.class_id === classId)?.class_name ?? ''
        const kinds: ImportKind[] = [
          ...(subjects.length > 0 ? (['assessments'] as const) : []),
          ...(homeroom ? (['attendance', 'conduct'] as const) : []),
        ]

        const requestedKind = searchParams.get('kind')
        const initialKind =
          KINDS.find((kind) => kind === requestedKind && kinds.includes(kind)) ?? kinds[0]
        const requestedSubject = Number(searchParams.get('subject'))
        const initialSubjectId = subjects.some((subject) => subject.id === requestedSubject)
          ? requestedSubject
          : null

        return (
          <>
            <PageTitle
              title="Nhập dữ liệu từ tệp"
              actions={
                <Link to="/" className="text-sm font-medium text-blue-700 hover:underline">
                  ← Trang chủ
                </Link>
              }
            />
            {initialKind === undefined ? (
              <p className="rounded-xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm">
                Bạn không có quyền nhập dữ liệu cho lớp này. Điểm chỉ do giáo viên được phân công
                đúng lớp-môn nhập; điểm danh và rèn luyện do giáo viên chủ nhiệm nhập.
              </p>
            ) : (
              <ImportWizard
                key={classId}
                classId={classId}
                className={className}
                kinds={kinds}
                subjects={subjects}
                initialKind={initialKind}
                initialSubjectId={initialSubjectId}
              />
            )}
          </>
        )
      }}
    </QueryState>
  )
}
