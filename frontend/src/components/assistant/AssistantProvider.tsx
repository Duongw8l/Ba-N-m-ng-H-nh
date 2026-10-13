import { useMutation } from '@tanstack/react-query'
import { useCallback, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { askAssistant, sendFeedback } from '../../api/assistant'
import type { AssistantFeedback } from '../../api/assistant'
import { ApiError } from '../../api/client'
import { useAssistantScreen } from '../../hooks/useAssistantScreen'
import { AssistantContext } from './context'
import type { ChatMessage, NewChatMessage } from './context'

function errorText(error: unknown): string {
  // 403, 404, 429, 502, 503: back-end đã trả thông điệp tiếng Việt.
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

// Giữ cuộc trò chuyện khi người dùng chuyển trang (nằm trong AppLayout), dùng chung cho khung chat
// nổi và trang Trợ lý AI. Mỗi câu hỏi độc lập: back-end không nhớ các câu trước (D-089), lịch sử
// chỉ để người dùng xem lại trên màn hình.
export function AssistantProvider({ children }: { children: ReactNode }) {
  const screen = useAssistantScreen()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [open, setOpen] = useState(false)
  const nextId = useRef(1)

  const append = useCallback((message: NewChatMessage) => {
    const id = nextId.current++
    setMessages((current) => [...current, { ...message, id } as ChatMessage])
  }, [])

  const asking = useMutation({
    mutationFn: (question: string) => askAssistant(question, screen),
    onSuccess: (reply) => append({ role: 'assistant', reply, feedback: null }),
    onError: (error) => append({ role: 'error', text: errorText(error) }),
  })

  const { mutate, isPending } = asking
  const ask = useCallback(
    (question: string) => {
      const text = question.trim()
      if (text === '' || isPending) return
      append({ role: 'user', text })
      mutate(text)
    },
    [append, mutate, isPending],
  )

  const rate = useCallback(
    (messageId: number, value: AssistantFeedback) => {
      const target = messages.find((m) => m.id === messageId)
      if (target?.role !== 'assistant') return
      const set = (feedback: AssistantFeedback | null) =>
        setMessages((current) =>
          current.map((m) => (m.id === messageId && m.role === 'assistant' ? { ...m, feedback } : m)),
        )
      set(value)
      // Không ghi được đánh giá thì bỏ chọn để người dùng thấy và thử lại.
      sendFeedback(target.reply.log_id, value).catch(() => set(null))
    },
    [messages],
  )

  const clear = useCallback(() => setMessages([]), [])

  const value = useMemo(
    () => ({ messages, pending: isPending, ask, rate, clear, open, setOpen }),
    [messages, isPending, ask, rate, clear, open],
  )
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>
}
