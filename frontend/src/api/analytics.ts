import type { ClassRef } from './auth'
import { apiGet } from './client'

// Khớp schema của back-end (backend/app/analytics/schemas.py). Điểm là số thực trong JSON; giao diện
// chỉ định dạng (lib/format.ts), không tính lại.
export type Period = '1' | '2' | 'year'
export type AssessmentType = 'score' | 'comment'
export type CommentResult = 'pass' | 'fail'

export interface Thresholds {
  fail: number
  passing: number
  fair: number
  good: number
}

export interface MonthAbsence {
  month: string // YYYY-MM
  excused: number
  unexcused: number
  total: number
}

export interface AbsenceLimits {
  notice: number
  maximum: number
}

// --- Dashboard lớp ---

export interface SubjectStat {
  subject_id: number
  name: string
  assessment_type: AssessmentType
  student_count: number
  mean: number | null
  below_pass: number
  below_fail: number
  comment_fail: number
  incomplete: number
}

export interface Attention {
  student_id: number
  student_code: string
  full_name: string
  absent_sessions: number
  reasons: string[]
}

export interface Dashboard {
  class_info: ClassRef
  period: Period
  student_count: number
  learning_levels: Record<string, number>
  conduct_levels: Record<string, number>
  conduct_derived_count: number
  absent_notice_students: number
  absent_over_limit_students: number
  subjects: SubjectStat[]
  attention: Attention[]
  promotion: { eligible: number; not_eligible: number; unknown: number } | null
  absences_by_month: MonthAbsence[]
  absence_limits: AbsenceLimits
  thresholds: Thresholds
}

// --- Bảng điểm môn ---

export interface ScoreRow {
  student_id: number
  student_code: string
  full_name: string
  tx: number[]
  tx_missing: number
  midterm: number | null
  final: number | null
  average: number | null
  comment_result: CommentResult | null
  complete: boolean
  average_semester1: number | null
  average_semester2: number | null
  year_average: number | null
}

export interface SubjectScores {
  class_info: ClassRef
  subject: {
    id: number
    name: string
    assessment_type: AssessmentType
    periods_per_year: number
    regular_required: number
  }
  semester: number
  thresholds: Thresholds
  student_count: number
  mean: number | null
  distribution: {
    below_fail: number
    fail_to_pass: number
    pass_to_fair: number
    fair_to_good: number
    at_least_good: number
  }
  incomplete_count: number
  comment_fail_count: number
  rows: ScoreRow[]
}

// --- Tổng quan khối ---

export interface ClassOverview {
  class_id: number
  name: string
  student_count: number
  learning_levels: Record<string, number>
  conduct_levels: Record<string, number>
  absent_notice_students: number
  absent_over_limit_students: number
  below_fail_students: number
}

export interface GradeOverview {
  grade_level: number
  period: Period
  classes: ClassOverview[]
  common_subjects: {
    subject_id: number
    name: string
    class_means: { class_id: number; mean: number | null }[]
  }[]
}

// --- Hồ sơ học sinh ---

export interface ProfileSemester {
  semester: number
  tx: number[]
  tx_missing: number
  midterm: number | null
  final: number | null
  average: number | null
  comment_result: CommentResult | null
  complete: boolean
}

export interface ProfileSubject {
  subject_id: number
  name: string
  assessment_type: AssessmentType
  periods_per_year: number
  regular_required: number
  semesters: ProfileSemester[]
  year_average: number | null
  year_comment_result: CommentResult | null
}

interface ProfileBase {
  class_info: ClassRef
  student: { id: number; student_code: string; full_name: string }
  subjects: ProfileSubject[]
  thresholds: Thresholds
}

export interface StudentProfileFull extends ProfileBase {
  scope: 'full'
  period: Period
  guardian_name: string | null
  guardian_phone: string | null
  learning: {
    level: string | null
    base_level: string | null
    adjusted: boolean
    incomplete_subjects: string[]
    below_fail_subjects: string[]
    below_pass_subjects: string[]
    failed_comment_subjects: string[]
  }
  conduct: { level: string | null; derived: boolean }
  attendance: {
    excused: number
    unexcused: number
    late: number
    absent_total: number
    limits: AbsenceLimits
    by_month: MonthAbsence[]
  }
  promotion: {
    eligible: boolean | null
    reasons: string[]
    retake_subjects: { subject_id: number; name: string; reason: string }[]
  } | null
  attention_reasons: string[]
}

// GVBM nhận hồ sơ không có các khoá phụ huynh, chuyên cần, rèn luyện, xếp loại (không phải khoá rỗng).
export interface StudentProfileSubjects extends ProfileBase {
  scope: 'subjects'
}

export type StudentProfile = StudentProfileFull | StudentProfileSubjects

export function fetchDashboard(classId: number, period: Period, signal?: AbortSignal) {
  return apiGet<Dashboard>(`/classes/${classId}/dashboard?semester=${period}`, signal)
}

export function fetchSubjectScores(
  classId: number,
  subjectId: number,
  semester: 1 | 2,
  signal?: AbortSignal,
) {
  return apiGet<SubjectScores>(
    `/classes/${classId}/subjects/${subjectId}/scores?semester=${semester}`,
    signal,
  )
}

export function fetchGradeOverview(level: number, period: Period, signal?: AbortSignal) {
  return apiGet<GradeOverview>(`/grades/${level}/overview?semester=${period}`, signal)
}

export function fetchStudentProfile(
  classId: number,
  studentId: number,
  period: Period,
  signal?: AbortSignal,
) {
  return apiGet<StudentProfile>(
    `/classes/${classId}/students/${studentId}/profile?semester=${period}`,
    signal,
  )
}
