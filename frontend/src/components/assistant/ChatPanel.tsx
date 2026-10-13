import { useEffect, useRef, useState } from 'react'
import type { FormEvent, KeyboardEvent } from 'react'
import { MAX_QUESTION_LENGTH } from '../../api/assistant'
import type { AssistantFeedback, AssistantSource } from '../../api/assistant'
import { useAssignments } from '../../hooks/useAssignments'
import { useAssistantScreen } from '../../hooks/useAssistantScreen'
import { formatSimilarity } from '../../lib/format'
import { PERIOD_LABELS } from '../../lib/labels'
import { useAssistantChat } from './context'
import type { ChatMessage } from './context'

// Câu hỏi gợi ý theo DESIGN mục 8.
const SUGGESTIONS = [
  'Lớp 10A1 em nào đã nghỉ từ 30 buổi?',
  'Vì sao em An bị cảnh báo?',
  'Học sinh có một môn dưới 3,5 có được lên lớp không?',
  'So sánh kết quả học kỳ I của các lớp khối 11.',
]

function describeSource(source: AssistantSource): string {
  if (source.type === 'data') return source.description
  const place = [source.article, source.clause].filter(Boolean).join(' · ')
  return `${source.document}${place ? ` · ${place}` : ''} (tương đồng ${formatSimilarity(source.similarity)})`
}

// Mục "Nguồn": hàm Analytics đã gọi và điều khoản đã trích, để người dùng tự kiểm tra câu trả lời.
function SourceList({ sources }: { sources: AssistantSource[] }) {
  if (sources.length === 0) {
    return <p className="mt-2 text-xs text-slate-500">Nguồn: không có (không gọi hàm nào).</p>
  }
  return (
    <details className="mt-2 text-xs text-slate-600">
      <summary className="cursor-pointer font-medium">Nguồn ({sources.length})</summary>
      <ul className="mt-1 list-disc space-y-0.5 pl-5">
        {sources.map((source, index) => (
          <li key={`${index}-${describeSource(source)}`}>{describeSource(source)}</li>
        ))}
      </ul>
    </details>
  )
}

function FeedbackButtons({
  value,
  onRate,
}: {
  value: AssistantFeedback | null
  onRate: (value: AssistantFeedback) => void
}) {
  const base = 'rounded-lg border px-2 py-1 text-xs font-medium transition-colors'
  function pick(option: AssistantFeedback, active: string) {
    return `${base} ${value === option ? active : 'border-slate-300 bg-surface text-slate-700 hover:bg-slate-100'}`
  }
  return (
    <div className="mt-2 flex items-center gap-2" role="group" aria-label="Đánh giá câu trả lời">
      <span className="text-xs text-slate-500">Câu trả lời này:</span>
      <button
        type="button"
        aria-pressed={value === 'correct'}
        onClick={() => onRate('correct')}
        className={pick('correct', 'border-green-600 bg-green-50 text-green-800')}
      >
        Đúng
      </button>
      <button
        type="button"
        aria-pressed={value === 'incorrect'}
        onClick={() => onRate('incorrect')}
        className={pick('incorrect', 'border-red-600 bg-red-50 text-red-800')}
      >
        Sai
      </button>
    </div>
  )
}

function Message({
  message,
  onRate,
}: {
  message: ChatMessage
  onRate: (id: number, value: AssistantFeedback) => void
}) {
  if (message.role === 'user') {
    return (
      <li className="flex justify-end">
        <p className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-sm bg-brand-700 px-3 py-2 text-sm text-white">
          {message.text}
        </p>
      </li>
    )
  }
  if (message.role === 'error') {
    return (
      <li>
        <p role="alert" className="rounded-xl bg-red-50 px-3 py-2 text-sm text-red-800">
          {message.text}
        </p>
      </li>
    )
  }
  const { reply } = message
  return (
    <li className="flex">
      <div className="max-w-[92%] rounded-2xl rounded-bl-sm border border-slate-200 bg-surface px-3 py-2">
        <p className="whitespace-pre-wrap text-sm text-slate-900">{reply.answer}</p>
        {reply.blocked && (
          <p className="mt-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-900 ring-1 ring-amber-200">
            Một phần câu hỏi nằm ngoài quyền xem của bạn nên trợ lý không lấy dữ liệu đó.
          </p>
        )}
        {reply.ungrounded_numbers.length > 0 && (
          <p className="mt-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-900 ring-1 ring-amber-200">
            Chưa đối chiếu được với dữ liệu hệ thống các số: {reply.ungrounded_numbers.join(', ')}.
            Hãy kiểm tra lại trước khi dùng.
          </p>
        )}
        {!reply.clarification && <SourceList sources={reply.sources} />}
        {!reply.clarification && (
          <FeedbackButtons value={message.feedback} onRate={(value) => onRate(message.id, value)} />
        )}
      </div>
    </li>
  )
}

