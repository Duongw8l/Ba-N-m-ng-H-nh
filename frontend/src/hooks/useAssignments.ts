import { useQuery } from '@tanstack/react-query'
import { fetchAssignments } from '../api/auth'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'

export function useAssignments() {
  const { token } = useAuth()
  return useQuery({
    // Token nằm trong khoá để dữ liệu của hai người dùng không bao giờ dùng chung một bộ nhớ đệm.
    queryKey: ['assignments', token],
    queryFn: ({ signal }) => fetchAssignments(signal),
    enabled: token !== null,
    // Lỗi 4xx (hết phiên, bị từ chối) không đổi khi thử lại; chỉ thử lại lỗi mạng và 5xx.
    retry: (failureCount, error) =>
      failureCount < 1 && !(error instanceof ApiError && error.status < 500),
  })
}
