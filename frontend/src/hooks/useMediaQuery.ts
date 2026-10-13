import { useSyncExternalStore } from 'react'

// Theo dõi một media query (ví dụ '(min-width: 1024px)'), cập nhật khi cửa sổ đổi cỡ.
export function useMediaQuery(query: string): boolean {
  return useSyncExternalStore(
    (notify) => {
      const list = window.matchMedia(query)
      list.addEventListener('change', notify)
      return () => list.removeEventListener('change', notify)
    },
    () => window.matchMedia(query).matches,
    () => false,
  )
}
