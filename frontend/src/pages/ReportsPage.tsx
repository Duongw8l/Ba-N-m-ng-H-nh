import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { PageTitle } from '../components/Panel'

const KINDS: { title: string; text: string; icon: IconName }[] = [
  {
    title: 'Nhận xét học bạ',
    text: 'Nhận xét từng học sinh cuối học kỳ, giáo viên sửa rồi duyệt.',
    icon: 'file',
  },
  {
    title: 'Phiếu liên lạc',
    text: 'Phiếu gửi phụ huynh, xuất PDF sau khi giáo viên duyệt.',
    icon: 'mail',
  },
  {
    title: 'Báo cáo lớp / khối',
    text: 'Báo cáo tổng hợp số liệu của lớp hoặc khối.',
    icon: 'chart',
  },
]

// Khung Nhận xét & báo cáo. Chưa nối API: Giai đoạn 9 sinh bản nháp bằng LLM (luôn ở trạng thái
// nháp cho tới khi giáo viên bấm Duyệt) và xuất PDF.
export default function ReportsPage() {
  return (
    <>
      <PageTitle title="Nhận xét & báo cáo" subtitle="Bản nháp do AI tạo, giáo viên sửa và duyệt" />
      <p
        role="status"
        className="flex items-start gap-3 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900 ring-1 ring-amber-200"
      >
        <Icon name="info" className="mt-0.5 h-5 w-5" />
        Chức năng sinh nhận xét và báo cáo sẽ được nối ở Giai đoạn 9. Màn hình này mới là khung giao
        diện.
      </p>
      <div className="grid gap-5 lg:grid-cols-3">
        {KINDS.map((kind, index) => (
          <section
            key={kind.title}
            aria-labelledby={`loai-${index}`}
            className="card flex flex-col p-6"
          >
            <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-tint text-brand-700 dark:text-brand-300">
              <Icon name={kind.icon} className="h-6 w-6" />
            </span>
            <h2 id={`loai-${index}`} className="mt-4 text-base font-semibold tracking-tight">
              {kind.title}
            </h2>
            <p className="mt-1 flex-1 text-sm text-slate-500">{kind.text}</p>
            <p className="badge-neutral mt-4 self-start">Bản nháp do AI tạo</p>
            <div className="mt-3 flex gap-2">
              <button type="button" disabled className="btn-secondary btn-sm">
                Tạo bản nháp
              </button>
              <button type="button" disabled className="btn-secondary btn-sm">
                Duyệt
              </button>
            </div>
          </section>
        ))}
      </div>
    </>
  )
}