// Khung chat: lớp, môn và kỳ lấy từ màn hình đang mở; mọi câu trả lời kèm nguồn và nút đánh giá.
// `dock`: khung nổi (cao theo khung chứa); `page`: trang Trợ lý AI.
export function ChatPanel({ variant }: { variant: 'dock' | 'page' }) {
  const chat = useAssistantChat()
  const screen = useAssistantScreen()
  const assignments = useAssignments()
  const [draft, setDraft] = useState('')
  const endRef = useRef<HTMLLIElement>(null)

  useEffect(() => {
    endRef.current?.scrollIntoView?.({ block: 'end' })
  }, [chat.messages.length, chat.pending])

  const known = assignments.data
  const teachingItem = known?.teaching.find(
    (item) => item.class_id === screen.classId && item.subject_id === screen.subjectId,
  )
  const className =
    known?.homeroom_classes.find((item) => item.id === screen.classId)?.name ??
    known?.teaching.find((item) => item.class_id === screen.classId)?.class_name
  const where =
    screen.classId === null
      ? 'Không chọn lớp nào'
      : `Lớp ${className ?? `#${screen.classId}`}${teachingItem ? `, môn ${teachingItem.subject_name}` : ''}`

  function submit(event?: FormEvent) {
    event?.preventDefault()
    if (draft.trim() === '' || chat.pending) return
    chat.ask(draft)
    setDraft('')
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault()
      submit()
    }
  }

  const listHeight = variant === 'dock' ? 'min-h-0 flex-1' : 'h-[28rem]'
  return (
    <div className={variant === 'dock' ? 'flex min-h-0 flex-1 flex-col' : 'flex flex-col'}>
      <p className="mb-2 text-xs text-slate-500">
        Đang hỏi trong: {where} · {PERIOD_LABELS[screen.semester]}
      </p>
      <ul
        role="log"
        aria-label="Cuộc trò chuyện với Trợ lý AI"
        aria-live="polite"
        className={`${listHeight} space-y-3 overflow-y-auto rounded-xl bg-slate-50 p-3`}
      >
        {chat.messages.length === 0 && (
          <li className="text-sm text-slate-600">
            Hỏi bằng tiếng Việt về điểm, chuyên cần, cảnh báo hoặc quy định. Số liệu do hệ thống
            tính; mỗi câu trả lời đều có mục Nguồn.
          </li>
        )}
        {chat.messages.map((message) => (
          <Message key={message.id} message={message} onRate={chat.rate} />
        ))}
        {chat.pending && (
          <li className="text-sm text-slate-500" aria-live="polite">
            Trợ lý đang tra dữ liệu…
          </li>
        )}
        <li ref={endRef} aria-hidden="true" />
      </ul>

      {chat.messages.length === 0 && (
        <div className="mt-3">
          <p className="mb-1 text-xs font-medium text-slate-500">Câu hỏi gợi ý</p>
          <ul className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((question) => (
              <li key={question}>
                <button
                  type="button"
                  disabled={chat.pending}
                  onClick={() => chat.ask(question)}
                  className="rounded-full border border-slate-300 bg-surface px-3 py-1 text-left text-xs text-slate-700 hover:bg-slate-100 disabled:opacity-60"
                >
                  {question}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={submit} className="mt-3 flex items-end gap-2">
        <label className="sr-only" htmlFor={`cau-hoi-${variant}`}>
          Câu hỏi cho Trợ lý AI
        </label>
        <textarea
          id={`cau-hoi-${variant}`}
          value={draft}
          rows={2}
          maxLength={MAX_QUESTION_LENGTH}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Nhập câu hỏi… (Enter để gửi)"
          className="input min-w-0 flex-1 resize-none text-sm"
        />
        <button
          type="submit"
          disabled={draft.trim() === '' || chat.pending}
          className="btn-primary"
        >
          Gửi
        </button>
      </form>
      <div className="mt-2 flex items-start justify-between gap-3">
        <p className="text-xs text-slate-500">
          Họ tên học sinh được thay bằng mã tạm trước khi gửi cho mô hình ngôn ngữ. Trợ lý có thể
          sai: hãy kiểm tra số liệu trước khi dùng.
        </p>
        {chat.messages.length > 0 && (
          <button
            type="button"
            onClick={chat.clear}
            className="shrink-0 text-xs font-medium link"
          >
            Xoá cuộc trò chuyện
          </button>
        )}
      </div>
    </div>
  )
}
