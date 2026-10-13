import { useEffect, useState } from 'react'
import { Outlet } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { describeRole } from '../auth/roles'
import { useAssignments } from '../hooks/useAssignments'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { AssistantProvider } from './assistant/AssistantProvider'
import { ChatDock } from './assistant/ChatDock'
import { Sidebar } from './layout/Sidebar'
import type { NavGroup } from './layout/Sidebar'
import { Topbar } from './layout/Topbar'
import { useBreadcrumbs } from './layout/useBreadcrumbs'

const SIDEBAR_KEY = 'thda.sidebar'

function readCompact(): boolean {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === 'compact'
  } catch {
    return false
  }
}

// Khung chung của mọi trang cần đăng nhập: thanh bên trái (theo vai trò, thu gọn được; màn hình hẹp
// là ngăn kéo), thanh trên (đường dẫn, chế độ giao diện, người dùng), nội dung và khung chat nổi.
export function AppLayout() {
  const { logout } = useAuth()
  const assignments = useAssignments()
  const data = assignments.data
  const isDesktop = useMediaQuery('(min-width: 1024px)')
  const [compact, setCompact] = useState(readCompact)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const crumbs = useBreadcrumbs(data)
  const role = data?.user.role

  const groups: NavGroup[] = [
    { title: 'Tổng quan', items: [{ to: '/', label: 'Trang chủ', icon: 'home', end: true }] },
  ]
  if (data && data.homeroom_classes.length > 0) {
    groups.push({
      title: 'Lớp của tôi',
      items: data.homeroom_classes.map((item) => ({
        to: `/classes/${item.id}`,
        label: `Lớp ${item.name}`,
        icon: 'users' as const,
      })),
    })
  }
  if (data && data.grades.length > 0) {
    groups.push({
      title: 'Khối',
      items: data.grades.map((grade) => ({
        to: `/grades/${grade}`,
        label: `Khối ${grade}`,
        icon: 'layers' as const,
      })),
    })
  }
  groups.push({
    title: 'Công cụ',
    items: [
      ...(role === 'admin'
        ? []
        : [{ to: '/assistant', label: 'Trợ lý AI', icon: 'sparkles' as const }]),
      { to: '/reports', label: 'Nhận xét & báo cáo', icon: 'file' as const },
    ],
  })
  if (role === 'admin') {
    groups.push({
      title: 'Quản trị',
      items: [{ to: '/admin/regulations', label: 'Văn bản quy định', icon: 'book' }],
    })
  }

  function toggleCompact() {
    setCompact((current) => {
      const next = !current
      try {
        localStorage.setItem(SIDEBAR_KEY, next ? 'compact' : 'expanded')
      } catch {
        // Không lưu được thì chỉ áp dụng cho phiên này.
      }
      return next
    })
  }

  // Ngăn kéo (màn hình hẹp): Esc đóng, và khoá cuộn nền khi đang mở.
  const drawerShown = drawerOpen && !isDesktop
  useEffect(() => {
    if (!drawerShown) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setDrawerOpen(false)
    }
    document.addEventListener('keydown', onKey)
    const previous = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = previous
    }
  }, [drawerShown])

  return (
    <AssistantProvider>
      <div className="min-h-screen lg:flex">
        <a
          href="#noi-dung"
          className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-[60] focus:rounded-lg focus:bg-surface focus:px-3 focus:py-2 focus:shadow-pop"
        >
          Bỏ qua điều hướng
        </a>
        <Sidebar
          groups={groups}
          compact={compact}
          onToggleCompact={toggleCompact}
          isDesktop={isDesktop}
          drawerOpen={drawerShown}
          onCloseDrawer={() => setDrawerOpen(false)}
        />
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar
            crumbs={crumbs}
            user={data?.user}
            roleLabel={data ? describeRole(data) : ''}
            onOpenMenu={() => setDrawerOpen(true)}
            onLogout={logout}
          />
          <main
            id="noi-dung"
            tabIndex={-1}
            className="mx-auto w-full max-w-7xl flex-1 space-y-6 px-4 py-6 outline-none sm:px-6 lg:px-8"
          >
            <Outlet />
          </main>
        </div>
        {data && role !== 'admin' && <ChatDock />}
      </div>
    </AssistantProvider>
  )
}
