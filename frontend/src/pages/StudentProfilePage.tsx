import { Link, useParams } from 'react-router-dom'
import type {
  ProfileSemester,
  ProfileSubject,
  StudentProfile,
  StudentProfileFull,
  Thresholds,
} from '../api/analytics'
import { ProfileAlertPanel } from '../components/alerts/ProfileAlertPanel'
import { AbsenceMeter } from '../components/AbsenceMeter'
import { AbsenceChart } from '../components/charts/AbsenceChart'
import { Icon } from '../components/Icon'
import { Panel } from '../components/Panel'
import { PeriodSelect } from '../components/PeriodSelect'
import { QueryState } from '../components/QueryState'
import { StatCard, StatGrid } from '../components/StatCard'
import { useAssignments } from '../hooks/useAssignments'
import { usePeriod, useStudentProfile } from '../hooks/useAnalytics'
import { formatScore } from '../lib/format'
import { initialsOf } from '../lib/initials'
import {
  COMMENT_LABELS,
  PERIOD_LABELS,
  PROMOTION_REASON_LABELS,
  RETAKE_REASON_LABELS,
  RISK_LABELS,
  levelLabel,
} from '../lib/labels'

const PERIODS = ['1', '2', 'year'] as const

function averageTone(value: number | null, thresholds: Thresholds): string {
  if (value === null) return ''
  if (value < thresholds.fail) return 'font-semibold text-red-700'
  if (value < thresholds.passing) return 'font-medium text-amber-700'
  return 'font-medium'
}

function SemesterCell({
  subject,
  semester,
  thresholds,
}: {
  subject: ProfileSubject
  semester: ProfileSemester
  thresholds: Thresholds
}) {
  if (subject.assessment_type === 'comment') {
    return semester.comment_result ? (
      <span className={semester.comment_result === 'fail' ? 'font-medium text-red-700' : ''}>
        {COMMENT_LABELS[semester.comment_result]}
      </span>
    ) : (
      <span className="text-red-800">chưa có</span>
    )
  }
  const missing = semester.tx_missing + (semester.midterm === null ? 1 : 0) + (semester.final === null ? 1 : 0)
  return (
    <div>
      <span className={`tabular-nums ${averageTone(semester.average, thresholds)}`}>
        {formatScore(semester.average)}
        {semester.average !== null && !semester.complete && <sup aria-label="tạm tính">*</sup>}
      </span>
      <span className="mt-0.5 block text-xs text-slate-500 tabular-nums">
        TX: {semester.tx.length > 0 ? semester.tx.map((value) => formatScore(value)).join(' · ') : '—'}
        {' | '}GK {formatScore(semester.midterm)} | CK {formatScore(semester.final)}
      </span>
      {missing > 0 && (
        <span className="mt-0.5 block text-xs font-medium text-red-800">Thiếu {missing} đầu điểm</span>
      )}
    </div>
  )
}

