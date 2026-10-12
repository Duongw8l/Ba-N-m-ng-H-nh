import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { ScoreRow, SubjectScores } from '../api/analytics'
import { DistributionChart } from '../components/charts/DistributionChart'
import { PageTitle, Panel } from '../components/Panel'
import { PeriodSelect } from '../components/PeriodSelect'
import { QueryState } from '../components/QueryState'
import { StatCard, StatGrid } from '../components/StatCard'
import { useAssignments } from '../hooks/useAssignments'
import { useSubjectScores, usePeriod } from '../hooks/useAnalytics'
import { formatScore } from '../lib/format'
import { COMMENT_LABELS } from '../lib/labels'

const SEMESTERS = ['1', '2'] as const

function Missing() {
  return (
    <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs font-medium text-red-800">thiếu</span>
  )
}

function ScoreCell({ value }: { value: number | undefined | null }) {
  return (
    <td className="px-2 py-1.5 text-right tabular-nums">
      {value === undefined || value === null ? <Missing /> : formatScore(value)}
    </td>
  )
}

function AverageCell({
  value,
  complete,
  scores,
}: {
  value: number | null
  complete: boolean
  scores: SubjectScores
}) {
  const { thresholds } = scores
  let tone = ''
  if (value !== null && value < thresholds.fail) tone = 'font-semibold text-red-700'
  else if (value !== null && value < thresholds.passing) tone = 'font-medium text-amber-700'
  return (
    <td
      className={`px-2 py-1.5 text-right tabular-nums ${tone}`}
      title={value !== null && !complete ? 'Tạm tính: còn thiếu đầu điểm' : undefined}
    >
      {formatScore(value)}
      {value !== null && !complete && <sup aria-label="tạm tính">*</sup>}
    </td>
  )
}

function missingCount(row: ScoreRow): number {
  return row.tx_missing + (row.midterm === null ? 1 : 0) + (row.final === null ? 1 : 0)
}

