import { useState } from 'react'
import type { FormEvent } from 'react'
import type { AdminUser, CreatedUser } from '../../api/admin'
import type { UserRole } from '../../api/auth'
import { useCreateUser, useUpdateUser } from '../../hooks/useAdmin'
import { ErrorAlert } from './shared'
import { ROLE_OPTIONS } from './roles'

const EMAIL_SHAPE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/

interface CreateProps {
  mode: 'create'
  onCreated: (created: CreatedUser) => void
}

interface EditProps {
  mode: 'edit'
  user: AdminUser
  // Đang sửa chính tài khoản đăng nhập: không đổi được vai trò (back-end cũng chặn).
  isSelf: boolean
  onDone: () => void
}

// Biểu mẫu tạo tài khoản (hệ thống sinh mật khẩu tạm) hoặc sửa họ tên, email, vai trò.
export function UserForm(props: CreateProps | EditProps) {
  const editing = props.mode === 'edit' ? props.user : null
  const create = useCreateUser()
  const update = useUpdateUser()
  const [fullName, setFullName] = useState(editing?.full_name ?? '')
  const [email, setEmail] = useState(editing?.email ?? '')
  const [role, setRole] = useState<UserRole>(editing?.role ?? 'teacher')
  const mutation = props.mode === 'create' ? create : update

  const valid = fullName.trim() !== '' && EMAIL_SHAPE.test(email.trim())
  const dirty =
    editing === null ||
    fullName.trim() !== editing.full_name ||
    email.trim().toLowerCase() !== editing.email ||
    role !== editing.role

  function submit(event: FormEvent) {
    event.preventDefault()
    if (!valid || !dirty || mutation.isPending) return
    if (props.mode === 'create') {
      create.mutate(
        { email: email.trim(), full_name: fullName.trim(), role },
        {
          onSuccess: (created) => {
            setFullName('')
            setEmail('')
            setRole('teacher')
            props.onCreated(created)
          },
        },
      )
    } else {
      update.mutate(
        {
          id: props.user.id,
          body: {
            ...(fullName.trim() !== props.user.full_name ? { full_name: fullName.trim() } : {}),
            ...(email.trim().toLowerCase() !== props.user.email ? { email: email.trim() } : {}),
            ...(role !== props.user.role ? { role } : {}),
          },
        },
        { onSuccess: props.onDone },
      )
    }
  }

  const idPrefix = editing ? `sua-${editing.id}` : 'moi'
  return (
    <form onSubmit={submit} className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <div>
          <label htmlFor={`${idPrefix}-ten`} className="label">
            Họ và tên
          </label>
          <input
            id={`${idPrefix}-ten`}
            type="text"
            value={fullName}
            maxLength={100}
            disabled={mutation.isPending}
            onChange={(event) => setFullName(event.target.value)}
            className="input mt-1"
            autoComplete="off"
          />
        </div>
        <div>
          <label htmlFor={`${idPrefix}-email`} className="label">
            Email đăng nhập
          </label>
          <input
            id={`${idPrefix}-email`}
            type="email"
            value={email}
            maxLength={255}
            disabled={mutation.isPending}
            onChange={(event) => setEmail(event.target.value)}
            className="input mt-1"
            autoComplete="off"
          />
        </div>
        <div>
          <label htmlFor={`${idPrefix}-vai-tro`} className="label">
            Vai trò
          </label>
          <select
            id={`${idPrefix}-vai-tro`}
            value={role}
            disabled={mutation.isPending || (props.mode === 'edit' && props.isSelf)}
            onChange={(event) => setRole(event.target.value as UserRole)}
            className="input mt-1"
          >
            {ROLE_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
          {props.mode === 'edit' && props.isSelf && (
            <p className="mt-1 text-xs text-slate-500">Không đổi được vai trò của chính mình.</p>
          )}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-3">
        <button type="submit" disabled={!valid || !dirty || mutation.isPending} className="btn-primary">
          {props.mode === 'create'
            ? mutation.isPending
              ? 'Đang tạo…'
              : 'Tạo tài khoản'
            : mutation.isPending
              ? 'Đang lưu…'
              : 'Lưu thay đổi'}
        </button>
        {props.mode === 'edit' && (
          <button type="button" onClick={props.onDone} className="btn-secondary">
            Huỷ
          </button>
        )}
        {props.mode === 'create' && (
          <p className="text-sm text-slate-500">
            Hệ thống tự sinh mật khẩu tạm và chỉ hiện cho bạn một lần.
          </p>
        )}
      </div>
      {mutation.isError && <ErrorAlert error={mutation.error} />}
    </form>
  )
}
