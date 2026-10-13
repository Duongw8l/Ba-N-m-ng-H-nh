import type { KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { Icon } from '../Icon'
import { ChatPanel } from './ChatPanel'
import { useAssistantChat } from './context'

// Khung chat nổi, mở được từ mọi màn hình (DESIGN mục 8). Trang Trợ lý AI đã có khung chat riêng
// nên ẩn ở đó; cuộc trò chuyện dùng chung nên chuyển trang không mất. Màn hình hẹp: khung chiếm gần
// hết chiều rộng.
export function ChatDock() {
  const { open, setOpen } = useAssistantChat()
  const { pathname } = useLocation()
  if (pathname === '/assistant') return null

  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === 'Escape') setOpen(false)
  }

  return (
    <>
      {open && (
        <div
          role="dialog"
          aria-label="Trợ lý AI"
          onKeyDown={onKeyDown}
          className="fixed right-3 bottom-20 z-40 flex h-[34rem] max-h-[calc(100dvh-6.5rem)] w-[26rem] max-w-[calc(100vw-1.5rem)] flex-col overflow-hidden rounded-3xl border border-slate-200 bg-surface shadow-pop sm:right-5"
        >
          <div className="flex items-center justify-between bg-linear-to-r from-brand-800 to-brand-600 px-4 py-3 text-white">
            <h2 className="flex items-center gap-2 text-base font-semibold">
              <Icon name="sparkles" className="h-5 w-5" />
              Trợ lý AI
            </h2>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Đóng khung chat"
              className="rounded-lg p-1.5 text-white/90 hover:bg-white/15"
            >
              <Icon name="x" className="h-5 w-5" />
            </button>
          </div>
          <div className="flex min-h-0 flex-1 flex-col p-4">
            <ChatPanel variant="dock" />
          </div>
        </div>
      )}
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="fixed right-3 bottom-4 z-40 inline-flex items-center gap-2 rounded-full bg-linear-to-br from-brand-700 to-brand-800 px-5 py-3 font-semibold text-white shadow-pop transition-transform hover:scale-[1.03] sm:right-5"
      >
        <Icon name={open ? 'x' : 'message-circle'} className="h-5 w-5" />
        {open ? 'Đóng trợ lý' : 'Hỏi Trợ lý AI'}
      </button>
    </>
  )
}
