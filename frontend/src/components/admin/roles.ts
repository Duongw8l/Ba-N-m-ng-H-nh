import type { UserRole } from '../../api/auth'

// Nhãn khớp backend/app/core/labels.py (UserRole); back-end cũng trả sẵn `role_label` cho từng tài khoản.
export const ROLE_OPTIONS: { value: UserRole; label: string }[] = [
  { value: 'teacher', label: 'Giáo viên' },
  { value: 'principal', label: 'Ban giám hiệu' },
  { value: 'admin', label: 'Quản trị viên' },
]
