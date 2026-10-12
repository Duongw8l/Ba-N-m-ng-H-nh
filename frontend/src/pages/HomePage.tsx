import { StatusRow } from '../components/StatusRow'
import type { StatusState } from '../components/StatusRow'
import { useHealth } from '../hooks/useHealth'

interface HealthStates {
  server: StatusState
  db: StatusState
}

function resolveStates(health: ReturnType<typeof useHealth>): HealthStates {
  if (health.isPending) return { server: 'loading', db: 'loading' }
  // Không gọi được API thì cũng không biết tình trạng DB.
  if (health.isError) return { server: 'error', db: 'unknown' }
  return { server: 'ok', db: health.data.db ? 'ok' : 'error' }
}

export default function HomePage() {
  const health = useHealth()
  const states = resolveStates(health)
  const dbDown = health.isSuccess && !health.data.db

  return (
    <main className="min-h-screen bg-slate-50 px-4 py-12 text-slate-900">
      <div className="mx-auto max-w-lg">
        <h1 className="text-2xl font-semibold">Trợ lý AI quản lý lớp học THPT</h1>
        <p className="mt-1 text-sm text-slate-500">Khối 10, 11, 12 · Giai đoạn 0: bộ khung dự án</p>

        <section
          aria-labelledby="trang-thai-he-thong"
          className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
        >
          <h2 id="trang-thai-he-thong" className="text-lg font-medium">
            Trạng thái hệ thống
          </h2>
          <ul className="mt-2 divide-y divide-slate-100" aria-live="polite">
            <StatusRow label="Máy chủ" state={states.server} />
            <StatusRow label="Cơ sở dữ liệu" state={states.db} />
          </ul>

          {health.isError && (
            <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa (make up hoặc make
              dev-be).
            </p>
          )}
          {dbDown && (
            <p role="alert" className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">
              Máy chủ đang chạy nhưng không kết nối được cơ sở dữ liệu. Hãy kiểm tra PostgreSQL (make
              db) và biến DATABASE_URL.
            </p>
          )}
        </section>
      </div>
    </main>
  )
}
