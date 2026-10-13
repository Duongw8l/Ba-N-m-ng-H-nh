import { createContext, useContext } from 'react'

// Lựa chọn của người dùng; "system" theo cài đặt của hệ điều hành.
export type ThemePreference = 'light' | 'dark' | 'system'

export const THEME_STORAGE_KEY = 'thda.theme'

export interface ThemeContextValue {
  preference: ThemePreference
  // Chế độ đang áp dụng thật sự (đã phân giải "system").
  resolved: 'light' | 'dark'
  setPreference: (preference: ThemePreference) => void
}

export const ThemeContext = createContext<ThemeContextValue | null>(null)

export function useTheme(): ThemeContextValue {
  const value = useContext(ThemeContext)
  if (value === null) throw new Error('useTheme phải được dùng bên trong ThemeProvider')
  return value
}
