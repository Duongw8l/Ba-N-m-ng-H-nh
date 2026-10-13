import { Link } from 'react-router-dom'
import { PageTitle, Panel } from '../components/Panel'
import { QueryState } from '../components/QueryState'
import { RegulationTable } from '../components/regulations/RegulationTable'
import { SearchBox } from '../components/regulations/SearchBox'
import { UploadForm } from '../components/regulations/UploadForm'
import { useAssignments } from '../hooks/useAssignments'
import { useRegulations } from '../hooks/useRegulations'

function Documents() {
  const regulations = useRegulations()
  return <QueryState query={regulations}>{(data) => <RegulationTable documents={data} />}</QueryState>
}

// Quản lý văn bản quy định cho Trợ lý AI (Thông tư 22, quy chế thi, nội quy...): chỉ Admin. Trợ lý chỉ
// trích dẫn văn bản còn hiệu lực. Back-end kiểm lại quyền ở mọi yêu cầu; trang này chỉ ẩn nội dung.
export default function RegulationsPage() {
  const assignments = useAssignments()

  return (
    <QueryState query={assignments}>
      {(data) =>
        data.user.role !== 'admin' ? (
          <p className="card p-6 text-slate-600">
            Chỉ quản trị viên được quản lý văn bản quy định.
          </p>
        ) : (
          <>
            <PageTitle
              title="Văn bản quy định"
              subtitle="Trợ lý AI chỉ trích dẫn các văn bản còn hiệu lực ở đây."
              actions={
                <Link to="/" className="link text-sm">
                  ← Trang chủ
                </Link>
              }
            />
            <Panel id="danh-sach-van-ban" title="Các văn bản đã tải">
              <Documents />
            </Panel>
            <Panel
              id="tai-van-ban"
              title="Tải văn bản mới"
              description="Mỗi tên chỉ có một bản còn hiệu lực: muốn thay bằng bản mới, hãy đánh dấu bản cũ hết hiệu lực trước."
            >
              <UploadForm />
            </Panel>
            <Panel
              id="thu-tim"
              title="Thử tìm"
              description="Xem những đoạn Trợ lý AI sẽ được đưa cho khi nhận một câu hỏi."
            >
              <SearchBox />
            </Panel>
          </>
        )
      }
    </QueryState>
  )
}
