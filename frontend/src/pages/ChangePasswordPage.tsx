import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import type { FormEvent } from 'react'
import { changePassword } from '../api/auth'
import { ErrorAlert, SuccessNote } from '../components/admin/shared'
import { PageTitle, Panel } from '../components/Panel'

const MIN_LENGTH = 8

// Đổi mật khẩu của chính mình, cho mọi vai trò (D-097). Back-end kiểm mật khẩu hiện tại, độ dài tối
// thiểu 8 ký tự (tối đa 72 byte) và mật khẩu mới phải khác mật khẩu cũ.
export default function ChangePasswordPage() {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [repeat, setRepeat] = useState('')
  const mutation = useMutation({
    mutationFn: () => changePassword(current, next),
    onSuccess: () => {
      setCurrent('')
      setNext('')
      setRepeat('')
    },
  })

  const tooShort = next !== '' && next.length < MIN_LENGTH
  const mismatch = repeat !== '' && repeat !== next
  const canSubmit =
    current !== '' && next.length >= MIN_LENGTH && repeat === next && !mutation.isPending

  function submit(event: FormEvent) {
    event.preventDefault()
    if (canSubmit) mutation.mutate()
  }

  return (
    <>
      <PageTitle title="Đổi mật khẩu" />
      <Panel
        id="doi-mat-khau"
        title="Mật khẩu của bạn"
        description="Dùng mật khẩu dài, khó đoán và không dùng lại ở nơi khác."
      >
        <form onSubmit={submit} className="max-w-md space-y-4">
          <div>
            <label htmlFor="mat-khau-hien-tai" className="label">
              Mật khẩu hiện tại
            </label>
            <input
              id="mat-khau-hien-tai"
              type="password"
              value={current}
              autoComplete="current-password"
              disabled={mutation.isPending}
              onChange={(event) => {
                setCurrent(event.target.value)
                mutation.reset()
              }}
              className="input mt-1"
            />
          </div>
          <div>
            <label htmlFor="mat-khau-moi" className="label">
              Mật khẩu mới
            </label>
            <input
              id="mat-khau-moi"
              type="password"
              value={next}
              autoComplete="new-password"
              aria-describedby="mat-khau-moi-ghi-chu"
              disabled={mutation.isPending}
              onChange={(event) => {
                setNext(event.target.value)
                mutation.reset()
              }}
              className="input mt-1"
            />
            <p
              id="mat-khau-moi-ghi-chu"
              className={`mt-1 text-xs ${tooShort ? 'text-red-700' : 'text-slate-500'}`}
            >
              Tối thiểu {MIN_LENGTH} ký tự.
            </p>
          </div>
          <div>
            <label htmlFor="nhap-lai-mat-khau" className="label">
              Nhập lại mật khẩu mới
            </label>
            <input
              id="nhap-lai-mat-khau"
              type="password"
              value={repeat}
              autoComplete="new-password"
              disabled={mutation.isPending}
              onChange={(event) => {
                setRepeat(event.target.value)
                mutation.reset()
              }}
              className="input mt-1"
            />
            {mismatch && (
              <p className="mt-1 text-xs text-red-700">Hai lần nhập chưa giống nhau.</p>
            )}
          </div>
          <button type="submit" disabled={!canSubmit} className="btn-primary">
            {mutation.isPending ? 'Đang lưu…' : 'Đổi mật khẩu'}
          </button>
          {mutation.isSuccess && <SuccessNote>Đã đổi mật khẩu.</SuccessNote>}
          {mutation.isError && <ErrorAlert error={mutation.error} />}
        </form>
      </Panel>
    </>
  )
}
