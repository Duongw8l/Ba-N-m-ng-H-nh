import type { ReactNode } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import type { ImportKind } from '../api/imports'
import { useAuth } from '../auth/context'
import { describeRole } from '../auth/roles'
import { AppHeader } from '../components/AppHeader'
import { ImportWizard } from '../components/import/ImportWizard'
import { useAssignments } from '../hooks/useAssignments'

const KINDS: ImportKind[] = ['assessments', 'attendance', 'conduct']

function Shell({ children, header }: { children: ReactNode; header?: ReactNode }) {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {header}
      <main className="mx-auto max-w-6xl space-y-6 px-4 py-8">{children}</main>
    </div>
  )
}

// Nhập điểm, điểm danh, rèn luyện từ tệp Excel/CSV cho một lớp (DESIGN mục 4). Quyền ghi hẹp hơn
// quyền xem: điểm do giáo viên được phân công đúng lớp-môn nhập; điểm danh và rèn luyện do GVCN.
// Back-end kiểm lại quyền ở mọi bước; trang này chỉ ẩn những gì người dùng chắc chắn không được làm.
export default function ImportPage() {
  const { logout } = useAuth()
  const assignments = useAssignments()
  const params = useParams()
  const [searchParams] = useSearchParams()
  const classId = Number(params.classId)

  if (assignments.isPending) {
    return (
      <Shell>
        <p aria-live="polite" className="text-slate-600">
          Đang tải…
        </p>
      </Shell>
    )
  }
  if (assignments.isError) {
    return (
      <Shell>
        <p role="alert" className="rounded-md bg-red-50 p-3 text-red-700">
          Không tải được thông tin của bạn. Hãy quay lại trang chủ rồi thử lại.
        </p>
        <Link to="/" className="font-medium text-blue-700 hover:underline">
          ← Trang chủ
        </Link>
      </Shell>
    )
  }

  const data = assignments.data
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
    <Shell
      header={
        <AppHeader
          wide
          fullName={data.user.full_name}
          roleLabel={describeRole(data)}
          onLogout={logout}
        />
      }
    >
      <div className="flex items-center justify-between gap-4">
        <h1 className="text-xl font-semibold">Nhập dữ liệu từ tệp</h1>
        <Link to="/" className="text-sm font-medium text-blue-700 hover:underline">
          ← Trang chủ
        </Link>
      </div>

      {initialKind === undefined ? (
        <p className="rounded-xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm">
          Bạn không có quyền nhập dữ liệu cho lớp này. Điểm chỉ do giáo viên được phân công đúng
          lớp-môn nhập; điểm danh và rèn luyện do giáo viên chủ nhiệm nhập.
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
    </Shell>
  )
}
