// Chữ cái đầu của hai từ cuối trong họ tên ("Bùi Thanh Linh" thành "TL"), cho ảnh đại diện chữ cái.
export function initialsOf(fullName: string): string {
  const parts = fullName.trim().split(/\s+/).filter(Boolean)
  if (parts.length === 0) return '?'
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase()
  return (parts[parts.length - 2][0] + parts[parts.length - 1][0]).toUpperCase()
}
