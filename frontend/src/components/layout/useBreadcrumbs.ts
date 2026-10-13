import { matchPath, useLocation } from 'react-router-dom'
import type { Assignments } from '../../api/auth'

export interface Crumb {
  label: string
  to?: string
}

// Đường dẫn ngắn ở thanh trên (Trang chủ, Lớp 11A2 › Bảng điểm...). Tên lớp lấy từ phân công của
// người dùng; BGH xem lớp ngoài phân công thì ghi "Lớp" (tiêu đề trang vẫn có tên lớp đầy đủ).
export function useBreadcrumbs(data: Assignments | undefined): Crumb[] {
  const { pathname } = useLocation()
  const home: Crumb = { label: 'Trang chủ', to: '/' }

  function classCrumb(id: string | undefined): Crumb {
    const numeric = Number(id)
    const name =
      data?.homeroom_classes.find((c) => c.id === numeric)?.name ??
      data?.teaching.find((t) => t.class_id === numeric)?.class_name
    return { label: name ? `Lớp ${name}` : 'Lớp', to: `/classes/${id}` }
  }

  const at = (pattern: string) => matchPath({ path: pattern, end: true }, pathname)
  let m = at('/classes/:classId/subjects/:subjectId')
  if (m) return [home, classCrumb(m.params.classId), { label: 'Bảng điểm' }]
  m = at('/classes/:classId/students/:studentId')
  if (m) return [home, classCrumb(m.params.classId), { label: 'Hồ sơ học sinh' }]
  m = at('/classes/:classId/import')
  if (m) return [home, classCrumb(m.params.classId), { label: 'Nhập dữ liệu' }]
  m = at('/classes/:classId')
  if (m) return [home, { label: classCrumb(m.params.classId).label }]
  m = at('/grades/:level')
  if (m) return [home, { label: `Khối ${m.params.level}` }]
  if (at('/assistant')) return [home, { label: 'Trợ lý AI' }]
  if (at('/reports')) return [home, { label: 'Nhận xét & báo cáo' }]
  if (at('/admin/regulations')) return [home, { label: 'Quản trị' }, { label: 'Văn bản quy định' }]
  if (at('/admin/users')) return [home, { label: 'Quản trị' }, { label: 'Tài khoản' }]
  if (at('/admin/school')) return [home, { label: 'Quản trị' }, { label: 'Năm học & lớp' }]
  m = at('/admin/classes/:classId')
  if (m) {
    return [home, { label: 'Quản trị' }, { label: 'Năm học & lớp', to: '/admin/school' }, { label: 'Quản lý lớp' }]
  }
  if (at('/account/password')) return [home, { label: 'Đổi mật khẩu' }]
  return [{ label: 'Trang chủ' }]
}
