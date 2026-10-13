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
import type { ClassOverview } from '../../api/analytics'
import { LEVEL_COLORS, LEVEL_LABELS } from '../../lib/labels'
import { axisTick, gridProps, legendProps, tooltipProps } from './theme'

const STACK = ['good', 'fair', 'pass', 'fail', 'incomplete'] as const

// Cột chồng: số học sinh ở từng mức học tập của mỗi lớp trong khối.
export function ClassLevelsChart({ classes, label }: { classes: ClassOverview[]; label: string }) {
  const data = classes.map((item) => ({ name: item.name, ...item.learning_levels }))
  return (
    <figure aria-label={label} className="h-72 w-full min-w-0 overflow-hidden">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
          <CartesianGrid {...gridProps} />
          <XAxis dataKey="name" tick={axisTick()} />
          <YAxis allowDecimals={false} tick={axisTick()} />
          <Tooltip {...tooltipProps} />
          <Legend itemSorter={null} {...legendProps} />
          {STACK.map((key) => (
            <Bar
              key={key}
              dataKey={key}
              name={LEVEL_LABELS[key]}
              stackId="levels"
              fill={LEVEL_COLORS[key]}
              isAnimationActive={false}
            />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </figure>
  )
}
