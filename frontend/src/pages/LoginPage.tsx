import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'
import { SystemStatus } from '../components/SystemStatus'

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) return 'Hãy nhập email và mật khẩu.'
    return error.message // 401: "Email hoặc mật khẩu không đúng." do back-end trả
  }
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

export default function LoginPage() {
  const { token, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  // Đã đăng nhập (kể cả ngay sau khi đăng nhập xong) thì về trang đang định mở, mặc định là trang chủ.
  if (token !== null) {
    const from = (location.state as { from?: string } | null)?.from ?? '/'
    return <Navigate to={from} replace />
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setPending(true)
    try {
      await login(email, password)
    } catch (caught) {
      setError(loginErrorMessage(caught))
      setPending(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-900">
      <div className="mx-auto max-w-lg space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Trợ lý AI quản lý lớp học THPT</h1>
          <p className="mt-1 text-sm text-slate-500">Khối 10, 11, 12 · Đăng nhập để tiếp tục</p>
        </div>

        <form
          onSubmit={onSubmit}
          className="space-y-4 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 className="text-lg font-medium">Đăng nhập</h2>
          <label className="block text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              required
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base"
            />
          </label>
          <label className="block text-sm font-medium text-slate-700">
            Mật khẩu
            <input
              type="password"
              required
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              className="mt-1 block w-full rounded-md border border-slate-300 px-3 py-2 text-base"
            />
          </label>

          {error !== null && (
            <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-700">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={pending}
            className="w-full rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {pending ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </button>
        </form>

        <SystemStatus />
      </div>
    </main>
  )
}
