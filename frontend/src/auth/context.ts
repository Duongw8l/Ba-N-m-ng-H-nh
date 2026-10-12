import { createContext, useContext } from 'react'

export interface AuthContextValue {
  token: string | null
  login: (email: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue | null>(null)

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext)
  if (value === null) throw new Error('useAuth phải được dùng bên trong AuthProvider')
  return value
}
