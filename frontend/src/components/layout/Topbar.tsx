import { Link } from 'react-router-dom'
import type { AuthUser } from '../../api/auth'
import { Icon } from '../Icon'
import { ThemeToggle } from './ThemeToggle'
import { UserMenu } from './UserMenu'
import type { Crumb } from './useBreadcrumbs'

interface TopbarProps {
  crumbs: Crumb[]
  user: AuthUser | undefined
  roleLabel: string
  onOpenMenu: () => void
  onLogout: () => void
}

// Thanh trên: nút mở menu (màn hình hẹp), đường dẫn, chế độ giao diện, người dùng.
export function Topbar({ crumbs, user, roleLabel, onOpenMenu, onLogout }: TopbarProps) {
  return (
    <header className="sticky top-0 z-30 border-b border-slate-200/80 bg-surface/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-7xl items-center gap-3 px-4 sm:px-6 lg:px-8">
        <button
          type="button"
          onClick={onOpenMenu}
          aria-label="Mở menu"
          aria-controls="thanh-ben"
          className="-ml-1.5 rounded-xl p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
        >
          <Icon name="menu" className="h-6 w-6" />
        </button>

        <nav aria-label="Vị trí hiện tại" className="min-w-0 flex-1">
          <ol className="flex items-center gap-1.5 text-sm text-slate-500">
            {crumbs.map((crumb, index) => {
              const last = index === crumbs.length - 1
              return (
                <li key={`${index}-${crumb.label}`} className="flex min-w-0 items-center gap-1.5">
                  {index > 0 && <Icon name="chevron-right" className="h-3.5 w-3.5 text-slate-400" />}
                  {crumb.to && !last ? (
                    <Link to={crumb.to} className="truncate hover:text-slate-800 hover:underline">
                      {crumb.label}
                    </Link>
                  ) : (
                    <span
                      aria-current={last ? 'page' : undefined}
                      className={`truncate ${last ? 'font-semibold text-slate-900' : ''}`}
                    >
                      {crumb.label}
                    </span>
                  )}
                </li>
              )
            })}
          </ol>
        </nav>

        <ThemeToggle />
        {user && <UserMenu user={user} roleLabel={roleLabel} onLogout={onLogout} />}
      </div>
    </header>
  )
}
