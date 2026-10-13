import { createElement } from 'react'

// Kiểu dùng chung cho biểu đồ Recharts. Mọi màu là biến CSS (index.css) nên tự đổi theo chế độ
// sáng/tối; nhãn chữ và số luôn có trên cột nên không chỉ dựa vào màu.
export const axisTick = (fontSize = 12) => ({ fontSize, fill: 'var(--chart-axis)' })

export const gridProps = {
  strokeDasharray: '3 3',
  vertical: false,
  stroke: 'var(--chart-grid)',
} as const

export const tooltipProps = {
  contentStyle: {
    background: 'var(--color-surface)',
    border: '1px solid var(--color-slate-200)',
    borderRadius: 12,
    boxShadow: 'var(--shadow-card)',
    color: 'var(--color-slate-900)',
    fontSize: 13,
  },
  labelStyle: { color: 'var(--color-slate-700)', fontWeight: 600 },
  itemStyle: { color: 'var(--color-slate-700)' },
  cursor: { fill: 'var(--chart-grid)', opacity: 0.35 },
} as const

// Chữ chú giải luôn màu trung tính (Recharts mặc định tô theo màu chuỗi dữ liệu nên khó đọc).
export const legendProps = {
  wrapperStyle: { fontSize: 12, width: '100%', left: 0 },
  formatter: (value: string) => createElement('span', { style: { color: 'var(--color-slate-700)' } }, value),
} as const

export const labelFill = 'var(--color-slate-700)'
