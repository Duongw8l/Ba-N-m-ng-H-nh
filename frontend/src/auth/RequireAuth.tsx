import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from './context'

// Route cha của mọi trang cần đăng nhập: chưa có token thì chuyển về /login và nhớ trang đang mở.
export function RequireAuth() {
  const { token } = useAuth()
  const location = useLocation()

  if (token === null) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  return <Outlet />
}
