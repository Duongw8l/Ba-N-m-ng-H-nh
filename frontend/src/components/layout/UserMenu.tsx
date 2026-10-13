import { useEffect, useRef, useState } from 'react'
import type { AuthUser } from '../../api/auth'
import { initialsOf } from '../../lib/initials'
import { Icon } from '../Icon'

interface UserMenuProps {
  user: AuthUser
  roleLabel: string
  onLogout: () => void
}

// Thẻ người dùng ở góc phải thanh trên: ảnh đại diện chữ cái, họ tên, vai trò; mở menu có Đăng xuất.
export function UserMenu({ user, roleLabel, onLogout }: UserMenuProps) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (root.current && !root.current.contains(event.target as Node)) setOpen(false)
    }
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('pointerdown', onPointer)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2.5 rounded-xl p-1 pr-2 transition-colors hover:bg-slate-100"
      >
        <span
          aria-hidden="true"
          className="flex h-9 w-9 items-center justify-center rounded-full bg-linear-to-br from-brand-400 to-brand-700 text-sm font-semibold text-white"
        >
          {initialsOf(user.full_name)}
        </span>
        <span className="hidden text-left leading-tight sm:block">
          <span className="block text-sm font-semibold">{user.full_name}</span>
          <span className="block text-xs text-slate-500">{roleLabel}</span>
        </span>
        <Icon name="chevron-down" className="hidden h-4 w-4 text-slate-400 sm:block" />
      </button>
      {open && (
        <div
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 rounded-2xl border border-slate-200 bg-surface p-2 shadow-pop"
        >
          <div className="px-3 py-2">
            <p className="text-sm font-semibold">{user.full_name}</p>
            <p className="truncate text-xs text-slate-500">{user.email}</p>
            <span className="badge-info mt-2">{roleLabel}</span>
          </div>
          <div className="my-1 border-t border-slate-100" />
          <button
            type="button"
            role="menuitem"
            onClick={onLogout}
            className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100"
          >
            <Icon name="logout" className="h-4 w-4" />
            Đăng xuất
          </button>
        </div>
      )}
    </div>
  )
}
