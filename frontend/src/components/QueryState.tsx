import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'
import { Icon } from './Icon'

function errorMessage(error: unknown): { text: string; retryable: boolean } {
  if (error instanceof ApiError) {
    if (error.status === 403) return { text: 'Bạn không có quyền xem trang này.', retryable: false }
    if (error.status === 404) return { text: 'Không tìm thấy dữ liệu này.', retryable: false }
    if (error.status === 422) return { text: 'Địa chỉ trang không hợp lệ.', retryable: false }
  }
  return { text: 'Không tải được dữ liệu. Hãy thử lại.', retryable: true }
}

interface QueryStateProps<T> {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
}

// Khung xương khi đang tải: vài khối mờ có dạng ô số liệu và bảng, thay cho chữ "Đang tải…".
function Loading() {
  return (
    <div aria-live="polite" aria-busy="true" className="space-y-4">
      <span className="sr-only">Đang tải…</span>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="skeleton h-28 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton h-64 rounded-2xl" />
    </div>
  )
}

// Trạng thái tải và lỗi dùng chung: đang tải, lỗi (có thử lại khi là lỗi mạng hoặc máy chủ), không
// có quyền hoặc không có dữ liệu (không thử lại vì kết quả không đổi), còn lại là nội dung.
export function QueryState<T>({ query, children }: QueryStateProps<T>) {
  if (query.isPending) return <Loading />
  if (query.isError) {
    const { text, retryable } = errorMessage(query.error)
    return (
      <div
        role="alert"
        className="flex flex-col items-start gap-3 rounded-2xl bg-red-50 p-5 text-red-800 ring-1 ring-red-200"
      >
        <p className="flex items-center gap-2 font-medium">
          <Icon name="alert" className="h-5 w-5" />
          {text}
        </p>
        {retryable && (
          <button type="button" onClick={() => void query.refetch()} className="btn-primary">
            Thử lại
          </button>
        )}
      </div>
    )
  }
  return <>{children(query.data)}</>
}
