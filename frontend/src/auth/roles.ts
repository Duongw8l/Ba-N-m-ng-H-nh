import type { Assignments } from '../api/auth'

// Vai trò hiển thị cho người dùng. Giáo viên chủ nhiệm hay bộ môn không phải một cột của tài khoản
// mà suy ra từ phân công (DESIGN mục 2), nên lấy từ /me/assignments.
export function describeRole(data: Assignments): string {
  switch (data.user.role) {
    case 'principal':
      return 'Ban giám hiệu'
    case 'admin':
      return 'Quản trị viên'
    case 'teacher': {
      const homeroom = data.homeroom_classes.length > 0
      const teaching = data.teaching.length > 0
      if (homeroom && teaching) return 'Giáo viên chủ nhiệm và bộ môn'
      if (homeroom) return 'Giáo viên chủ nhiệm'
      if (teaching) return 'Giáo viên bộ môn'
      return 'Giáo viên'
    }
  }
}