function SubjectsTable({
  subjects,
  thresholds,
}: {
  subjects: ProfileSubject[]
  thresholds: Thresholds
}) {
  return (
    <div className="overflow-x-auto">
      <table className="data-table min-w-max">
        <thead>
          <tr>
            <th scope="col" className="py-2 pr-4 font-medium">
              Môn
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Học kỳ I
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Học kỳ II
            </th>
            <th scope="col" className="px-3 py-2 font-medium">
              Cả năm
            </th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-100 align-top">
          {subjects.map((subject) => (
            <tr key={subject.subject_id}>
              <th scope="row" className="py-2 pr-4 font-normal">
                {subject.name}
                {subject.assessment_type === 'comment' && (
                  <span className="ml-2 text-xs text-slate-500">(nhận xét)</span>
                )}
              </th>
              {subject.semesters.map((semester) => (
                <td key={semester.semester} className="px-3 py-2">
                  <SemesterCell subject={subject} semester={semester} thresholds={thresholds} />
                </td>
              ))}
              <td className="px-3 py-2">
                {subject.assessment_type === 'comment' ? (
                  subject.year_comment_result ? (
                    COMMENT_LABELS[subject.year_comment_result]
                  ) : (
                    '—'
                  )
                ) : (
                  <span className={`tabular-nums ${averageTone(subject.year_average, thresholds)}`}>
                    {formatScore(subject.year_average)}
                  </span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FullProfile({ profile, canRecord }: { profile: StudentProfileFull; canRecord: boolean }) {
  const { learning, conduct, attendance, promotion } = profile
  const eligibleText =
    promotion === null
      ? null
      : promotion.eligible === true
        ? 'Đủ điều kiện'
        : promotion.eligible === false
          ? 'Không đủ điều kiện'
          : 'Chưa đủ dữ liệu'

  return (
    <>
      <StatGrid>
        <StatCard
          label="Kết quả học tập"
          value={levelLabel(learning.level, 'Chưa đủ dữ liệu')}
          valueClassName={learning.level === 'fail' ? 'text-red-700' : 'text-slate-900'}
          hint={
            learning.adjusted
              ? 'Đã điều chỉnh mức theo quy định'
              : learning.incomplete_subjects.length > 0
                ? `Thiếu dữ liệu ở ${learning.incomplete_subjects.length} môn`
                : undefined
          }
        />
        <StatCard
          label="Rèn luyện"
          value={levelLabel(conduct.level)}
          valueClassName={conduct.level === 'fail' ? 'text-red-700' : 'text-slate-900'}
          hint={conduct.derived ? 'Cả năm: suy ra từ học kỳ II' : undefined}
        />
        <StatCard
          label="Số buổi nghỉ"
          value={attendance.absent_total}
          hint={`Có phép ${attendance.excused}, không phép ${attendance.unexcused}, đi muộn ${attendance.late}`}
        />
        {eligibleText !== null ? (
          <StatCard
            label="Điều kiện lên lớp"
            value={eligibleText}
            valueClassName={
              promotion?.eligible === false
                ? 'text-red-700'
                : promotion?.eligible === true
                  ? 'text-green-700'
                  : 'text-slate-900'
            }
            hint="Chỉ để tham khảo; hội đồng nhà trường quyết định"
          />
        ) : (
          <StatCard
            label="Cảnh báo sớm"
            value={profile.alert ? RISK_LABELS[profile.alert.level] : '—'}
            valueClassName={profile.alert?.level === 'high' ? 'text-red-700' : 'text-slate-900'}
            hint="Chi tiết ở mục Cảnh báo sớm bên dưới"
          />
        )}
      </StatGrid>

      <ProfileAlertPanel alert={profile.alert} canRecord={canRecord} />

      <Panel
        id="cac-mon"
        title="Điểm các môn"
        description="ĐTB do hệ thống tính theo Thông tư 22. Dấu * là điểm tạm tính vì còn thiếu đầu điểm."
      >
        <SubjectsTable subjects={profile.subjects} thresholds={profile.thresholds} />
      </Panel>

      <Panel id="chuyen-can" title="Chuyên cần">
        <div className="grid gap-6 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Cả năm học</p>
            <AbsenceMeter total={attendance.absent_total} limits={attendance.limits} />
          </div>
          <div>
            <p className="mb-2 text-sm font-medium text-slate-700">Theo tháng</p>
            <AbsenceChart months={attendance.by_month} label="Số buổi nghỉ của học sinh theo tháng" />
          </div>
        </div>
      </Panel>

      {promotion && (
        <Panel id="len-lop" title="Điều kiện lên lớp">
          <p className="text-sm font-medium">{eligibleText}</p>
          {promotion.reasons.length > 0 && (
            <ul className="mt-2 list-inside list-disc text-sm text-slate-700">
              {promotion.reasons.map((reason) => (
                <li key={reason}>{PROMOTION_REASON_LABELS[reason] ?? reason}</li>
              ))}
            </ul>
          )}
          {promotion.retake_subjects.length > 0 && (
            <>
              <p className="mt-3 text-sm font-medium">Môn có thể phải kiểm tra lại</p>
              <ul className="mt-1 list-inside list-disc text-sm text-slate-700">
                {promotion.retake_subjects.map((item) => (
                  <li key={item.subject_id}>
                    {item.name}: {RETAKE_REASON_LABELS[item.reason] ?? item.reason}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Panel>
      )}

      <Panel id="phu-huynh" title="Thông tin phụ huynh">
        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
          <dt className="text-slate-500">Họ tên</dt>
          <dd>{profile.guardian_name ?? '—'}</dd>
          <dt className="text-slate-500">Số điện thoại</dt>
          <dd className="tabular-nums">{profile.guardian_phone ?? '—'}</dd>
        </dl>
      </Panel>
    </>
  )
}

function ProfileContent({ profile, canRecord }: { profile: StudentProfile; canRecord: boolean }) {
  if (profile.scope === 'full') return <FullProfile profile={profile} canRecord={canRecord} />
  return (
    <>
      <p className="card p-4 text-sm text-slate-600">
        Bạn chỉ xem được điểm các môn mình dạy ở lớp này.
      </p>
      <Panel id="cac-mon" title="Điểm các môn bạn dạy">
        <SubjectsTable subjects={profile.subjects} thresholds={profile.thresholds} />
      </Panel>
    </>
  )
}

// Hồ sơ một học sinh: GVCN và BGH thấy đầy đủ (kể cả chuyên cần, rèn luyện, phụ huynh); GVBM chỉ thấy
// điểm các môn mình dạy. Phạm vi do back-end quyết định, trang chỉ hiển thị những gì API trả.
export default function StudentProfilePage() {
  const params = useParams()
  const classId = Number(params.classId)
  const studentId = Number(params.studentId)
  const [period, setPeriod] = usePeriod(PERIODS, '1')
  const profile = useStudentProfile(classId, studentId, period)
  const assignments = useAssignments()
  const data = profile.data
  const isHomeroom = assignments.data?.homeroom_classes.some((item) => item.id === classId) ?? false
  const canOpenDashboard =
    assignments.data !== undefined &&
    (assignments.data.user.role === 'principal' ||
      assignments.data.homeroom_classes.some((item) => item.id === classId))

  return (
    <>
      <header className="flex flex-wrap items-center justify-between gap-x-6 gap-y-4">
        <div className="flex min-w-0 items-center gap-4">
          <span
            aria-hidden="true"
            className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-linear-to-br from-brand-400 to-brand-700 text-xl font-semibold text-white shadow-sm"
          >
            {data ? initialsOf(data.student.full_name) : <Icon name="user" className="h-7 w-7" />}
          </span>
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-semibold tracking-tight">
              {data ? data.student.full_name : 'Hồ sơ học sinh'}
            </h1>
            {data && (
              <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-slate-500">
                <span>
                  Mã {data.student.student_code} · lớp {data.class_info.name}
                  {data.scope === 'full' ? ` · ${PERIOD_LABELS[period]}` : ''}
                </span>
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {/* GVBM chỉ có điểm theo từng học kỳ nên không có ô chọn kỳ. */}
          {data?.scope !== 'subjects' && (
            <PeriodSelect value={period} options={PERIODS} onChange={setPeriod} />
          )}
          {canOpenDashboard && (
            <Link to={`/classes/${classId}`} className="link text-sm">
              ← Dashboard lớp
            </Link>
          )}
          <button
            type="button"
            disabled
            title="Tạo nhận xét có ở Giai đoạn 9"
            className="btn-secondary btn-sm"
          >
            Tạo nhận xét
          </button>
        </div>
      </header>
      <QueryState query={profile}>
        {(result) => <ProfileContent profile={result} canRecord={isHomeroom} />}
      </QueryState>
    </>
  )
}
