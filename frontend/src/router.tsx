import { createBrowserRouter } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import { AppLayout } from './components/AppLayout'
import { PageFallback } from './components/PageFallback'
import AssistantPage from './pages/AssistantPage'
import HomePage from './pages/HomePage'
import ImportPage from './pages/ImportPage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'

// Các trang có biểu đồ nạp theo yêu cầu để thư viện Recharts (phần nặng nhất của gói) không làm chậm
// trang đăng nhập và trang chủ.
export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  // Mọi trang cần đăng nhập đặt làm con của RequireAuth, trong khung AppLayout (điều hướng chung).
  {
    element: <RequireAuth />,
    HydrateFallback: PageFallback,
    children: [
      {
        element: <AppLayout />,
        children: [
          { path: '/', element: <HomePage /> },
          {
            path: '/classes/:classId',
            lazy: async () => ({ Component: (await import('./pages/ClassDashboardPage')).default }),
          },
          {
            path: '/classes/:classId/subjects/:subjectId',
            lazy: async () => ({ Component: (await import('./pages/SubjectScoresPage')).default }),
          },
          {
            path: '/classes/:classId/students/:studentId',
            lazy: async () => ({ Component: (await import('./pages/StudentProfilePage')).default }),
          },
          { path: '/classes/:classId/import', element: <ImportPage /> },
          {
            path: '/grades/:level',
            lazy: async () => ({ Component: (await import('./pages/GradeOverviewPage')).default }),
          },
          { path: '/assistant', element: <AssistantPage /> },
          {
            path: '/reports',
            lazy: async () => ({ Component: (await import('./pages/ReportsPage')).default }),
          },
          {
            path: '/account/password',
            lazy: async () => ({ Component: (await import('./pages/ChangePasswordPage')).default }),
          },
          // Chỉ Admin (trang tự kiểm vai trò, back-end kiểm lại ở mọi yêu cầu).
          {
            path: '/admin/regulations',
            lazy: async () => ({ Component: (await import('./pages/RegulationsPage')).default }),
          },
          {
            path: '/admin/users',
            lazy: async () => ({ Component: (await import('./pages/AdminUsersPage')).default }),
          },
          {
            path: '/admin/school',
            lazy: async () => ({ Component: (await import('./pages/AdminSchoolPage')).default }),
          },
          {
            path: '/admin/classes/:classId',
            lazy: async () => ({ Component: (await import('./pages/AdminClassPage')).default }),
          },
        ],
      },
    ],
  },
  { path: '*', element: <NotFoundPage /> },
])
