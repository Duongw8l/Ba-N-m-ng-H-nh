import { Icon } from '../Icon'
import type { IconName } from '../Icon'
import { useTheme } from '../../theme/context'
import type { ThemePreference } from '../../theme/context'

const OPTIONS: { value: ThemePreference; label: string; icon: IconName }[] = [
  { value: 'light', label: 'Giao diện sáng', icon: 'sun' },
  { value: 'system', label: 'Theo hệ thống', icon: 'monitor' },
  { value: 'dark', label: 'Giao diện tối', icon: 'moon' },
]

// Ba nút chọn chế độ sáng, theo hệ thống, tối; lựa chọn được nhớ (ThemeProvider).
export function ThemeToggle() {
  const { preference, setPreference } = useTheme()
  return (
    <div
      role="group"
      aria-label="Chế độ giao diện"
      className="flex items-center rounded-xl border border-slate-200 bg-slate-50 p-0.5"
    >
      {OPTIONS.map((option) => {
        const active = preference === option.value
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            aria-label={option.label}
            title={option.label}
            onClick={() => setPreference(option.value)}
            className={`rounded-lg p-1.5 transition-colors ${
              active
                ? 'bg-surface text-brand-700 shadow-sm dark:text-brand-300'
                : 'text-slate-500 hover:text-slate-800'
            }`}
          >
            <Icon name={option.icon} className="h-4 w-4" />
          </button>
        )
      })}
    </div>
  )
}
