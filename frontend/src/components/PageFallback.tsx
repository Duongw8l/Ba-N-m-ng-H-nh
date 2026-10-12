// Hiện khi mở thẳng một đường dẫn tới trang nạp theo yêu cầu (lazy) và gói của trang chưa tải xong.
export function PageFallback() {
  return (
    <p aria-live="polite" className="p-6 text-slate-600">
      Đang tải…
    </p>
  )
}
