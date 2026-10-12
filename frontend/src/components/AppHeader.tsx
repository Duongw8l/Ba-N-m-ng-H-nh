interface AppHeaderProps {
  fullName: string
  roleLabel: string
  onLogout: () => void
}

export function AppHeader({ fullName, roleLabel, onLogout }: AppHeaderProps) {
  return (
    <header className="border-b border-slate-200 bg-white">
      <div className="mx-auto flex max-w-3xl items-center justify-between gap-4 px-4 py-3">
        <span className="font-semibold">Trợ lý AI quản lý lớp học</span>
        <div className="flex items-center gap-4 text-sm">
          <span className="text-right">
            <span className="block font-medium">{fullName}</span>
            <span className="block text-slate-500">{roleLabel}</span>
          </span>
          <button
            type="button"
            onClick={onLogout}
            className="rounded-md border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-100"
          >
            Đăng xuất
          </button>
        </div>
      </div>
    </header>
  )
}
