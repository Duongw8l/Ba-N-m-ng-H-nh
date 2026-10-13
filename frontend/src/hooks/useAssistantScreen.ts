import { matchPath, useLocation, useSearchParams } from 'react-router-dom'
import type { AssistantScreen } from '../api/assistant'
import type { Period } from '../api/analytics'

// Các màn hình có lớp (và môn) đang mở. Khung chat nằm trong AppLayout, ngoài các route con, nên
// không dùng được useParams: so khớp đường dẫn hiện tại.
const CLASS_PATTERNS = [
  '/classes/:classId/subjects/:subjectId',
  '/classes/:classId/students/:studentId',
  '/classes/:classId/import',
  '/classes/:classId',
] as const

const PERIODS: readonly Period[] = ['1', '2', 'year']

function toId(raw: string | undefined): number | null {
  if (raw === undefined || !/^\d+$/.test(raw)) return null
  return Number(raw)
}

// Lớp, môn và kỳ của màn hình đang mở (DESIGN mục 8: trợ lý tự biết người dùng đang xem gì).
export function useAssistantScreen(): AssistantScreen {
  const { pathname } = useLocation()
  const [params] = useSearchParams()

  let classId: number | null = null
  let subjectId: number | null = null
  for (const pattern of CLASS_PATTERNS) {
    const match = matchPath({ path: pattern, end: true }, pathname)
    if (match) {
      const found: Record<string, string | undefined> = match.params
      classId = toId(found.classId)
      subjectId = toId(found.subjectId)
      break
    }
  }
  const raw = params.get('semester')
  const semester = PERIODS.find((item) => item === raw) ?? '1'
  return { classId, subjectId, semester }
}
