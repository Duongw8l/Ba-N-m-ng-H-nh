import { Link } from 'react-router-dom'
import { Icon } from './Icon'

// BGH: ba khối của trường, mỗi khối một thẻ dẫn tới trang so sánh các lớp.
export function GradeCards({ grades }: { grades: number[] }) {
  return (
    <section aria-labelledby="cac-khoi" className="space-y-3">
      <h2 id="cac-khoi" className="text-base font-semibold tracking-tight">
        Các khối trong trường
      </h2>
      <ul className="grid gap-4 sm:grid-cols-3">
        {grades.map((grade) => (
          <li key={grade}>
            <Link
              to={`/grades/${grade}`}
              aria-label={`So sánh các lớp khối ${grade}`}
              className="card group relative block overflow-hidden p-5 transition-all hover:-translate-y-0.5 hover:border-brand-300"
            >
              <span
                aria-hidden="true"
                className="absolute -top-8 -right-8 h-28 w-28 rounded-full bg-tint opacity-80 transition-transform group-hover:scale-110"
              />
              <span className="relative flex h-10 w-10 items-center justify-center rounded-xl bg-tint text-brand-700 dark:text-brand-300">
                <Icon name="layers" />
              </span>
              <span className="relative mt-4 block text-2xl font-semibold tracking-tight">
                Khối {grade}
              </span>
              <span className="relative mt-1 flex items-center gap-1 text-sm font-medium text-link">
                So sánh các lớp
                <Icon name="arrow-right" className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
