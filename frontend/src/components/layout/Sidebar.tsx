import { NavLink } from 'react-router-dom'
import { Icon } from '../Icon'
import type { IconName } from '../Icon'
import { Logo } from '../Logo'

export interface NavItem {
  to: string
  label: string
  icon: IconName
  end?: boolean
}

export interface NavGroup {
  title: string
  items: NavItem[]
}

interface SidebarProps {
  groups: NavGroup[]
  // Chỉ có nghĩa ở màn hình rộng: thu về cột biểu tượng.
  compact: boolean
  onToggleCompact: () => void
  // Màn hình hẹp: thanh bên là ngăn kéo.
  isDesktop: boolean
  drawerOpen: boolean
  onCloseDrawer: () => void
}

function linkClass({ isActive }: { isActive: boolean }, slim: boolean): string {
  const base =
    'group relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors'
  const state = isActive
    ? 'bg-white/12 text-white shadow-[inset_0_0_0_1px_rgb(255_255_255/0.08)]'
    : 'text-brand-100/80 hover:bg-white/6 hover:text-white'
  return `${base} ${state} ${slim ? 'justify-center px-0' : ''}`
}

// Thanh bên trái: logo, các mục theo nhóm (biểu tượng + nhãn), thu gọn được. Màn hình hẹp thì là ngăn
// kéo trượt từ trái, đóng bằng lớp phủ, nút đóng hoặc Esc (AppLayout xử lý Esc).
export function Sidebar({
  groups,
  compact,
  onToggleCompact,
  isDesktop,
  drawerOpen,
  onCloseDrawer,
}: SidebarProps) {
  const slim = compact && isDesktop
  return (
    <>
      {drawerOpen && !isDesktop && (
        <div
          aria-hidden="true"
          onClick={onCloseDrawer}
          className="fixed inset-0 z-40 bg-slate-950/55 backdrop-blur-[2px] lg:hidden"
        />
      )}
      <aside
        id="thanh-ben"
        // Ngăn kéo đóng thì không cho Tab vào các liên kết đang nằm ngoài màn hình.
        inert={!isDesktop && !drawerOpen}
        className={`fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-sidebar text-brand-100 shadow-pop transition-transform duration-200 lg:sticky lg:top-0 lg:z-20 lg:h-screen lg:translate-x-0 lg:shadow-none lg:transition-[width] ${
          drawerOpen ? 'translate-x-0' : '-translate-x-full'
        } ${slim ? 'lg:w-[4.75rem]' : 'lg:w-64'}`}
      >
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-0 bg-[radial-gradient(18rem_14rem_at_0%_0%,rgb(45_212_191/0.16),transparent_70%)]"
        />
        <div
          className={`relative flex h-16 shrink-0 items-center border-b border-white/8 ${
            slim ? 'justify-center' : 'justify-between px-5'
          }`}
        >
          <Logo compact={slim} className="text-white" />
          {!isDesktop && (
            <button
              type="button"
              onClick={onCloseDrawer}
              aria-label="Đóng menu"
              className="rounded-lg p-2 text-brand-100 hover:bg-white/10"
            >
              <Icon name="x" />
            </button>
          )}
        </div>

        <nav aria-label="Điều hướng chính" className="relative flex-1 space-y-5 overflow-y-auto p-3">
          {groups.map((group) => (
            <div key={group.title}>
              {slim ? (
                <div aria-hidden="true" className="mx-3 mb-2 border-t border-white/10" />
              ) : (
                <p className="mb-1.5 px-3 text-[0.68rem] font-semibold tracking-wider text-brand-300/80 uppercase">
                  {group.title}
                </p>
              )}
              <ul className="space-y-1">
                {group.items.map((item) => (
                  <li key={item.to}>
                    <NavLink
                      to={item.to}
                      end={item.end}
                      onClick={onCloseDrawer}
                      title={slim ? item.label : undefined}
                      aria-label={slim ? item.label : undefined}
                      className={(state) => linkClass(state, slim)}
                    >
                      {({ isActive }) => (
                        <>
                          {isActive && (
                            <span
                              aria-hidden="true"
                              className="absolute top-2 bottom-2 left-0 w-1 rounded-r-full bg-brand-300"
                            />
                          )}
                          <Icon name={item.icon} className="h-5 w-5" />
                          {!slim && <span className="truncate">{item.label}</span>}
                        </>
                      )}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>

        {isDesktop && (
          <div className="relative border-t border-white/8 p-3">
            <button
              type="button"
              onClick={onToggleCompact}
              aria-pressed={compact}
              aria-label={compact ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
              title={compact ? 'Mở rộng thanh bên' : 'Thu gọn thanh bên'}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium text-brand-100/70 transition-colors hover:bg-white/6 hover:text-white ${
                slim ? 'justify-center px-0' : ''
              }`}
            >
              <Icon name={slim ? 'chevrons-right' : 'chevrons-left'} />
              {!slim && <span>Thu gọn</span>}
            </button>
          </div>
        )}
      </aside>
    </>
  )
}
