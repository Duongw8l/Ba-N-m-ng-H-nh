import { Icon } from './Icon'
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
      className="rounded-2xl border border-slate-200 bg-surface/70 px-5 py-4"
    >
      <h2 id="trang-thai-he-thong" className="text-sm font-semibold text-slate-700">
        Trạng thái hệ thống
      </h2>
      <ul className="mt-1 divide-y divide-slate-100 text-sm" aria-live="polite">
        <StatusRow label="Máy chủ" state={states.server} />
        <StatusRow label="Cơ sở dữ liệu" state={states.db} />
      </ul>

      {health.isError && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200"
        >
          <Icon name="alert" className="mt-0.5 h-4 w-4" />
          Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa (make up hoặc make
          dev-be).
        </p>
      )}
      {dbDown && (
        <p
          role="alert"
          className="mt-3 flex items-start gap-2 rounded-xl bg-red-50 p-3 text-sm text-red-800 ring-1 ring-red-200"
        >
          <Icon name="alert" className="mt-0.5 h-4 w-4" />
          Máy chủ đang chạy nhưng không kết nối được cơ sở dữ liệu. Hãy kiểm tra PostgreSQL (make
          db) và biến DATABASE_URL.
        </p>
      )}
    </section>
  )
}
