import { useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { login as loginRequest } from '../api/auth'
import { setUnauthorizedHandler } from '../api/client'
import { AuthContext } from './context'
import { clearToken, getToken, setToken } from './tokenStore'

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()
  const [token, setTokenState] = useState<string | null>(() => getToken())

  const logout = useCallback(() => {
    clearToken()
    setTokenState(null)
    // Xoá bộ nhớ đệm để người đăng nhập sau không thấy dữ liệu của người trước.
    queryClient.clear()
  }, [queryClient])

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginRequest(email, password)
    setToken(result.access_token)
    setTokenState(result.access_token)
  }, [])

  // Token hết hạn hoặc bị từ chối giữa chừng thì đăng xuất, RequireAuth sẽ đưa về trang đăng nhập.
  useEffect(() => {
    setUnauthorizedHandler(logout)
    return () => setUnauthorizedHandler(null)
  }, [logout])

  const value = useMemo(() => ({ token, login, logout }), [token, login, logout])
  return <AuthContext value={value}>{children}</AuthContext>
}