function ScoreGrid({ scores, rows }: { scores: SubjectScores; rows: ScoreRow[] }) {
  const classId = scores.class_info.id
  const txColumns = Math.max(scores.subject.regular_required, ...rows.map((row) => row.tx.length))
  const txIndexes = Array.from({ length: txColumns }, (_, index) => index)
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
          <tr>
            <th scope="col" className="px-2 py-2 font-medium">
              STT
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Mã HS
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Họ và tên
            </th>
            {txIndexes.map((index) => (
              <th key={index} scope="col" className="px-2 py-2 text-right font-medium">
                TX{index + 1}
              </th>
            ))}
            <th scope="col" className="px-2 py-2 text-right font-medium">
              Giữa kỳ
            </th>
            <th scope="col" className="px-2 py-2 text-right font-medium">
              Cuối kỳ
            </th>
            <th scope="col" className="border-l border-slate-200 px-2 py-2 text-right font-medium">
              ĐTB kỳ này
            </th>
            <th scope="col" className="px-2 py-2 text-right font-medium">
              ĐTB HK I
            </th>
            <th scope="col" className="px-2 py-2 text-right font-medium">
              ĐTB HK II
            </th>
            <th scope="col" className="px-2 py-2 text-right font-medium">
              ĐTB cả năm
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Ghi chú
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, position) => (
            <tr key={row.student_id} className={row.complete ? '' : 'bg-red-50'}>
              <td className="px-2 py-1.5 text-slate-500">{position + 1}</td>
              <td className="px-2 py-1.5 font-mono">{row.student_code}</td>
              <th scope="row" className="px-2 py-1.5 font-normal">
                <Link
                  to={`/classes/${classId}/students/${row.student_id}`}
                  className="text-blue-700 hover:underline"
                >
                  {row.full_name}
                </Link>
              </th>
              {txIndexes.map((index) => (
                <ScoreCell key={index} value={row.tx[index]} />
              ))}
              <ScoreCell value={row.midterm} />
              <ScoreCell value={row.final} />
              <AverageCell value={row.average} complete={row.complete} scores={scores} />
              <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                {formatScore(row.average_semester1)}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                {formatScore(row.average_semester2)}
              </td>
              <td className="px-2 py-1.5 text-right tabular-nums text-slate-600">
                {formatScore(row.year_average)}
              </td>
              <td className="px-2 py-1.5 text-xs text-red-800">
                {!row.complete && `Thiếu ${missingCount(row)} đầu điểm`}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CommentGrid({ scores, rows }: { scores: SubjectScores; rows: ScoreRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 bg-slate-50 text-slate-600">
          <tr>
            <th scope="col" className="px-2 py-2 font-medium">
              STT
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Mã HS
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Họ và tên
            </th>
            <th scope="col" className="px-2 py-2 font-medium">
              Nhận xét
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {rows.map((row, position) => (
            <tr key={row.student_id} className={row.complete ? '' : 'bg-red-50'}>
              <td className="px-2 py-1.5 text-slate-500">{position + 1}</td>
              <td className="px-2 py-1.5 font-mono">{row.student_code}</td>
              <th scope="row" className="px-2 py-1.5 font-normal">
                <Link
                  to={`/classes/${scores.class_info.id}/students/${row.student_id}`}
                  className="text-blue-700 hover:underline"
                >
                  {row.full_name}
                </Link>
              </th>
              <td className="px-2 py-1.5">
                {row.comment_result ? (
                  <span className={row.comment_result === 'fail' ? 'font-medium text-red-700' : ''}>
                    {COMMENT_LABELS[row.comment_result]}
                  </span>
                ) : (
                  <Missing />
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Distribution({ scores }: { scores: SubjectScores }) {
  const { distribution: d, thresholds: t } = scores
  return (
    <DistributionChart
      label="Số học sinh theo khoảng điểm trung bình"
      data={[
        { name: `Dưới ${formatScore(t.fail)}`, value: d.below_fail, color: '#dc2626' },
        {
          name: `${formatScore(t.fail)} đến dưới ${formatScore(t.passing)}`,
          value: d.fail_to_pass,
          color: '#f97316',
        },
        {
          name: `${formatScore(t.passing)} đến dưới ${formatScore(t.fair)}`,
          value: d.pass_to_fair,
          color: '#d97706',
        },
        {
          name: `${formatScore(t.fair)} đến dưới ${formatScore(t.good)}`,
          value: d.fair_to_good,
          color: '#0284c7',
        },
        { name: `Từ ${formatScore(t.good)}`, value: d.at_least_good, color: '#15803d' },
      ]}
    />
  )
}

function ScoresContent({ scores, canImport }: { scores: SubjectScores; canImport: boolean }) {
  const [onlyMissing, setOnlyMissing] = useState(false)
  const isScore = scores.subject.assessment_type === 'score'
  const rows = onlyMissing ? scores.rows.filter((row) => !row.complete) : scores.rows

  return (
    <>
      <StatGrid>
        <StatCard label="Sĩ số" value={scores.student_count} />
        {isScore ? (
          <StatCard label="ĐTB của lớp" value={formatScore(scores.mean)} />
        ) : (
          <StatCard
            label="Chưa đạt"
            value={scores.comment_fail_count}
            valueClassName={scores.comment_fail_count > 0 ? 'text-red-700' : 'text-slate-900'}
          />
        )}
        <StatCard
          label="Chưa đủ đầu điểm"
          value={scores.incomplete_count}
          valueClassName={scores.incomplete_count > 0 ? 'text-red-700' : 'text-slate-900'}
          hint={
            isScore
              ? `Mỗi học kỳ cần ${scores.subject.regular_required} đầu điểm thường xuyên`
              : undefined
          }
        />
        {canImport && (
          <div className="flex items-center rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <Link
              to={`/classes/${scores.class_info.id}/import?kind=assessments&subject=${scores.subject.id}`}
              className="font-medium text-blue-700 hover:underline"
            >
              Nhập điểm từ tệp
            </Link>
          </div>
        )}
      </StatGrid>

      {isScore && (
        <Panel id="phan-bo" title="Phân bố điểm trung bình">
          <Distribution scores={scores} />
        </Panel>
      )}

      <Panel
        id="luoi-diem"
        title={isScore ? 'Bảng điểm' : 'Nhận xét'}
        description={
          isScore
            ? 'ĐTB do hệ thống tính theo Thông tư 22. Dấu * là điểm tạm tính vì còn thiếu đầu điểm.'
            : undefined
        }
      >
        <label className="mb-3 flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            checked={onlyMissing}
            onChange={(event) => setOnlyMissing(event.target.checked)}
          />
          Chỉ hiện học sinh còn thiếu đầu điểm
        </label>
        {rows.length === 0 ? (
          <p className="text-sm text-slate-600">Không có học sinh nào thiếu đầu điểm.</p>
        ) : isScore ? (
          <ScoreGrid scores={scores} rows={rows} />
        ) : (
          <CommentGrid scores={scores} rows={rows} />
        )}
      </Panel>
    </>
  )
}

// Bảng điểm một môn của lớp (GVBM đúng môn, GVCN, BGH): lưới đầu điểm, ĐTB do server tính, ô thiếu
// đầu điểm được tô nổi.
export default function SubjectScoresPage() {
  const params = useParams()
  const classId = Number(params.classId)
  const subjectId = Number(params.subjectId)
  const [period, setPeriod] = usePeriod(SEMESTERS, '1')
  const scores = useSubjectScores(classId, subjectId, period === '2' ? 2 : 1)
  const assignments = useAssignments()
  const canImport =
    assignments.data?.teaching.some(
      (item) => item.class_id === classId && item.subject_id === subjectId,
    ) ?? false
  // Dashboard lớp chỉ dành cho GVCN của lớp và BGH (GVBM nhận 403), nên chỉ hiện liên kết cho họ.
  const canOpenDashboard =
    assignments.data !== undefined &&
    (assignments.data.user.role === 'principal' ||
      assignments.data.homeroom_classes.some((item) => item.id === classId))
  const data = scores.data

  return (
    <>
      <PageTitle
        title={
          data ? `Bảng điểm ${data.subject.name} · lớp ${data.class_info.name}` : 'Bảng điểm môn'
        }
        actions={
          <>
            <PeriodSelect value={period} options={SEMESTERS} onChange={setPeriod} />
            {canOpenDashboard && (
              <Link
                to={`/classes/${classId}`}
                className="text-sm font-medium text-blue-700 hover:underline"
              >
                Dashboard lớp
              </Link>
            )}
          </>
        }
      />
      <QueryState query={scores}>
        {(result) => <ScoresContent key={result.semester} scores={result} canImport={canImport} />}
      </QueryState>
    </>
  )
}
