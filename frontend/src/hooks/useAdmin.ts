import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  copyAssignments,
  createClass,
  createUser,
  deleteClass,
  fetchAdminUsers,
  fetchClassAssignments,
  fetchSchool,
  fetchTeachers,
  removeAssignment,
  removeStudent,
  resetPassword,
  saveSchoolYear,
  setAssignment,
  updateClass,
  updateUser,
} from '../api/admin'
import type { UserUpdate } from '../api/admin'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'

// Lỗi 4xx (không có quyền, không tìm thấy) không đổi khi thử lại; chỉ thử lại lỗi mạng và 5xx.
const retry = (failureCount: number, error: Error) =>
  failureCount < 1 && !(error instanceof ApiError && error.status < 500)

export function useAdminUsers() {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['admin-users', token],
    queryFn: ({ signal }) => fetchAdminUsers(signal),
    enabled: token !== null,
    retry,
  })
}

export function useSchool() {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['admin-school', token],
    queryFn: ({ signal }) => fetchSchool(signal),
    enabled: token !== null,
    retry,
  })
}

export function useTeachers() {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['admin-teachers', token],
    queryFn: ({ signal }) => fetchTeachers(signal),
    enabled: token !== null,
    retry,
  })
}

export function useClassAssignments(classId: number) {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['admin-assignments', token, classId],
    queryFn: ({ signal }) => fetchClassAssignments(classId, signal),
    enabled: token !== null && Number.isFinite(classId),
    retry,
  })
}

// Đổi tài khoản, lớp hay phân công làm các danh sách liên quan đổi (số phân công, GVCN, sĩ số), nên
// làm mới mọi truy vấn quản trị sau khi xong. Dữ liệu ít, làm mới hết cho chắc.
export function useRefreshAdmin() {
  const client = useQueryClient()
  return () =>
    Promise.all([
      client.invalidateQueries({ queryKey: ['admin-users'] }),
      client.invalidateQueries({ queryKey: ['admin-school'] }),
      client.invalidateQueries({ queryKey: ['admin-teachers'] }),
      client.invalidateQueries({ queryKey: ['admin-assignments'] }),
      // Trang chủ và thanh bên của giáo viên đọc lớp chủ nhiệm / phân công từ đây.
      client.invalidateQueries({ queryKey: ['assignments'] }),
    ])
}

export function useCreateUser() {
  const refresh = useRefreshAdmin()
  return useMutation({ mutationFn: createUser, onSuccess: refresh })
}

export function useUpdateUser() {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: UserUpdate }) => updateUser(id, body),
    onSuccess: refresh,
  })
}

export function useResetPassword() {
  return useMutation({ mutationFn: (id: number) => resetPassword(id) })
}

export function useSaveSchoolYear() {
  const refresh = useRefreshAdmin()
  return useMutation({ mutationFn: saveSchoolYear, onSuccess: refresh })
}

export function useCreateClass() {
  const refresh = useRefreshAdmin()
  return useMutation({ mutationFn: createClass, onSuccess: refresh })
}

export function useUpdateClass() {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number
      body: { name?: string; homeroom_teacher_id?: number | null }
    }) => updateClass(id, body),
    onSuccess: refresh,
  })
}

export function useDeleteClass() {
  const refresh = useRefreshAdmin()
  return useMutation({ mutationFn: (id: number) => deleteClass(id), onSuccess: refresh })
}

export function useSetAssignment(classId: number) {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: ({ subjectId, teacherId }: { subjectId: number; teacherId: number }) =>
      setAssignment(classId, subjectId, teacherId),
    onSuccess: refresh,
  })
}

export function useRemoveAssignment(classId: number) {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: (subjectId: number) => removeAssignment(classId, subjectId),
    onSuccess: refresh,
  })
}

export function useCopyAssignments(classId: number) {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: (fromClassId: number) => copyAssignments(classId, fromClassId),
    onSuccess: refresh,
  })
}

export function useRemoveStudent(classId: number) {
  const refresh = useRefreshAdmin()
  return useMutation({
    mutationFn: (code: string) => removeStudent(classId, code),
    onSuccess: refresh,
  })
}
