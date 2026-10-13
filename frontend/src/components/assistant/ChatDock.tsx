import type { KeyboardEvent } from 'react'
import { useLocation } from 'react-router-dom'
import { ChatPanel } from './ChatPanel'
import { useAssistantChat } from './context'

// Khung chat nổi, mở được từ mọi màn hình (DESIGN mục 8). Trang Trợ lý AI đã có khung chat riêng
// nên ẩn ở đó; cuộc trò chuyện dùng chung nên chuyển trang không mất.
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
          className="fixed bottom-20 right-4 z-40 flex h-[34rem] max-h-[calc(100vh-7rem)] w-[26rem] max-w-[calc(100vw-2rem)] flex-col rounded-xl border border-slate-200 bg-white p-4 shadow-xl"
        >
          <div className="mb-2 flex items-center justify-between">
            <h2 className="text-base font-semibold">Trợ lý AI</h2>
            <button
              type="button"
              onClick={() => setOpen(false)}
              aria-label="Đóng khung chat"
              className="rounded-md px-2 py-1 text-slate-600 hover:bg-slate-100"
            >
              ✕
            </button>
          </div>
          <ChatPanel variant="dock" />
        </div>
      )}
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="fixed bottom-4 right-4 z-40 rounded-full bg-blue-700 px-5 py-3 font-medium text-white shadow-lg hover:bg-blue-800"
      >
        {open ? 'Đóng trợ lý' : 'Hỏi Trợ lý AI'}
      </button>
    </>
  )
}
