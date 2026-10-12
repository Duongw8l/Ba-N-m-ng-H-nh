import type { UseQueryResult } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { ApiError } from '../api/client'

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

// Trạng thái tải và lỗi dùng chung: đang tải, lỗi (có thử lại khi là lỗi mạng hoặc máy chủ), không
// có quyền hoặc không có dữ liệu (không thử lại vì kết quả không đổi), còn lại là nội dung.
export function QueryState<T>({ query, children }: QueryStateProps<T>) {
  if (query.isPending) {
    return (
      <p aria-live="polite" className="py-6 text-slate-600">
        Đang tải…
      </p>
    )
  }
  if (query.isError) {
    const { text, retryable } = errorMessage(query.error)
    return (
      <div role="alert" className="space-y-3 rounded-md bg-red-50 p-4 text-red-800">
        <p>{text}</p>
        {retryable && (
          <button
            type="button"
            onClick={() => void query.refetch()}
            className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800"
          >
            Thử lại
          </button>
        )}
      </div>
    )
  }
  return <>{children(query.data)}</>
}
