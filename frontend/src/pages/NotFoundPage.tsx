import { Link } from 'react-router-dom'
import { Icon } from '../components/Icon'
import { LogoMark } from '../components/Logo'

export default function NotFoundPage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-5 py-12">
      <div className="w-full max-w-md text-center">
        <LogoMark className="mx-auto h-12 w-12" />
        <p
          aria-hidden="true"
          className="mt-8 bg-linear-to-br from-brand-400 to-brand-700 bg-clip-text text-7xl font-bold tracking-tight text-transparent"
        >
          404
        </p>
        <h1 className="mt-2 text-2xl font-semibold tracking-tight">Không tìm thấy trang</h1>
        <p className="mt-2 text-slate-600">Địa chỉ bạn mở không tồn tại.</p>
        <Link to="/" className="btn-primary mt-6">
          <Icon name="home" className="h-4 w-4" />
          Về trang chủ
        </Link>
      </div>
    </main>
  )
}
