import type { UseQueryResult } from '@tanstack/react-query'
import { useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import type { GradeOverview } from '../api/analytics'
import { ClassLevelsChart } from '../components/charts/ClassLevelsChart'
import { CompareChart } from '../components/charts/CompareChart'
import type { CompareDatum } from '../components/charts/CompareChart'
import { PageTitle, Panel } from '../components/Panel'
import { PeriodSelect } from '../components/PeriodSelect'
import { QueryState } from '../components/QueryState'
import { useGradeOverview, usePeriod } from '../hooks/useAnalytics'
import { formatScore } from '../lib/format'
import { LEVEL_LABELS, PERIOD_LABELS } from '../lib/labels'

const PERIODS = ['1', '2', 'year'] as const

function Th({ children, right = true }: { children: ReactNode; right?: boolean }) {
  return (
    <th scope="col" className={`px-3 py-2 font-medium ${right ? 'text-right' : ''}`}>
      {children}
    </th>
  )
}

function ClassesTable({ overview }: { overview: GradeOverview }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-max text-left text-sm">
        <thead className="border-b border-slate-200 text-slate-500">
          <tr>
            <Th right={false}>Lớp</Th>
            <Th>Sĩ số</Th>
            <Th>{LEVEL_LABELS.good}</Th>
            <Th>{LEVEL_LABELS.fair}</Th>
            <Th>{LEVEL_LABELS.pass}</Th>
            <Th>{LEVEL_LABELS.fail}</Th>
            <Th>{LEVEL_LABELS.incomplete}</Th>
            <Th>Nghỉ nhiều</Th>
            <Th>Nghỉ quá số buổi</Th>
            <Th>Có môn điểm quá thấp</Th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100">
          {overview.classes.map((item) => (
            <tr key={item.class_id}>
              <th scope="row" className="px-3 py-2 font-normal">
                <Link to={`/classes/${item.class_id}`} className="text-blue-700 hover:underline">
                  {item.name}
                </Link>
              </th>
              <td className="px-3 py-2 text-right tabular-nums">{item.student_count}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.learning_levels.good}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.learning_levels.fair}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.learning_levels.pass}</td>
              <td className="px-3 py-2 text-right tabular-nums">{item.learning_levels.fail}</td>
              <td className="px-3 py-2 text-right tabular-nums">
                {item.learning_levels.incomplete}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{item.absent_notice_students}</td>
              <td className="px-3 py-2 text-right tabular-nums">
                {item.absent_over_limit_students}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{item.below_fail_students}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function meanOf(overview: GradeOverview, subjectId: number, classId: number): number | null {
  return (
    overview.common_subjects
      .find((subject) => subject.subject_id === subjectId)
      ?.class_means.find((item) => item.class_id === classId)?.mean ?? null
  )
}

function Comparison({ first, second }: { first: GradeOverview; second: GradeOverview }) {
  const [chosen, setChosen] = useState<number | null>(null)
  const subjects = first.common_subjects
  const subjectId = chosen ?? subjects[0]?.subject_id ?? null

  const meanData: CompareDatum[] =
    subjectId === null
      ? []
      : first.classes.map((item) => ({
          name: item.name,
          first: meanOf(first, subjectId, item.class_id),
          second: meanOf(second, subjectId, item.class_id),
        }))
  const failData: CompareDatum[] = first.classes.map((item) => ({
    name: item.name,
    first: item.learning_levels.fail ?? 0,
    second: second.classes.find((other) => other.class_id === item.class_id)?.learning_levels.fail ?? 0,
  }))

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-700">
            Môn
            <select
              value={subjectId ?? ''}
              onChange={(event) => setChosen(Number(event.target.value))}
              className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-base"
            >
              {subjects.map((subject) => (
                <option key={subject.subject_id} value={subject.subject_id}>
                  {subject.name}
                </option>
              ))}
            </select>
          </label>
          <CompareChart data={meanData} kind="score" label="ĐTB của lớp: học kỳ I so với học kỳ II" />
        </div>
        <div>
          <p className="mb-2 text-sm font-medium text-slate-700">
            Số học sinh xếp loại {LEVEL_LABELS.fail}
          </p>
          <CompareChart
            data={failData}
            kind="count"
            label="Số học sinh Chưa đạt: học kỳ I so với học kỳ II"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-max text-left text-sm">
          <caption className="pb-2 text-left text-sm text-slate-500">
            ĐTB của lớp theo môn: học kỳ I → học kỳ II
          </caption>
          <thead className="border-b border-slate-200 text-slate-500">
            <tr>
              <Th right={false}>Môn</Th>
              {first.classes.map((item) => (
                <Th key={item.class_id}>{item.name}</Th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {subjects.map((subject) => (
              <tr key={subject.subject_id}>
                <th scope="row" className="px-3 py-2 font-normal">
                  {subject.name}
                </th>
                {first.classes.map((item) => (
                  <td key={item.class_id} className="px-3 py-2 text-right tabular-nums">
                    {formatScore(meanOf(first, subject.subject_id, item.class_id))}
                    <span aria-hidden="true"> → </span>
                    <span className="sr-only"> sang </span>
                    {formatScore(meanOf(second, subject.subject_id, item.class_id))}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function CompareSection({
  first,
  second,
}: {
  first: UseQueryResult<GradeOverview>
  second: UseQueryResult<GradeOverview>
}) {
  // Cần cả hai học kỳ: hiện lỗi của bên nào hỏng trước, còn lại thì chờ.
  if (first.isError) return <QueryState query={first}>{() => null}</QueryState>
  if (second.isError) return <QueryState query={second}>{() => null}</QueryState>
  if (first.isPending || second.isPending) {
    return (
      <p aria-live="polite" className="text-slate-600">
        Đang tải…
      </p>
    )
  }
  return <Comparison first={first.data} second={second.data} />
}

// Dashboard khối (BGH): so sánh các lớp trong khối, học kỳ I cạnh học kỳ II. Chỉ số liệu gộp theo
// lớp, không có tên học sinh.
export default function GradeOverviewPage() {
  const level = Number(useParams().level)
  const [period, setPeriod] = usePeriod(PERIODS, '1')
  const selected = useGradeOverview(level, period)
  const first = useGradeOverview(level, '1')
  const second = useGradeOverview(level, '2')

  return (
    <>
      <PageTitle
        title={`Khối ${level}`}
        subtitle="So sánh các lớp trong khối"
        actions={<PeriodSelect value={period} options={PERIODS} onChange={setPeriod} />}
      />
      <QueryState query={selected}>
        {(overview) => (
          <>
            <Panel id="cac-lop" title={`Các lớp · ${PERIOD_LABELS[period]}`}>
              <ClassesTable overview={overview} />
            </Panel>
            <Panel
              id="muc-hoc-tap"
              title="Kết quả học tập theo lớp"
              description="Số học sinh ở từng mức; cột cao hơn nghĩa là lớp đông hơn."
            >
              <ClassLevelsChart
                classes={overview.classes}
                label="Số học sinh theo kết quả học tập của từng lớp"
              />
            </Panel>
          </>
        )}
      </QueryState>
      <Panel
        id="hk1-hk2"
        title="Học kỳ I so với học kỳ II"
        description="Chỉ các môn mà mọi lớp trong khối đều học. ĐTB của lớp là số mô tả để so sánh, không phải số của Thông tư."
      >
        <CompareSection first={first} second={second} />
      </Panel>
    </>
  )
}
