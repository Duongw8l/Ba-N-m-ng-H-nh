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
  ok: 'bg-emerald-500 shadow-[0_0_0_3px_rgb(16_185_129/0.2)]',
  error: 'bg-red-500 shadow-[0_0_0_3px_rgb(239_68_68/0.2)]',
  unknown: 'bg-amber-500 shadow-[0_0_0_3px_rgb(245_158_11/0.2)]',
}

export function StatusRow({ label, state }: StatusRowProps) {
  return (
    <li className="flex items-center justify-between py-2.5">
      <span className="text-slate-600">{label}</span>
      <span className="flex items-center gap-2 font-medium" data-state={state}>
        <span aria-hidden="true" className={`h-2 w-2 rounded-full ${DOT_CLASS[state]}`} />
        {STATE_TEXT[state]}
      </span>
    </li>
  )
}
