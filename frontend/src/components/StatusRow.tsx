export type StatusState = 'loading' | 'ok' | 'error' | 'unknown'

interface StatusRowProps {
  label: string
  state: StatusState
}

const STATE_TEXT: Record<StatusState, string> = {
  loading: 'đang kiểm tra…',
  ok: 'ok',
  error: 'lỗi',
  unknown: 'không xác định',
}

const DOT_CLASS: Record<StatusState, string> = {
  loading: 'bg-slate-400 animate-pulse',
  ok: 'bg-emerald-500',
  error: 'bg-red-500',
  unknown: 'bg-amber-500',
}

export function StatusRow({ label, state }: StatusRowProps) {
  return (
    <li className="flex items-center justify-between py-3">
      <span className="text-slate-600">{label}</span>
      <span className="flex items-center gap-2 font-medium" data-state={state}>
        <span aria-hidden="true" className={`h-2.5 w-2.5 rounded-full ${DOT_CLASS[state]}`} />
        {STATE_TEXT[state]}
      </span>
    </li>
  )
}
