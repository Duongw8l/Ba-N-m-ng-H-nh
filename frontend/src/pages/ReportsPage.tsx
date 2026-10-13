import type { ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'
import type { Period } from '../api/analytics'
import type { Assignments } from '../api/auth'
import type { ReportType } from '../api/reports'
import { Icon } from '../components/Icon'
import { PageTitle, Panel } from '../components/Panel'
import { PeriodSelect } from '../components/PeriodSelect'
import { QueryState } from '../components/QueryState'
import { AggregateReport } from '../components/reports/AggregateReport'
import { TYPE_HINTS, TYPE_LABELS } from '../components/reports/options'
import { StudentReports } from '../components/reports/StudentReports'
import { useGradeOverview, usePeriod } from '../hooks/useAnalytics'
import { useAssignments } from '../hooks/useAssignments'
import { useReportList } from '../hooks/useReports'
import type { ReportTarget } from '../api/reports'

const PERIODS = ['1', '2', 'year'] as const
// Nhận xét môn chỉ viết cho từng học kỳ (back-end cũng từ chối cả năm).
const SUBJECT_PERIODS = ['1', '2'] as const

// Nhận xét và báo cáo do AI viết (DESIGN mục 6.5, FLOWS luồng 5). Mọi bản sinh ra là bản nháp cho tới
// khi giáo viên bấm Duyệt; chỉ bản đã duyệt mới xuất được PDF. Quyền do back-end quyết định: trang
// chỉ ẩn những lựa chọn người dùng chắc chắn không có.
export default function ReportsPage() {
  const assignments = useAssignments()
  return (
    <>
      <PageTitle title="Nhận xét & báo cáo" subtitle="Bản nháp do AI tạo, giáo viên sửa và duyệt" />
      <p className="flex items-start gap-3 rounded-2xl bg-tint p-4 text-sm text-tint-text ring-1 ring-brand-200/70">
        <Icon name="info" className="mt-0.5 h-5 w-5 shrink-0" />
        <span>
          Số liệu do hệ thống tính từ điểm và điểm danh; AI chỉ diễn đạt lại. Họ tên học sinh được
          thay bằng mã tạm trước khi gửi cho mô hình AI. Nhận xét nào không qua kiểm tra tự động (số
          liệu, từ ngữ) sẽ được để trống cho thầy/cô tự viết. Chỉ bản đã duyệt mới xuất được PDF.
        </span>
      </p>
      <QueryState query={assignments}>{(data) => <Workspace data={data} />}</QueryState>
    </>
  )
}

function typeOptionsOf(data: Assignments): ReportType[] {
  if (data.user.role === 'principal') return ['report']
  if (data.user.role !== 'teacher') return []
  return [
    ...(data.teaching.length > 0 ? (['subject_comment'] as const) : []),
    ...(data.homeroom_classes.length > 0
      ? (['school_record', 'contact_slip', 'report'] as const)
      : []),
  ]
}

function Workspace({ data }: { data: Assignments }) {
  const [params, setParams] = useSearchParams()
  const options = typeOptionsOf(data)
  const type = options.find((option) => option === params.get('type')) ?? options[0]
  const [period, setPeriod] = usePeriod(type === 'subject_comment' ? SUBJECT_PERIODS : PERIODS, '1')

  function setParam(changes: Record<string, string | null>) {
    setParams(
      (current) => {
        const next = new URLSearchParams(current)
        for (const [key, value] of Object.entries(changes)) {
          if (value === null) next.delete(key)
          else next.set(key, value)
        }
        return next
      },
      { replace: true },
    )
  }

  if (type === undefined) {
    return (
      <p className="card p-6 text-slate-600">
        Tài khoản này không có lớp nào để viết nhận xét hoặc báo cáo. Giáo viên cần được phân công
        dạy một môn hoặc chủ nhiệm một lớp; quản trị viên không xem dữ liệu học sinh nên không dùng
        chức năng này.
      </p>
    )
  }
  const student = Number(params.get('student'))
  const common = {
    type,
    options,
    period,
    setPeriod,
    setParam,
    params,
    initialStudentId: Number.isInteger(student) && student > 0 ? student : null,
  }
  return data.user.role === 'principal' ? (
    <PrincipalWorkspace grades={data.grades} {...common} />
  ) : (
    <TeacherWorkspace data={data} {...common} />
  )
}

interface WorkspaceProps {
  type: ReportType
  options: ReportType[]
  period: Period
  setPeriod: (period: Period) => void
  setParam: (changes: Record<string, string | null>) => void
  params: URLSearchParams
  initialStudentId: number | null
}

function Toolbar({
  type,
  options,
  period,
  setPeriod,
  setParam,
  children,
}: Pick<WorkspaceProps, 'type' | 'options' | 'period' | 'setPeriod' | 'setParam'> & {
  children: ReactNode
}) {
  return (
    <div className="card space-y-3 p-4 sm:p-5">
      <div className="grid gap-4 sm:grid-cols-2">
        <div>
          <label htmlFor="loai-nhan-xet" className="label">
            Loại
          </label>
          <select
            id="loai-nhan-xet"
            value={type}
            onChange={(event) =>
              setParam({ type: event.target.value, subject: null, student: null })
            }
            disabled={options.length === 1}
            className="input mt-1"
          >
            {options.map((option) => (
              <option key={option} value={option}>
                {TYPE_LABELS[option]}
              </option>
            ))}
          </select>
        </div>
        {children}
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="text-sm text-slate-500">{TYPE_HINTS[type]}</p>
        <PeriodSelect
          value={period}
          options={type === 'subject_comment' ? SUBJECT_PERIODS : PERIODS}
          onChange={setPeriod}
        />
      </div>
    </div>
  )
}

interface Choice {
  value: string
  label: string
  classId: number
  className: string
  subjectId?: number
}

function TeacherWorkspace({ data, ...props }: WorkspaceProps & { data: Assignments }) {
  const { type, period, params, setParam, initialStudentId } = props
  const choices: Choice[] =
    type === 'subject_comment'
      ? data.teaching.map((item) => ({
          value: `${item.class_id}:${item.subject_id}`,
          label: `Lớp ${item.class_name} · ${item.subject_name}`,
          classId: item.class_id,
          className: item.class_name,
          subjectId: item.subject_id,
        }))
      : data.homeroom_classes.map((item) => ({
          value: String(item.id),
          label: `Lớp ${item.name}`,
          classId: item.id,
          className: item.name,
        }))
  const wanted =
    type === 'subject_comment'
      ? `${params.get('class')}:${params.get('subject')}`
      : params.get('class')
  const choice = choices.find((item) => item.value === wanted) ?? choices[0]
  const target: ReportTarget = {
    type,
    semester: period,
    classId: choice.classId,
    ...(choice.subjectId !== undefined && { subjectId: choice.subjectId }),
  }

  return (
    <>
      <Toolbar {...props}>
        <div>
          <label htmlFor="pham-vi" className="label">
            {type === 'subject_comment' ? 'Lớp và môn' : 'Lớp'}
          </label>
          <select
            id="pham-vi"
            value={choice.value}
            onChange={(event) => {
              const picked = choices.find((item) => item.value === event.target.value)
              if (picked === undefined) return
              setParam({
                class: String(picked.classId),
                subject: picked.subjectId === undefined ? null : String(picked.subjectId),
                student: null,
              })
            }}
            className="input mt-1"
          >
            {choices.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>
      </Toolbar>
      <ReportBody
        key={`${type}-${choice.value}-${period}`}
        target={target}
        scopeLabel={`lớp ${choice.className}`}
        initialStudentId={initialStudentId}
      />
    </>
  )
}

function PrincipalWorkspace({ grades, ...props }: WorkspaceProps & { grades: number[] }) {
  const { type, period, params, setParam } = props
  const requested = Number(params.get('grade'))
  const grade = grades.find((item) => item === requested) ?? grades[0]
  // Danh sách lớp của khối lấy từ tổng quan khối (cùng nguồn với màn hình so sánh các lớp).
  const overview = useGradeOverview(grade, '1')
  const classes = overview.data?.classes ?? []
  const classId = classes.find((item) => item.class_id === Number(params.get('class')))?.class_id
  const target: ReportTarget =
    classId === undefined
      ? { type, semester: period, gradeLevel: grade }
      : { type, semester: period, classId }
  const scopeLabel =
    classId === undefined
      ? `khối ${grade}`
      : `lớp ${classes.find((item) => item.class_id === classId)?.name ?? ''}`

  return (
    <>
      <Toolbar {...props}>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label htmlFor="khoi" className="label">
              Khối
            </label>
            <select
              id="khoi"
              value={grade}
              onChange={(event) => setParam({ grade: event.target.value, class: null })}
              className="input mt-1"
            >
              {grades.map((item) => (
                <option key={item} value={item}>
                  Khối {item}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="lop-hoac-khoi" className="label">
              Phạm vi
            </label>
            <select
              id="lop-hoac-khoi"
              value={classId === undefined ? '' : String(classId)}
              onChange={(event) => setParam({ class: event.target.value || null })}
              className="input mt-1"
            >
              <option value="">Cả khối {grade}</option>
              {classes.map((item) => (
                <option key={item.class_id} value={item.class_id}>
                  Lớp {item.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Toolbar>
      <ReportBody
        key={`${grade}-${classId ?? 'khoi'}-${period}`}
        target={target}
        scopeLabel={scopeLabel}
        initialStudentId={null}
      />
    </>
  )
}

interface ReportBodyProps {
  target: ReportTarget
  scopeLabel: string
  initialStudentId: number | null
}

function ReportBody({ target, scopeLabel, initialStudentId }: ReportBodyProps) {
  const list = useReportList(target)
  return (
    <Panel id="ket-qua-nhan-xet" title={TYPE_LABELS[target.type]} description={scopeLabel}>
      <QueryState query={list}>
        {(result) =>
          target.type === 'report' ? (
            <AggregateReport
              target={target}
              report={result.items[0]?.report ?? null}
              scopeLabel={scopeLabel}
            />
          ) : (
            <StudentReports target={target} list={result} initialStudentId={initialStudentId} />
          )
        }
      </QueryState>
    </Panel>
  )
}
