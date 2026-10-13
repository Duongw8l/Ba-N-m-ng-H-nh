// Hiện khi mở thẳng một đường dẫn tới trang nạp theo yêu cầu (lazy) và gói của trang chưa tải xong.
export function PageFallback() {
  return (
    <div aria-live="polite" aria-busy="true" className="mx-auto max-w-7xl space-y-5 p-6">
      <span className="sr-only">Đang tải…</span>
      <div className="skeleton h-8 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((item) => (
          <div key={item} className="skeleton h-28 rounded-2xl" />
        ))}
      </div>
      <div className="skeleton h-64 rounded-2xl" />
    </div>
  )
}
