import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { formatScore } from '../../lib/format'
import { axisTick, gridProps, legendProps, tooltipProps } from './theme'

export interface CompareDatum {
  name: string
  first: number | null
  second: number | null
}

interface CompareChartProps {
  data: CompareDatum[]
  label: string
  // Trục tung: điểm (thang 0 đến 10) hoặc số học sinh.
  kind: 'score' | 'count'
}

// Hai cột cạnh nhau cho mỗi lớp: học kỳ I và học kỳ II. Hai số đều do API trả; giao diện không tự
// trừ hay tính chênh lệch.
export function CompareChart({ data, label, kind }: CompareChartProps) {
  return (
    <figure aria-label={label} className="h-72 w-full min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="name" tick={axisTick()} />
          <YAxis
            allowDecimals={kind === 'score'}
            domain={kind === 'score' ? [0, 10] : [0, 'auto']}
            ticks={kind === 'score' ? [0, 2, 4, 6, 8, 10] : undefined}
            tick={axisTick()}
          />
          <Tooltip {...tooltipProps}
            formatter={(value) =>
              typeof value === 'number' ? (kind === 'score' ? formatScore(value) : value) : '—'
            }
          />
          <Legend itemSorter={null} {...legendProps} />
          <Bar
            dataKey="first"
            name="Học kỳ I"
            fill="var(--chart-accent-2)"
            isAnimationActive={false}
            radius={[4, 4, 0, 0]}
          />
          <Bar
            dataKey="second"
            name="Học kỳ II"
            fill="var(--chart-accent)"
            isAnimationActive={false}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
