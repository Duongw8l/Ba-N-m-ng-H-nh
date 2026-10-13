import { useState } from 'react'
import type { ReactNode } from 'react'
import { ApiError } from '../../api/client'
import type { AuthUser } from '../../api/auth'
import { useAssignments } from '../../hooks/useAssignments'
import { Icon } from '../Icon'
import { QueryState } from '../QueryState'

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

export function ErrorAlert({ error }: { error: unknown }) {
  return (
    <p role="alert" className="rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200">
      {errorText(error)}
    </p>
  )
}

export function SuccessNote({ children }: { children: ReactNode }) {
  return (
    <p
      role="status"
      className="rounded-xl bg-green-50 p-3 text-sm text-green-800 ring-1 ring-green-200"
    >
      {children}
    </p>
  )
}

// Chỉ Admin vào được các trang quản trị. Back-end kiểm lại quyền ở mọi yêu cầu; chỗ này chỉ để người
// khác mở thẳng địa chỉ thì thấy lời báo rõ ràng thay vì một loạt lỗi 403.
export function AdminGate({ children }: { children: (admin: AuthUser) => ReactNode }) {
  const assignments = useAssignments()
  return (
    <QueryState query={assignments}>
      {(data) =>
        data.user.role !== 'admin' ? (
          <p className="card p-6 text-slate-600">Chỉ quản trị viên được dùng trang này.</p>
        ) : (
          children(data.user)
        )
      }
    </QueryState>
  )
}

interface TempPasswordNoticeProps {
  title: string
  email: string
  password: string
  onDone: () => void
}

// Mật khẩu tạm chỉ hiện một lần: back-end không lưu bản rõ và không có cách xem lại. Admin sao chép,
// đưa cho người dùng, rồi bấm "Đã ghi lại" để đóng; muốn có mật khẩu khác phải đặt lại.
export function TempPasswordNotice({ title, email, password, onDone }: TempPasswordNoticeProps) {
  const [copied, setCopied] = useState<'yes' | 'no' | null>(null)

  async function copy() {
    try {
      await navigator.clipboard.writeText(password)
      setCopied('yes')
    } catch {
      setCopied('no')
    }
  }

  return (
    <section
      aria-labelledby="mat-khau-tam"
      className="space-y-3 rounded-2xl border border-amber-300 bg-amber-50 p-5 text-amber-900"
    >
      <h2 id="mat-khau-tam" className="flex items-center gap-2 text-base font-semibold">
        <Icon name="alert" className="h-5 w-5" />
        {title}
      </h2>
      <p className="text-sm">
        Tài khoản <strong>{email}</strong>. Mật khẩu này <strong>chỉ hiện một lần</strong>, hệ thống
        không lưu bản đọc được. Hãy đưa cho người dùng và nhắc họ đổi mật khẩu ngay ở menu người
        dùng (góc trên bên phải) › Đổi mật khẩu.
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <code
          data-testid="mat-khau-tam"
          className="select-all rounded-xl bg-white px-4 py-2 font-mono text-lg tracking-wider text-slate-900 ring-1 ring-amber-300"
        >
          {password}
        </code>
        <button type="button" onClick={() => void copy()} className="btn-secondary">
          Sao chép
        </button>
        <button type="button" onClick={onDone} className="btn-primary">
          Đã ghi lại
        </button>
      </div>
      <p aria-live="polite" className="min-h-5 text-sm">
        {copied === 'yes' && 'Đã sao chép vào bộ nhớ tạm.'}
        {copied === 'no' && 'Không sao chép được tự động. Hãy bôi đen mật khẩu rồi chép tay.'}
      </p>
    </section>
  )
}
