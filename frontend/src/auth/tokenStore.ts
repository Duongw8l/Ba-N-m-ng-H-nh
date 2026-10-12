// Nơi duy nhất đọc/ghi access token trong trình duyệt (D-045).
// sessionStorage: sống qua tải lại trang, mất khi đóng tab, và mỗi tab có token riêng nên có thể mở
// hai tab đăng nhập hai vai trò khác nhau. Muốn giữ đăng nhập qua nhiều tab thì đổi sang
// localStorage ở đây, không phải sửa chỗ khác. Token không bao giờ nằm trong URL.
const KEY = 'classroom.token'

export function getToken(): string | null {
  try {
    return sessionStorage.getItem(KEY)
  } catch {
    return null // trình duyệt chặn lưu trữ: coi như chưa đăng nhập
  }
}

export function setToken(token: string): void {
  try {
    sessionStorage.setItem(KEY, token)
  } catch {
    // Không lưu được thì đăng nhập vẫn dùng được tới khi tải lại trang.
  }
}

export function clearToken(): void {
  try {
    sessionStorage.removeItem(KEY)
  } catch {
    // Không có gì để xoá.
  }
}
