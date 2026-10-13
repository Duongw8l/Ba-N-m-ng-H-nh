import { apiPatch, apiPost } from './client'
import type { Period } from './analytics'

// Khớp schema của back-end (backend/app/assistant/schemas.py).
export type AssistantFeedback = 'correct' | 'incorrect'

export interface DataSource {
  type: 'data'
  tool: string
  description: string
}

export interface RegulationSource {
  type: 'regulation'
  document: string
  article: string | null
  clause: string | null
  similarity: number
}

export type AssistantSource = DataSource | RegulationSource

export interface ChatReply {
  log_id: number
  answer: string
  sources: AssistantSource[]
  blocked: boolean // có hàm bị từ chối vì không đủ quyền
  ungrounded_numbers: string[] // số trong câu trả lời chưa đối chiếu được với kết quả hàm
  clarification: boolean // trợ lý hỏi lại (ví dụ trùng tên), chưa gọi mô hình
}

// Màn hình đang mở: back-end kiểm lại quyền, giao diện chỉ báo cho trợ lý biết đang xem gì.
export interface AssistantScreen {
  classId: number | null
  subjectId: number | null
  semester: Period
}

export const MAX_QUESTION_LENGTH = 1000

export function askAssistant(question: string, screen: AssistantScreen): Promise<ChatReply> {
  return apiPost<ChatReply>('/assistant/chat', {
    question,
    class_id: screen.classId,
    subject_id: screen.classId === null ? null : screen.subjectId,
    semester: screen.semester,
  })
}

export function sendFeedback(logId: number, value: AssistantFeedback): Promise<unknown> {
  return apiPatch(`/assistant/logs/${logId}/feedback`, { value })
}
