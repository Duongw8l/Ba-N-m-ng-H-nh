import { Link, useParams } from 'react-router-dom'
import type { Dashboard } from '../api/analytics'
import { AbsenceChart } from '../components/charts/AbsenceChart'
import { LevelChart } from '../components/charts/LevelChart'
import { LevelBar } from '../components/LevelBar'
import { PageTitle, Panel } from '../components/Panel'
import { PeriodSelect } from '../components/PeriodSelect'
import { QueryState } from '../components/QueryState'
import { StatCard, StatGrid } from '../components/StatCard'
import { useAssignments } from '../hooks/useAssignments'
import { useDashboard, usePeriod } from '../hooks/useAnalytics'
import { formatInt, formatScore } from '../lib/format'
import { ATTENTION_LABELS, PERIOD_LABELS } from '../lib/labels'

const PERIODS = ['1', '2', 'year'] as const
const LEARNING_KEYS = ['good', 'fair', 'pass', 'fail', 'incomplete'] as const
const CONDUCT_KEYS = ['good', 'fair', 'pass', 'fail', 'missing'] as const

function SubjectTable({ dashboard }: { dashboard: Dashboard }) {
  const { thresholds } = dashboard
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">
              Môn
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              ĐTB của lớp
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Số HS có ĐTB
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Dưới {formatScore(thresholds.passing)}
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Dưới {formatScore(thresholds.fail)}
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Thiếu dữ liệu
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {dashboard.subjects.map((subject) => (
            <tr key={subject.subject_id}>
              <th scope="row" className="py-2 pr-4 font-normal">
                <Link
                  to={`/classes/${dashboard.class_info.id}/subjects/${subject.subject_id}`}
                  className="text-blue-700 hover:underline"
                >
                  {subject.name}
                </Link>
                {subject.assessment_type === 'comment' && (
                  <span className="ml-2 text-xs text-slate-500">(nhận xét)</span>
                )}
              </th>
              {subject.assessment_type === 'score' ? (
                <>
                  <td className="px-3 py-2 text-right font-medium tabular-nums">
                    {formatScore(subject.mean)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">{subject.student_count}</td>
                  <td className="px-3 py-2 text-right tabular-nums">{subject.below_pass}</td>
                  <td
                    className={`px-3 py-2 text-right tabular-nums ${subject.below_fail > 0 ? 'font-medium text-red-700' : ''}`}
                  >
                    {subject.below_fail}
                  </td>
                </>
              ) : (
                <>
                  <td className="px-3 py-2 text-right text-slate-500">—</td>
                  <td className="px-3 py-2 text-right text-slate-500">—</td>
                  <td
                    colSpan={2}
                    className={`px-3 py-2 text-right tabular-nums ${subject.comment_fail > 0 ? 'text-red-700' : ''}`}
                  >
                    Chưa đạt: {subject.comment_fail}
                  </td>
                </>
              )}
              <td className="px-3 py-2 text-right tabular-nums">{subject.incomplete}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function AttentionTable({ dashboard }: { dashboard: Dashboard }) {
  if (dashboard.attention.length === 0) {
    return <p className="text-sm text-slate-600">Không có học sinh nào cần quan tâm.</p>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">
              Học sinh
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Mã HS
            </th>
            <th scope="col" className="px-3 py-2 text-right font-medium">
              Số buổi nghỉ
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Lý do
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {dashboard.attention.map((item) => (
            <tr key={item.student_id}>
              <th scope="row" className="py-2 pr-4 font-normal">
                <Link
                  to={`/classes/${dashboard.class_info.id}/students/${item.student_id}`}
                  className="text-blue-700 hover:underline"
                >
                  {item.full_name}
                </Link>
              </th>
              <td className="px-3 py-2 font-mono">{item.student_code}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.absent_sessions}</td>
              <td className="px-3 py-2">
                <ul className="flex flex-wrap gap-1">
                  {item.reasons.map((reason) => (
                    <li
                      key={reason}
                      className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-900"
                    >
                      {ATTENTION_LABELS[reason] ?? reason}
                    </li>
                  ))}
                </ul>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function DashboardContent({ dashboard }: { dashboard: Dashboard }) {
  const { absence_limits: limits } = dashboard
  return (
    <>
      <StatGrid>
        <StatCard
          label="Sĩ số"
          value={formatInt(dashboard.student_count)}
          hint={`Khối ${dashboard.class_info.grade_level}`}
        />
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <dt className="text-sm text-slate-500">Các mức học tập</dt>
          <dd className="mt-2">
            <LevelBar
              counts={dashboard.learning_levels}
              keys={LEARNING_KEYS}
              total={dashboard.student_count}
            />
          </dd>
        </div>
        <StatCard
          label={`Nghỉ từ ${limits.notice} buổi`}
          value={formatInt(dashboard.absent_notice_students)}
          valueClassName={dashboard.absent_notice_students > 0 ? 'text-amber-700' : 'text-slate-900'}
          hint={`Nghỉ quá ${limits.maximum} buổi: ${dashboard.absent_over_limit_students}`}
        />
        <StatCard label="Cảnh báo sớm" value="—" hint="Sẽ có ở Giai đoạn 6" />
      </StatGrid>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel id="hoc-tap" title="Kết quả học tập">
          <LevelChart
            counts={dashboard.learning_levels}
            keys={LEARNING_KEYS}
            label="Số học sinh theo kết quả học tập"
          />
        </Panel>
        <Panel
          id="ren-luyen"
          title="Rèn luyện"
          description={
            dashboard.conduct_derived_count > 0
              ? `${dashboard.conduct_derived_count} học sinh có rèn luyện cả năm suy ra từ học kỳ II.`
              : undefined
          }
        >
          <LevelChart
            counts={dashboard.conduct_levels}
            keys={CONDUCT_KEYS}
            label="Số học sinh theo mức rèn luyện"
          />
        </Panel>
      </div>

      {dashboard.promotion && (
        <Panel
          id="len-lop"
          title="Điều kiện lên lớp (cả năm)"
          description="Chỉ để tham khảo. Quyết định cuối cùng do hội đồng nhà trường."
        >
          <StatGrid>
            <StatCard
              label="Đủ điều kiện"
              value={dashboard.promotion.eligible}
              valueClassName="text-green-700"
            />
            <StatCard
              label="Không đủ điều kiện"
              value={dashboard.promotion.not_eligible}
              valueClassName={dashboard.promotion.not_eligible > 0 ? 'text-red-700' : 'text-slate-900'}
            />
            <StatCard label="Chưa đủ dữ liệu" value={dashboard.promotion.unknown} />
          </StatGrid>
        </Panel>
      )}

      <Panel id="dtb-cac-mon" title="Điểm trung bình các môn">
        <SubjectTable dashboard={dashboard} />
      </Panel>

      <Panel
        id="can-quan-tam"
        title="Học sinh cần quan tâm"
        description="Lấy từ kết quả tính điểm và chuyên cần; chưa phải cảnh báo sớm (Giai đoạn 6)."
      >
        <AttentionTable dashboard={dashboard} />
      </Panel>

      <Panel
        id="nghi-theo-thang"
        title="Số buổi nghỉ theo tháng"
        description="Tổng số buổi nghỉ của cả lớp trong từng tháng của năm học (đi muộn không tính là nghỉ)."
      >
        <AbsenceChart months={dashboard.absences_by_month} label="Số buổi nghỉ của lớp theo tháng" />
      </Panel>
    </>
  )
}

// Dashboard lớp (GVCN của lớp và BGH): 4 ô số liệu, bảng ĐTB các môn, học sinh cần quan tâm, nghỉ
// theo tháng. Mọi con số do back-end tính; trang chỉ hiển thị.
export default function ClassDashboardPage() {
  const classId = Number(useParams().classId)
  const [period, setPeriod] = usePeriod(PERIODS, '1')
  const dashboard = useDashboard(classId, period)
  const assignments = useAssignments()
  const isHomeroom = assignments.data?.homeroom_classes.some((item) => item.id === classId) ?? false
  const name = dashboard.data?.class_info.name

  return (
    <>
      <PageTitle
        title={name ? `Lớp ${name}` : 'Dashboard lớp'}
        subtitle={`Kỳ xem: ${PERIOD_LABELS[period]}`}
        actions={
          <>
            <PeriodSelect value={period} options={PERIODS} onChange={setPeriod} />
            {isHomeroom && (
              <Link
                to={`/classes/${classId}/import`}
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Nhập dữ liệu
              </Link>
            )}
          </>
        }
      />
      <QueryState query={dashboard}>{(data) => <DashboardContent dashboard={data} />}</QueryState>
    </>
  )
}
