import {
  Bar,
  BarChart,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { axisTick, labelFill, tooltipProps } from './theme'

export interface DistributionDatum {
  name: string
  value: number
  color: string
}

// Phân bố ĐTB của lớp theo các ngưỡng; tên cột do nơi gọi dựng từ `thresholds` của API.
export function DistributionChart({
  data,
  label,
}: {
  data: DistributionDatum[]
  label: string
}) {
  return (
    <figure aria-label={label} className="h-56 w-full min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 20, right: 8, left: -16, bottom: 0 }}>
          <XAxis dataKey="name" tick={axisTick(11)} interval={0} />
          <YAxis allowDecimals={false} tick={axisTick()} />
          <Tooltip {...tooltipProps} formatter={(value) => [`${value} học sinh`, '']} separator="" />
          <Bar dataKey="value" isAnimationActive={false} radius={[4, 4, 0, 0]}>
            {data.map((item) => (
              <Cell key={item.name} fill={item.color} />
            ))}
            <LabelList dataKey="value" position="top" fill={labelFill} fontSize={12} />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
