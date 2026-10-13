import { NavLink, Outlet } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { describeRole } from '../auth/roles'
import { useAssignments } from '../hooks/useAssignments'
import { AssistantProvider } from './assistant/AssistantProvider'
import { ChatDock } from './assistant/ChatDock'

interface NavItem {
  to: string
  label: string
  end?: boolean
}

function linkClass({ isActive }: { isActive: boolean }): string {
  return `rounded-md px-3 py-1.5 font-medium ${
    isActive ? 'bg-blue-50 text-blue-800' : 'text-slate-700 hover:bg-slate-100'
  }`
}

// Khung chung của mọi trang cần đăng nhập: thanh điều hướng theo vai trò (lớp chủ nhiệm, các khối của
// BGH), Trợ lý AI, Nhận xét & báo cáo, người dùng và đăng xuất. Lớp-môn đang dạy vào từ trang chủ vì
// số lượng lớn.
export function AppLayout() {
  const { logout } = useAuth()
  const assignments = useAssignments()
  const data = assignments.data

  const items: NavItem[] = [{ to: '/', label: 'Trang chủ', end: true }]
  if (data) {
    items.push(
      ...data.homeroom_classes.map((item) => ({
        to: `/classes/${item.id}`,
        label: `Lớp ${item.name}`,
      })),
      ...data.grades.map((grade) => ({ to: `/grades/${grade}`, label: `Khối ${grade}` })),
    )
  }
  items.push(
    { to: '/assistant', label: 'Trợ lý AI' },
    { to: '/reports', label: 'Nhận xét & báo cáo' },
  )
  if (data?.user.role === 'admin') {
    items.push({ to: '/admin/regulations', label: 'Văn bản quy định' })
  }

  return (
    <AssistantProvider>
      <div className="min-h-screen bg-slate-50 text-slate-900">
        <a
          href="#noi-dung"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:rounded-md focus:bg-white focus:px-3 focus:py-2"
        >
          Bỏ qua điều hướng
        </a>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-x-6 gap-y-2 px-4 py-3">
            <span className="font-semibold">Trợ lý AI quản lý lớp học</span>
            <nav aria-label="Điều hướng chính">
              <ul className="flex flex-wrap gap-1 text-sm">
                {items.map((item) => (
                  <li key={item.to}>
                    <NavLink to={item.to} end={item.end} className={linkClass}>
                      {item.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </nav>
            <div className="flex items-center gap-4 text-sm">
              {data && (
                <span className="text-right">
                  <span className="block font-medium">{data.user.full_name}</span>
                  <span className="block text-slate-500">{describeRole(data)}</span>
                </span>
              )}
              <button
                type="button"
                onClick={logout}
                className="rounded-md border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-100"
              >
                Đăng xuất
              </button>
            </div>
          </div>
        </header>
        <main id="noi-dung" tabIndex={-1} className="mx-auto max-w-6xl space-y-6 px-4 py-6">
          <Outlet />
        </main>
        {data && data.user.role !== 'admin' && <ChatDock />}
      </div>
    </AssistantProvider>
  )
}
