import { useState } from 'react'
import type { FormEvent } from 'react'
import { ApiError } from '../../api/client'
import { useRegulationSearch } from '../../hooks/useRegulations'
import { formatSimilarity } from '../../lib/format'

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

// Thử tìm: hỏi một câu và xem những đoạn văn bản còn hiệu lực mà Trợ lý AI sẽ được đưa cho. Độ tương
// đồng và ngưỡng do back-end tính; trang này chỉ hiển thị.
export function SearchBox() {
  const search = useRegulationSearch()
  const [question, setQuestion] = useState('')

  function submit(event: FormEvent) {
    event.preventDefault()
    if (question.trim() !== '') search.mutate(question.trim())
  }

  const result = search.data
  return (
    <div className="space-y-4">
      <form onSubmit={submit} className="flex flex-wrap items-end gap-3">
        <div className="min-w-64 flex-1">
          <label htmlFor="cau-hoi-thu" className="block text-sm font-medium">
            Câu hỏi
          </label>
          <input
            id="cau-hoi-thu"
            type="text"
            value={question}
            maxLength={500}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="Ví dụ: Nghỉ bao nhiêu buổi thì bị mời phụ huynh?"
            className="mt-1 block w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-base"
          />
        </div>
        <button
          type="submit"
          disabled={question.trim() === '' || search.isPending}
          className="rounded-md bg-blue-700 px-4 py-2 font-medium text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {search.isPending ? 'Đang tìm…' : 'Thử tìm'}
        </button>
      </form>

      {search.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {errorText(search.error)}
        </p>
      )}

      {result && !result.found && (
        <div role="status" className="rounded-md bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">{result.message}</p>
          {result.best_similarity !== null && (
            <p className="mt-1">
              Đoạn gần nhất có độ tương đồng {formatSimilarity(result.best_similarity)}, dưới ngưỡng{' '}
              {formatSimilarity(result.min_similarity)}.
            </p>
          )}
        </div>
      )}

      {result?.found && (
        <ol aria-label="Kết quả tìm" className="space-y-3">
          {result.hits.map((hit, index) => (
            <li
              key={`${hit.document_id}-${hit.article}-${hit.clause}-${index}`}
              className="rounded-lg border border-slate-200 p-4"
            >
              <p className="text-sm font-medium">
                {hit.document_name}
                {hit.article && ` · ${hit.article}`}
                {hit.clause && ` · ${hit.clause}`}
                <span className="ml-2 font-normal text-slate-500">
                  tương đồng {formatSimilarity(hit.similarity)}
                </span>
              </p>
              <p className="mt-2 whitespace-pre-wrap text-sm text-slate-800">{hit.content}</p>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}
