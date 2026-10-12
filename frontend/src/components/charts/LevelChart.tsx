import { Bar, BarChart, Cell, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { LEVEL_COLORS, LEVEL_LABELS } from '../../lib/labels'

interface LevelChartProps {
  counts: Record<string, number>
  keys: readonly string[]
  label: string
}

// Số học sinh ở từng mức (học tập hoặc rèn luyện). Mọi cột có nhãn chữ và số ở đầu cột, nên không
// chỉ dựa vào màu.
export function LevelChart({ counts, keys, label }: LevelChartProps) {
  const data = keys.map((key) => ({ key, name: LEVEL_LABELS[key] ?? key, value: counts[key] ?? 0 }))
  return (
    <figure aria-label={label} className="h-56 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="name" tick={{ fontSize: 12 }} interval={0} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(value) => [`${value} học sinh`, '']} separator="" />
          <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
            {data.map((item) => (
              <Cell key={item.key} fill={LEVEL_COLORS[item.key] ?? '#64748b'} />
            ))}
            <LabelList dataKey="value" position="top" className="text-xs" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
