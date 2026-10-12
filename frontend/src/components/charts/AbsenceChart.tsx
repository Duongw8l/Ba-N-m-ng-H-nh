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
    <figure aria-label={label} className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="name" tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} tick={{ fontSize: 12 }} />
          <Tooltip
            labelFormatter={(_label, payload) =>
              payload?.[0] ? formatMonth(String(payload[0].payload.month)) : ''
            }
          />
          <Legend itemSorter={null} />
          <Bar
            dataKey="excused"
            name="Nghỉ có phép"
            stackId="absence"
            fill="#0284c7"
            isAnimationActive={false}
          />
          <Bar
            dataKey="unexcused"
            name="Nghỉ không phép"
            stackId="absence"
            fill="#dc2626"
            isAnimationActive={false}
          />
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
