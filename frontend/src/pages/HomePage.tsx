import type { ReactNode } from 'react'
import { GradeCards } from '../components/GradeCards'
import { HomeroomClasses } from '../components/HomeroomClasses'
import { QueryState } from '../components/QueryState'
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
  const assignments = useAssignments()

  return (
    <QueryState query={assignments}>
      {(data) => {
        const { role } = data.user
        const nothingAssigned = data.homeroom_classes.length === 0 && data.teaching.length === 0
        return (
          <>
            <h1 className="text-xl font-semibold">Xin chào, {data.user.full_name}</h1>

            {role === 'principal' && <GradeCards grades={data.grades} />}
            {data.homeroom_classes.length > 0 && (
              <HomeroomClasses classes={data.homeroom_classes} />
            )}
            {data.teaching.length > 0 && <TeachingTable items={data.teaching} />}

            {role === 'admin' && (
              <Notice>
                Tài khoản quản trị: các chức năng cấu hình (năm học, lớp, phân công, tài khoản, văn
                bản quy định) sẽ có ở bản sau. Quản trị viên không xem điểm hay danh sách học sinh.
              </Notice>
            )}
            {role === 'teacher' && nothingAssigned && (
              <Notice>Bạn chưa được phân công lớp hay môn nào. Hãy liên hệ giáo vụ.</Notice>
            )}
          </>
        )
      }}
    </QueryState>
  )
}
