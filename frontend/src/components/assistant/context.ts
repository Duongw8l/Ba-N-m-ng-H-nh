import { createContext, useContext } from 'react'
import type { AssistantFeedback, ChatReply } from '../../api/assistant'

export type ChatMessage =
  | { id: number; role: 'user'; text: string }
  | { id: number; role: 'assistant'; reply: ChatReply; feedback: AssistantFeedback | null }
  | { id: number; role: 'error'; text: string }

// Tin nhắn mới chưa có id (Provider cấp id khi thêm vào danh sách).
type WithoutId<T> = T extends { id: number } ? Omit<T, 'id'> : never
export type NewChatMessage = WithoutId<ChatMessage>

export interface AssistantChat {
  messages: ChatMessage[]
  pending: boolean
  ask: (question: string) => void
  rate: (messageId: number, value: AssistantFeedback) => void
  clear: () => void
  open: boolean
  setOpen: (open: boolean) => void
}

export const AssistantContext = createContext<AssistantChat | null>(null)

export function useAssistantChat(): AssistantChat {
  const value = useContext(AssistantContext)
  if (value === null) throw new Error('useAssistantChat phải nằm trong AssistantProvider')
  return value
}
