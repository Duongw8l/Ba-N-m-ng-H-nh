import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-900">
      <div className="mx-auto max-w-lg">
        <h1 className="text-2xl font-semibold">Không tìm thấy trang</h1>
        <p className="mt-2 text-slate-600">Địa chỉ bạn mở không tồn tại.</p>
        <Link to="/" className="mt-4 inline-block text-blue-700 underline">
          Về trang chủ
        </Link>
      </div>
    </main>
  )
}
