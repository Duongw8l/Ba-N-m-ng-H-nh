import { useMemo, useState } from 'react'
import type { AdminUser } from '../../api/admin'
import type { UserRole } from '../../api/auth'
import { useResetPassword, useUpdateUser } from '../../hooks/useAdmin'
import { ErrorAlert } from './shared'
import { ROLE_OPTIONS } from './roles'

type Action = { userId: number; kind: 'lock' | 'unlock' | 'reset' }

interface UserTableProps {
  users: AdminUser[]
  selfId: number
  onEdit: (user: AdminUser) => void
  onPasswordIssued: (user: AdminUser, password: string) => void
}

function dutiesText(user: AdminUser): string {
  if (user.role !== 'teacher') return '—'
  const parts: string[] = []
  if (user.homeroom_class) parts.push(`Chủ nhiệm ${user.homeroom_class}`)
  if (user.assignment_count > 0) parts.push(`${user.assignment_count} lớp–môn`)
  return parts.length > 0 ? parts.join(', ') : 'Chưa phân công'
}

// Danh sách tài khoản với bộ lọc. Khoá và đặt lại mật khẩu cần xác nhận ngay trên dòng.
export function UserTable({ users, selfId, onEdit, onPasswordIssued }: UserTableProps) {
  const update = useUpdateUser()
  const reset = useResetPassword()
  const [text, setText] = useState('')
  const [role, setRole] = useState<UserRole | ''>('')
  const [status, setStatus] = useState<'' | 'active' | 'locked'>('')
  const [action, setAction] = useState<Action | null>(null)

  const shown = useMemo(() => {
    const needle = text.trim().toLowerCase()
    return users.filter(
      (user) =>
        (role === '' || user.role === role) &&
        (status === '' || user.is_active === (status === 'active')) &&
        (needle === '' ||
          user.full_name.toLowerCase().includes(needle) ||
          user.email.toLowerCase().includes(needle)),
    )
  }, [users, text, role, status])

  const busy = update.isPending || reset.isPending
  const error = update.error ?? reset.error

  function run(user: AdminUser, current: Action) {
    if (current.kind === 'reset') {
      reset.mutate(user.id, {
        onSuccess: (data) => {
          setAction(null)
          onPasswordIssued(user, data.temporary_password)
        },
      })
    } else {
      update.mutate(
        { id: user.id, body: { is_active: current.kind === 'unlock' } },
        { onSuccess: () => setAction(null) },
      )
    }
  }

  function ask(user: AdminUser, kind: Action['kind']) {
    update.reset()
    reset.reset()
    setAction({ userId: user.id, kind })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-3 sm:grid-cols-3">
        <div>
          <label htmlFor="loc-ten" className="label">
            Tìm theo tên hoặc email
          </label>
          <input
            id="loc-ten"
            type="search"
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="input mt-1"
          />
        </div>
        <div>
          <label htmlFor="loc-vai-tro" className="label">
            Vai trò
          </label>
          <select
            id="loc-vai-tro"
            value={role}
            onChange={(event) => setRole(event.target.value as UserRole | '')}
            className="input mt-1"
          >
            <option value="">Tất cả</option>
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="loc-trang-thai" className="label">
            Trạng thái
          </label>
          <select
            id="loc-trang-thai"
            value={status}
            onChange={(event) => setStatus(event.target.value as '' | 'active' | 'locked')}
            className="input mt-1"
          >
            <option value="">Tất cả</option>
            <option value="active">Đang hoạt động</option>
            <option value="locked">Bị khoá</option>
          </select>
        </div>
      </div>

      <p aria-live="polite" className="text-sm text-slate-500">
        Hiện {shown.length} / {users.length} tài khoản.
      </p>

      <div className="overflow-x-auto">
        <table className="data-table min-w-max">
          <thead>
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">
                Người dùng
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Vai trò
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Công việc
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Trạng thái
              </th>
              <th scope="col" className="py-2 pl-3 font-medium">
                <span className="sr-only">Thao tác</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {shown.map((user) => {
              const confirming = action?.userId === user.id ? action : null
              const self = user.id === selfId
              return (
                <tr key={user.id}>
                  <th scope="row" className="py-2 pr-4 text-left font-normal">
                    <span className="block font-medium">
                      {user.full_name}
                      {self && <span className="ml-2 text-xs font-normal text-slate-500">(bạn)</span>}
                    </span>
                    <span className="block text-xs text-slate-500">{user.email}</span>
                  </th>
                  <td className="px-3 py-2">{user.role_label}</td>
                  <td className="px-3 py-2">{dutiesText(user)}</td>
                  <td className="px-3 py-2">
                    <span className={user.is_active ? 'badge-good' : 'badge-fail'}>
                      {user.is_active ? 'Hoạt động' : 'Bị khoá'}
                    </span>
                  </td>
                  <td className="py-2 pl-3">
                    {confirming ? (
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="max-w-xs text-xs text-slate-600">
                          {confirming.kind === 'reset' &&
                            'Mật khẩu hiện tại sẽ không dùng được nữa. Mật khẩu mới chỉ hiện một lần.'}
                          {confirming.kind === 'lock' &&
                            `Người này sẽ bị đăng xuất ngay và không đăng nhập được.${
                              user.assignment_count > 0 || user.homeroom_class
                                ? ' Họ còn phân công; hãy giao lại cho giáo viên khác.'
                                : ''
                            }`}
                          {confirming.kind === 'unlock' && 'Người này sẽ đăng nhập lại được.'}
                        </span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => run(user, confirming)}
                          className="btn-primary btn-sm"
                        >
                          {busy ? 'Đang lưu…' : 'Xác nhận'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setAction(null)}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Huỷ
                        </button>
                      </span>
                    ) : (
                      <span className="flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => onEdit(user)}
                          aria-label={`Sửa ${user.full_name}`}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Sửa
                        </button>
                        <button
                          type="button"
                          onClick={() => ask(user, 'reset')}
                          aria-label={`Đặt lại mật khẩu của ${user.full_name}`}
                          className="btn-secondary px-3 py-1.5"
                        >
                          Đặt lại mật khẩu
                        </button>
                        {user.is_active ? (
                          <button
                            type="button"
                            disabled={self}
                            title={self ? 'Không thể khoá chính mình' : undefined}
                            onClick={() => ask(user, 'lock')}
                            aria-label={`Khoá ${user.full_name}`}
                            className="btn-secondary px-3 py-1.5"
                          >
                            Khoá
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => ask(user, 'unlock')}
                            aria-label={`Mở khoá ${user.full_name}`}
                            className="btn-secondary px-3 py-1.5"
                          >
                            Mở khoá
                          </button>
                        )}
                      </span>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {shown.length === 0 && (
        <p className="text-sm text-slate-600">Không có tài khoản nào khớp bộ lọc.</p>
      )}
      {error && <ErrorAlert error={error} />}
    </div>
  )
}
