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
import type { MonthAbsence } from '../../api/analytics'
import { formatMonth, formatMonthShort } from '../../lib/format'
import { axisTick, gridProps, legendProps, tooltipProps } from './theme'

interface AbsenceChartProps {
  months: MonthAbsence[]
  label: string
}

// Số buổi nghỉ theo tháng, chia nghỉ có phép và không phép (đi muộn không tính là nghỉ).
export function AbsenceChart({ months, label }: AbsenceChartProps) {
  const data = months.map((item) => ({
    month: item.month,
    name: formatMonthShort(item.month),
    excused: item.excused,
    unexcused: item.unexcused,
  }))
  return (
    <figure aria-label={label} className="h-64 w-full min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="name" tick={axisTick()} />
          <YAxis allowDecimals={false} tick={axisTick()} />
          <Tooltip {...tooltipProps}
            labelFormatter={(_label, payload) =>
              payload?.[0] ? formatMonth(String(payload[0].payload.month)) : ''
            }
          />
          <Legend itemSorter={null} {...legendProps} />
          <Bar
            dataKey="excused"
            name="Nghỉ có phép"
            stackId="absence"
            fill="var(--chart-accent)"
            isAnimationActive={false}
          />
          <Bar
            dataKey="unexcused"
            name="Nghỉ không phép"
            stackId="absence"
            fill="var(--chart-fail)"
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
