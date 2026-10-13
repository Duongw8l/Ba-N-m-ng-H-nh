import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  fetchReports,
  generateReport,
  regenerateReport,
  startClassJob,
  updateReport,
} from '../api/reports'
import type { ReportTarget } from '../api/reports'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'

const retry = (failureCount: number, error: Error) =>
  failureCount < 1 && !(error instanceof ApiError && error.status < 500)

const POLL_MS = 2500

// Danh sách bản của một lớp (hoặc báo cáo lớp / khối). Khi đang sinh cả lớp thì hỏi lại định kỳ để
// thanh tiến độ và từng dòng cập nhật; xong hoặc dừng thì thôi.
export function useReportList(target: ReportTarget | null) {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['reports', token, target],
    queryFn: ({ signal }) => {
      if (target === null) throw new Error('Chưa chọn phạm vi.')
      return fetchReports(target, signal)
    },
    enabled: token !== null && target !== null,
    refetchInterval: (query) => (query.state.data?.job?.status === 'running' ? POLL_MS : false),
    retry,
  })
}

function useRefreshReports() {
  const client = useQueryClient()
  return () => client.invalidateQueries({ queryKey: ['reports'] })
}

export function useGenerateReport(target: ReportTarget) {
  const refresh = useRefreshReports()
  return useMutation({
    mutationFn: (options: { studentId?: number; feedback?: string }) =>
      generateReport(target, options),
    onSuccess: refresh,
  })
}

export function useStartClassJob(target: ReportTarget) {
  const refresh = useRefreshReports()
  return useMutation({ mutationFn: () => startClassJob(target), onSuccess: refresh })
}

export function useUpdateReport() {
  const refresh = useRefreshReports()
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: { text?: string; approve?: boolean } }) =>
      updateReport(id, body),
    onSuccess: refresh,
  })
}

export function useRegenerateReport() {
  const refresh = useRefreshReports()
  return useMutation({
    mutationFn: ({ id, feedback }: { id: number; feedback?: string }) =>
      regenerateReport(id, feedback),
    onSuccess: refresh,
  })
}
