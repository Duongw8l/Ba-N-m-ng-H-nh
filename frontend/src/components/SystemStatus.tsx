import { useHealth } from '../hooks/useHealth'
import { StatusRow } from './StatusRow'
import type { StatusState } from './StatusRow'

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

// Trạng thái máy chủ và cơ sở dữ liệu (GET /health, công khai nên xem được cả khi chưa đăng nhập).
export function SystemStatus() {
  const health = useHealth()
  const states = resolveStates(health)
  const dbDown = health.isSuccess && !health.data.db

  return (
    <section
      aria-labelledby="trang-thai-he-thong"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
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
  )
}
