// Dấu hiệu nhận diện: mũ tốt nghiệp trên nền xanh ngọc, kèm một tia sáng nhỏ (trợ lý AI). Dùng chung
// với public/favicon.svg.
export function LogoMark({ className = 'h-9 w-9' }: { className?: string }) {
  return (
    <svg viewBox="0 0 40 40" className={`shrink-0 ${className}`} aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id="logo-bg" x1="4" y1="2" x2="36" y2="38" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#2dd4bf" />
          <stop offset="1" stopColor="#0f766e" />
        </linearGradient>
      </defs>
      <rect width="40" height="40" rx="11" fill="url(#logo-bg)" />
      <path d="M20 10 7.5 16 20 22l12.5-6L20 10Z" fill="#fff" />
      <path d="M13 19.2v4.4c0 1.9 3.1 3.6 7 3.6s7-1.7 7-3.6v-4.4L20 22.6l-7-3.4Z" fill="#fff" fillOpacity="0.92" />
      <path d="M32 17.5v6" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" />
      <path d="m32.6 27.4.6 1.6 1.6.6-1.6.6-.6 1.6-.6-1.6-1.6-.6 1.6-.6.6-1.6Z" fill="#fde68a" />
    </svg>
  )
}

interface LogoProps {
  // true: chỉ hiện dấu hiệu (sidebar thu gọn).
  compact?: boolean
  className?: string
}

export function Logo({ compact = false, className = '' }: LogoProps) {
  return (
    <span className={`flex items-center gap-3 ${className}`}>
      <LogoMark />
      {!compact && (
        <span className="leading-tight">
          <span className="block text-[0.95rem] font-semibold tracking-tight">Trợ lý lớp học</span>
          <span className="block text-xs font-medium opacity-70">THPT · Khối 10-12</span>
        </span>
      )}
    </span>
  )
}
