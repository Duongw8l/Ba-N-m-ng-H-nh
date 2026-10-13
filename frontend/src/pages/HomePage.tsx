import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { SchoolAlertsPanel } from '../components/alerts/SchoolAlertsPanel'
import { describeRole } from '../auth/roles'
import { GradeCards } from '../components/GradeCards'
import { HomeroomClasses } from '../components/HomeroomClasses'
import { Icon } from '../components/Icon'
import { QueryState } from '../components/QueryState'
import { TeachingTable } from '../components/TeachingTable'
import { useAssignments } from '../hooks/useAssignments'

function Notice({ icon = 'info', children }: { icon?: 'info' | 'book'; children: ReactNode }) {
  return (
    <div className="card flex items-start gap-4 p-5 text-slate-600">
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-tint text-brand-700 dark:text-brand-300">
        <Icon name={icon} />
      </span>
      <p className="pt-1.5">{children}</p>
    </div>
  )
}

const ADMIN_SHORTCUTS: { to: string; icon: 'users' | 'layers' | 'book'; title: string; text: string }[] = [
  {
    to: '/admin/users',
    icon: 'users',
    title: 'Tài khoản',
    text: 'Tạo tài khoản giáo viên, Ban giám hiệu; đặt lại mật khẩu, khoá và mở khoá.',
  },
  {
    to: '/admin/school',
    icon: 'layers',
    title: 'Năm học & lớp',
    text: 'Năm học, các lớp, giáo viên chủ nhiệm; vào từng lớp để phân công và nhập danh sách học sinh.',
  },
  {
    to: '/admin/regulations',
    icon: 'book',
    title: 'Văn bản quy định',
    text: 'Thông tư 22, quy chế thi, nội quy... mà Trợ lý AI được phép trích dẫn.',
  },
]

// Lối tắt của Admin tới các việc cấu hình. Quản trị viên không xem điểm hay danh sách học sinh.
function AdminShortcuts() {
  return (
    <section aria-labelledby="quan-tri" className="space-y-3">
      <h2 id="quan-tri" className="text-base font-semibold tracking-tight">
        Quản trị hệ thống
      </h2>
      <div className="grid gap-4 md:grid-cols-3">
        {ADMIN_SHORTCUTS.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="card flex items-start gap-4 p-5 transition-shadow hover:shadow-pop"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-tint text-brand-700 dark:text-brand-300">
              <Icon name={item.icon} />
            </span>
            <span>
              <span className="block font-semibold">{item.title}</span>
              <span className="mt-1 block text-sm text-slate-500">{item.text}</span>
            </span>
          </Link>
        ))}
      </div>
      <p className="text-sm text-slate-500">
        Quản trị viên không xem điểm hay danh sách học sinh.
      </p>
    </section>
  )
}

const TODAY = new Intl.DateTimeFormat('vi-VN', {
  weekday: 'long',
  day: 'numeric',
  month: 'long',
  year: 'numeric',
})

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
            <section className="relative overflow-hidden rounded-3xl bg-linear-to-br from-brand-800 via-brand-700 to-brand-500 p-6 text-white shadow-card sm:p-8">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -top-16 -right-10 h-64 w-64 rounded-full bg-white/10 blur-2xl"
              />
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -bottom-20 left-1/3 h-56 w-56 rounded-full bg-brand-300/20 blur-3xl"
              />
              <p className="relative text-sm font-medium text-brand-100 first-letter:uppercase">
                {TODAY.format(new Date())}
              </p>
              <h1 className="relative mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
                Xin chào, {data.user.full_name}
              </h1>
              <p className="relative mt-3 inline-flex items-center gap-2 rounded-full bg-white/15 px-3 py-1 text-sm font-medium ring-1 ring-white/20">
                <Icon name="user" className="h-4 w-4" />
                {describeRole(data)}
              </p>
            </section>

            {role === 'principal' && <GradeCards grades={data.grades} />}
            {role === 'principal' && <SchoolAlertsPanel />}
            {data.homeroom_classes.length > 0 && (
              <HomeroomClasses classes={data.homeroom_classes} />
            )}
            {data.teaching.length > 0 && <TeachingTable items={data.teaching} />}

            {role === 'admin' && <AdminShortcuts />}
            {role === 'teacher' && nothingAssigned && (
              <Notice>Bạn chưa được phân công lớp hay môn nào. Hãy liên hệ giáo vụ.</Notice>
            )}
          </>
        )
      }}
    </QueryState>
  )
}
