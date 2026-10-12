import { createBrowserRouter } from 'react-router-dom'
import { RequireAuth } from './auth/RequireAuth'
import HomePage from './pages/HomePage'
import LoginPage from './pages/LoginPage'
import NotFoundPage from './pages/NotFoundPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  // Mọi trang cần đăng nhập đặt làm con của RequireAuth.
  { element: <RequireAuth />, children: [{ path: '/', element: <HomePage /> }] },
  { path: '*', element: <NotFoundPage /> },
])
