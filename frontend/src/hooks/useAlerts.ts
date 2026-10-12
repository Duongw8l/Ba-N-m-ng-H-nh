import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchClassAlerts, fetchSchoolAlerts, updateAlert } from '../api/warning'
import type { RiskLevel, TeacherStatus } from '../api/warning'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'

function retry(failureCount: number, error: Error): boolean {
  return failureCount < 1 && !(error instanceof ApiError && error.status < 500)
}

export function useClassAlerts(classId: number, enabled = true) {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['class-alerts', token, classId],
    queryFn: ({ signal }) => fetchClassAlerts(classId, signal),
    enabled: enabled && token !== null && Number.isInteger(classId),
    retry,
  })
}

export function useSchoolAlerts(level: RiskLevel, enabled = true) {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['school-alerts', token, level],
    queryFn: ({ signal }) => fetchSchoolAlerts(level, signal),
    enabled: enabled && token !== null,
    retry,
  })
}

// Ghi nhận "đã trao đổi" / "báo nhầm": làm mới mọi nơi đang hiện cảnh báo (danh sách lớp, dashboard,
// hồ sơ, danh sách toàn trường).
export function useUpdateAlert() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ alertId, status }: { alertId: number; status: TeacherStatus }) =>
      updateAlert(alertId, status),
    onSuccess: async () => {
      await Promise.all(
        ['class-alerts', 'school-alerts', 'dashboard', 'student-profile'].map((key) =>
          client.invalidateQueries({ queryKey: [key] }),
        ),
      )
    },
  })
}
