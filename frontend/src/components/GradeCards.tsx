import { Link } from 'react-router-dom'

export function GradeCards({ grades }: { grades: number[] }) {
  return (
    <section
      aria-labelledby="cac-khoi"
      className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm"
    >
      <h2 id="cac-khoi" className="text-lg font-medium">
        Các khối trong trường
      </h2>
      <ul className="mt-3 grid gap-3 sm:grid-cols-3">
        {grades.map((grade) => (
          <li key={grade} className="rounded-lg border border-slate-200 p-4">
            <span className="block text-xl font-semibold">Khối {grade}</span>
            <Link
              to={`/grades/${grade}`}
              aria-label={`So sánh các lớp khối ${grade}`}
              className="mt-2 inline-block text-sm font-medium text-blue-700 hover:underline"
            >
              So sánh các lớp
            </Link>
          </li>
        ))}
      </ul>
    </section>
  )
}
