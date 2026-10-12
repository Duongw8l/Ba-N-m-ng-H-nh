import { PageTitle, Panel } from '../components/Panel'

// Câu hỏi gợi ý theo DESIGN mục 8.
const SUGGESTIONS = [
  'Lớp 10A1 em nào đã nghỉ từ 30 buổi?',
  'Vì sao em An bị cảnh báo?',
  'Học sinh có một môn dưới 3,5 có được lên lớp không?',
  'So sánh kết quả học kỳ I của các lớp khối 11.',
]

// Khung Trợ lý AI. Chưa nối API: ô nhập bị khoá cho tới Giai đoạn 8 (LLM gọi hàm Analytics, mọi con
// số lấy từ code tính, mỗi câu trả lời có mục Nguồn và nút đánh giá đúng / sai).
export default function AssistantPage() {
  return (
    <>
      <PageTitle title="Trợ lý AI" subtitle="Hỏi số liệu và quy định bằng tiếng Việt" />
      <p
        role="status"
        className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
      >
        Trợ lý AI sẽ được nối ở Giai đoạn 8. Màn hình này mới là khung giao diện.
      </p>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Panel id="khung-chat" title="Trò chuyện">
            <div className="flex min-h-48 flex-col justify-end gap-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-500">
              <p>Chưa có cuộc trò chuyện nào.</p>
            </div>
            <form className="mt-3 flex gap-2" onSubmit={(event) => event.preventDefault()}>
              <label className="sr-only" htmlFor="cau-hoi">
                Câu hỏi
              </label>
              <textarea
                id="cau-hoi"
                disabled
                rows={2}
                placeholder="Nhập câu hỏi…"
                className="flex-1 rounded-md border border-slate-300 px-3 py-2 disabled:bg-slate-100"
              />
              <button
                type="submit"
                disabled
                className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white opacity-60"
              >
                Gửi
              </button>
            </form>
          </Panel>
        </div>
        <Panel id="goi-y" title="Câu hỏi gợi ý">
          <ul className="space-y-2 text-sm">
            {SUGGESTIONS.map((question) => (
              <li key={question} className="rounded-lg border border-slate-200 p-3">
                {question}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </>
  )
}
