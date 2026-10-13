import { ChatPanel } from '../components/assistant/ChatPanel'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { useAssignments } from '../hooks/useAssignments'

// Trang Trợ lý AI: cùng khung chat với nút nổi ở mọi màn hình (cuộc trò chuyện dùng chung). Trợ lý
// gọi các hàm Analytics có kiểm quyền; mọi con số trong câu trả lời do hệ thống tính (nguyên tắc 1).
export default function AssistantPage() {
  const assignments = useAssignments()
  return (
    <>
      <PageTitle title="Trợ lý AI" subtitle="Hỏi số liệu và quy định bằng tiếng Việt" />
      <QueryState query={assignments}>
        {(data) =>
          data.user.role === 'admin' ? (
            <p className="card p-6 text-slate-600">
              Quản trị viên không xem dữ liệu học sinh nên không dùng Trợ lý AI. Quản lý văn bản
              quy định ở mục Văn bản quy định.
            </p>
          ) : (
            <Panel id="khung-chat" title="Trò chuyện">
              <ChatPanel variant="page" />
            </Panel>
          )
        }
      </QueryState>
    </>
  )
}
