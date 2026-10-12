import type { ReactNode } from 'react'
import { useAuth } from '../auth/context'
import { describeRole } from '../auth/roles'
import { AppHeader } from '../components/AppHeader'
import { GradeCards } from '../components/GradeCards'
import { HomeroomClasses } from '../components/HomeroomClasses'
import { TeachingTable } from '../components/TeachingTable'
import { useAssignments } from '../hooks/useAssignments'

function Notice({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-xl border border-slate-200 bg-white p-6 text-slate-600 shadow-sm">
      {children}
    </p>
  )
}

// Trang chủ thay đổi theo vai trò (DESIGN mục 8), dựa trên GET /me/assignments:
// GVBM thấy lớp-môn đang dạy; GVCN thấy thêm lớp chủ nhiệm (quyền cộng dồn); BGH thấy các khối.
export default function HomePage() {
  const { logout } = useAuth()
  const assignments = useAssignments()

  if (assignments.isPending) {
    return (
      <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-600">
        <p className="mx-auto max-w-3xl" aria-live="polite">
          Đang tải…
        </p>
      </main>
    )
  }

  if (assignments.isError) {
    return (
      <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-900">
        <div className="mx-auto max-w-3xl space-y-4">
          <p role="alert" className="rounded-md bg-red-50 p-3 text-red-700">
            Không tải được thông tin của bạn. Hãy thử lại hoặc đăng nhập lại.
          </p>
          <div className="flex gap-3">
            <button
              type="button"
              onClick={() => void assignments.refetch()}
              className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800"
            >
              Thử lại
            </button>
            <button
              type="button"
              onClick={logout}
              className="rounded-md border border-slate-300 px-4 py-2 font-medium hover:bg-slate-100"
            >
              Đăng xuất
            </button>
          </div>
        </div>
      </main>
    )
  }

  const data = assignments.data
  const { role } = data.user
  const nothingAssigned = data.homeroom_classes.length === 0 && data.teaching.length === 0

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <AppHeader fullName={data.user.full_name} roleLabel={describeRole(data)} onLogout={logout} />
      <main className="mx-auto max-w-3xl space-y-6 px-4 py-8">
        <h1 className="text-xl font-semibold">Xin chào, {data.user.full_name}</h1>

        {role === 'principal' && <GradeCards grades={data.grades} />}
        {data.homeroom_classes.length > 0 && <HomeroomClasses classes={data.homeroom_classes} />}
        {data.teaching.length > 0 && <TeachingTable items={data.teaching} />}

        {role === 'admin' && (
          <Notice>
            Tài khoản quản trị: các chức năng cấu hình (năm học, lớp, phân công, tài khoản, văn bản
            quy định) sẽ có ở bản sau. Quản trị viên không xem điểm hay danh sách học sinh.
          </Notice>
        )}
        {role === 'teacher' && nothingAssigned && (
          <Notice>Bạn chưa được phân công lớp hay môn nào. Hãy liên hệ giáo vụ.</Notice>
        )}
      </main>
    </div>
  )
}
