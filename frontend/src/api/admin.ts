import { apiDelete, apiGet, apiPatch, apiPost, apiPut } from './client'
import type { UserRole } from './auth'

// Khớp schema của back-end: backend/app/auth/admin_schemas.py, backend/app/classes/admin_schemas.py.
// Chỉ Admin gọi được các endpoint này (back-end kiểm lại ở mọi yêu cầu).

export interface AdminUser {
  id: number
  email: string
  full_name: string
  role: UserRole
  role_label: string
  is_active: boolean
  homeroom_class: string | null
  assignment_count: number
}

export interface CreatedUser {
  user: AdminUser
  // Chỉ có trong phản hồi này: không thể xem lại sau đó.
  temporary_password: string
}

export interface UserUpdate {
  email?: string
  full_name?: string
  role?: UserRole
  is_active?: boolean
}

export interface TeacherRef {
  id: number
  full_name: string
}

export interface Teacher {
  id: number
  full_name: string
  email: string
  homeroom_class: string | null
}

export interface SchoolYear {
  id: number
  name: string
  start_date: string
  end_date: string
}

export interface AdminClass {
  id: number
  name: string
  grade_level: number
  homeroom_teacher: TeacherRef | null
  student_count: number
  assigned_subject_count: number
}

export interface School {
  school_year: SchoolYear | null
  classes: AdminClass[]
  subject_count: number
}

export interface AssignmentRow {
  subject_id: number
  subject_name: string
  is_elective: boolean
  assessment_type: 'score' | 'comment'
  teacher: TeacherRef | null
}

export interface ClassAssignments {
  class_id: number
  class_name: string
  grade_level: number
  subjects: AssignmentRow[]
}

export function fetchAdminUsers(signal?: AbortSignal): Promise<AdminUser[]> {
  return apiGet<AdminUser[]>('/admin/users', signal)
}

export function createUser(body: {
  email: string
  full_name: string
  role: UserRole
}): Promise<CreatedUser> {
  return apiPost<CreatedUser>('/admin/users', body)
}

export function updateUser(id: number, body: UserUpdate): Promise<AdminUser> {
  return apiPatch<AdminUser>(`/admin/users/${id}`, body)
}

export function resetPassword(id: number): Promise<{ temporary_password: string }> {
  return apiPost<{ temporary_password: string }>(`/admin/users/${id}/reset-password`, undefined)
}

export function fetchSchool(signal?: AbortSignal): Promise<School> {
  return apiGet<School>('/admin/school', signal)
}

export function fetchTeachers(signal?: AbortSignal): Promise<Teacher[]> {
  return apiGet<Teacher[]>('/admin/teachers', signal)
}

export function saveSchoolYear(body: {
  name: string
  start_date: string
  end_date: string
}): Promise<SchoolYear> {
  return apiPut<SchoolYear>('/admin/school-year', body)
}

export function createClass(body: {
  grade_level: number
  name: string
  homeroom_teacher_id: number | null
}): Promise<AdminClass> {
  return apiPost<AdminClass>('/admin/classes', body)
}

export function updateClass(
  id: number,
  body: { name?: string; homeroom_teacher_id?: number | null },
): Promise<AdminClass> {
  return apiPatch<AdminClass>(`/admin/classes/${id}`, body)
}

export function deleteClass(id: number): Promise<{ detail: string }> {
  return apiDelete<{ detail: string }>(`/admin/classes/${id}`)
}

export function fetchClassAssignments(
  classId: number,
  signal?: AbortSignal,
): Promise<ClassAssignments> {
  return apiGet<ClassAssignments>(`/admin/classes/${classId}/assignments`, signal)
}

export function setAssignment(
  classId: number,
  subjectId: number,
  teacherId: number,
): Promise<ClassAssignments> {
  return apiPut<ClassAssignments>(`/admin/classes/${classId}/assignments/${subjectId}`, {
    teacher_id: teacherId,
  })
}

export function removeAssignment(classId: number, subjectId: number): Promise<ClassAssignments> {
  return apiDelete<ClassAssignments>(`/admin/classes/${classId}/assignments/${subjectId}`)
}

export function copyAssignments(classId: number, fromClassId: number): Promise<{ copied: number }> {
  return apiPost<{ copied: number }>(`/admin/classes/${classId}/assignments/copy`, {
    from_class_id: fromClassId,
  })
}

export function removeStudent(classId: number, studentCode: string): Promise<{ detail: string }> {
  return apiPost<{ detail: string }>(`/admin/classes/${classId}/students/remove`, {
    student_code: studentCode,
  })
}
