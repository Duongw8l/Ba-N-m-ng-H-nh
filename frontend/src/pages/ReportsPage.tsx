import { PageTitle, Panel } from '../components/Panel'

const KINDS = [
  { title: 'Nhận xét học bạ', text: 'Nhận xét từng học sinh cuối học kỳ, giáo viên sửa rồi duyệt.' },
  { title: 'Phiếu liên lạc', text: 'Phiếu gửi phụ huynh, xuất PDF sau khi giáo viên duyệt.' },
  { title: 'Báo cáo lớp / khối', text: 'Báo cáo tổng hợp số liệu của lớp hoặc khối.' },
]

// Khung Nhận xét & báo cáo. Chưa nối API: Giai đoạn 9 sinh bản nháp bằng LLM (luôn ở trạng thái
// nháp cho tới khi giáo viên bấm Duyệt) và xuất PDF.
export default function ReportsPage() {
  return (
    <>
      <PageTitle title="Nhận xét & báo cáo" subtitle="Bản nháp do AI tạo, giáo viên sửa và duyệt" />
      <p
        role="status"
        className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900"
      >
        Chức năng sinh nhận xét và báo cáo sẽ được nối ở Giai đoạn 9. Màn hình này mới là khung giao
        diện.
      </p>
      <div className="grid gap-6 lg:grid-cols-3">
        {KINDS.map((kind, index) => (
          <Panel key={kind.title} id={`loai-${index}`} title={kind.title} description={kind.text}>
            <p className="mb-3 inline-block rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700">
              Bản nháp do AI tạo
            </p>
            <div className="flex gap-2">
              <button
                type="button"
                disabled
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium opacity-60"
              >
                Tạo bản nháp
              </button>
              <button
                type="button"
                disabled
                className="rounded-md border border-slate-300 px-3 py-1.5 text-sm font-medium opacity-60"
              >
                Duyệt
              </button>
            </div>
          </Panel>
        ))}
      </div>
    </>
  )
}
