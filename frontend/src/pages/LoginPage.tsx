import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'
import { Icon } from '../components/Icon'
import type { IconName } from '../components/Icon'
import { Logo } from '../components/Logo'
import { SystemStatus } from '../components/SystemStatus'
import { ThemeToggle } from '../components/layout/ThemeToggle'

function loginErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 422) return 'Hãy nhập email và mật khẩu.'
    return error.message // 401: "Email hoặc mật khẩu không đúng." do back-end trả
  }
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

const HIGHLIGHTS: { icon: IconName; title: string; text: string }[] = [
  {
    icon: 'bell',
    title: 'Cảnh báo sớm có lý do rõ ràng',
    text: 'Luật Thông tư 22 cùng mô hình dự báo; giáo viên là người quyết định.',
  },
  {
    icon: 'sparkles',
    title: 'Trợ lý AI luôn kèm nguồn',
    text: 'Mọi con số do hệ thống tính, mỗi câu trả lời có mục Nguồn để kiểm tra.',
  },
  {
    icon: 'shield',
    title: 'Họ tên học sinh được ẩn danh',
    text: 'AI chỉ nhận mã tạm, không nhận ngày sinh hay thông tin phụ huynh.',
  },
]

export default function LoginPage() {
  const { token, login } = useAuth()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
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
    <main className="grid min-h-screen lg:grid-cols-[1.05fr_1fr]">
      <section className="relative hidden overflow-hidden bg-linear-to-br from-brand-900 via-brand-800 to-brand-600 p-12 text-white lg:flex lg:flex-col lg:justify-between">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -top-24 -right-24 h-96 w-96 rounded-full bg-brand-300/20 blur-3xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-32 -left-20 h-96 w-96 rounded-full bg-brand-950/40 blur-3xl"
        />
        <Logo className="relative" />
        <div className="relative max-w-lg">
          <p className="text-sm font-medium tracking-wider text-brand-200 uppercase">
            Khối 10 · 11 · 12
          </p>
          <h2 className="mt-3 text-4xl leading-tight font-semibold tracking-tight">
            Theo dõi học tập, chuyên cần và rèn luyện, sớm hơn một bước.
          </h2>
          <ul className="mt-10 space-y-6">
            {HIGHLIGHTS.map((item) => (
              <li key={item.title} className="flex gap-4">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white/12 ring-1 ring-white/15">
                  <Icon name={item.icon} className="h-5 w-5 text-brand-100" />
                </span>
                <span>
                  <span className="block font-semibold">{item.title}</span>
                  <span className="mt-0.5 block text-sm text-brand-100/80">{item.text}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>
        <p className="relative text-xs text-brand-200/70">
          Bản demo chỉ dùng dữ liệu giả lập.
        </p>
      </section>

      <section className="relative flex flex-col items-center justify-center px-5 py-10 sm:px-8">
        <div className="absolute top-4 right-4">
          <ThemeToggle />
        </div>
        <div className="w-full max-w-md space-y-6">
          <div className="lg:hidden">
            <Logo />
          </div>
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Trợ lý AI quản lý lớp học THPT</h1>
            <p className="mt-1 text-sm text-slate-500">Khối 10, 11, 12 · Đăng nhập để tiếp tục</p>
          </div>

          <form onSubmit={onSubmit} className="card space-y-4 p-6">
            <h2 className="text-lg font-semibold">Đăng nhập</h2>
            <label className="label">
              Email
              <span className="relative mt-1.5 block">
                <Icon
                  name="mail"
                  className="pointer-events-none absolute top-1/2 left-3 h-5 w-5 -translate-y-1/2 text-slate-400"
                />
                <input
                  type="email"
                  required
                  autoComplete="username"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="ten@truong.edu.vn"
                  className="input pl-10"
                />
              </span>
            </label>
            <label className="label">
              Mật khẩu
              <span className="relative mt-1.5 block">
                <Icon
                  name="lock"
                  className="pointer-events-none absolute top-1/2 left-3 h-5 w-5 -translate-y-1/2 text-slate-400"
                />
                <input
                  type={showPassword ? 'text' : 'password'}
                  required
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="input pr-11 pl-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-pressed={showPassword}
                  aria-label={showPassword ? 'Ẩn ký tự đã nhập' : 'Hiện ký tự đã nhập'}
                  className="absolute top-1/2 right-2 -translate-y-1/2 rounded-lg p-1.5 text-slate-400 hover:text-slate-700"
                >
                  <Icon name={showPassword ? 'eye-off' : 'eye'} className="h-5 w-5" />
                </button>
              </span>
            </label>

            {error !== null && (
              <p
                role="alert"
                className="flex items-start gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200"
              >
                <Icon name="alert" className="mt-0.5 h-4 w-4" />
                {error}
              </p>
            )}

            <button type="submit" disabled={pending} className="btn-primary w-full py-2.5 text-base">
              {pending ? 'Đang đăng nhập…' : 'Đăng nhập'}
            </button>
          </form>

          <SystemStatus />
        </div>
      </section>
    </main>
  )
}
