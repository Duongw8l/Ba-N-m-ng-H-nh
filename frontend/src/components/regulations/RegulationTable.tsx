import { useState } from 'react'
import { ApiError } from '../../api/client'
import type { RegulationDocument } from '../../api/regulations'
import { useSetRegulationStatus } from '../../hooks/useRegulations'
import { formatDate, formatInt } from '../../lib/format'

function StatusBadge({ document }: { document: RegulationDocument }) {
  const active = document.status === 'active'
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${
        active ? 'bg-green-100 text-green-800' : 'bg-slate-200 text-slate-700'
      }`}
    >
      {document.status_label}
    </span>
  )
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Không kết nối được tới máy chủ. Hãy kiểm tra back-end đã chạy chưa.'
}

// Danh sách văn bản quy định và nút đổi hiệu lực. Văn bản hết hiệu lực không còn được Trợ lý AI trích
// dẫn nhưng vẫn được giữ lại để bật lại khi cần.
export function RegulationTable({ documents }: { documents: RegulationDocument[] }) {
  const mutation = useSetRegulationStatus()
  const [confirmingId, setConfirmingId] = useState<number | null>(null)

  if (documents.length === 0) {
    return (
      <p className="text-sm text-slate-600">
        Chưa có văn bản nào. Hãy tải văn bản đầu tiên ở phần bên dưới.
      </p>
    )
  }

  function change(document: RegulationDocument) {
    mutation.mutate(
      { id: document.id, status: document.status === 'active' ? 'expired' : 'active' },
      { onSettled: () => setConfirmingId(null) },
    )
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto">
        <table className="w-full min-w-max text-left text-sm">
          <thead className="border-b border-slate-200 text-slate-500">
            <tr>
              <th scope="col" className="py-2 pr-4 font-medium">
                Văn bản
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Trạng thái
              </th>
              <th scope="col" className="px-3 py-2 font-medium">
                Ngày tải
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Số điều
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Số đoạn
              </th>
              <th scope="col" className="py-2 pl-3 font-medium">
                <span className="sr-only">Thao tác</span>
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 align-top">
            {documents.map((document) => {
              const active = document.status === 'active'
              const confirming = confirmingId === document.id
              const busy = mutation.isPending && mutation.variables?.id === document.id
              return (
                <tr key={document.id}>
                  <th scope="row" className="py-2 pr-4 text-left font-normal">
                    <span className="block font-medium">{document.name}</span>
                    <span className="block text-xs text-slate-500">{document.file_name}</span>
                  </th>
                  <td className="px-3 py-2">
                    <StatusBadge document={document} />
                    {document.expired_at && (
                      <span className="mt-0.5 block text-xs text-slate-500">
                        từ {formatDate(document.expired_at)}
                      </span>
                    )}
                  </td>
                  <td className="px-3 py-2">{formatDate(document.created_at)}</td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatInt(document.article_count)}
                  </td>
                  <td className="px-3 py-2 text-right tabular-nums">
                    {formatInt(document.chunk_count)}
                  </td>
                  <td className="py-2 pl-3">
                    {confirming ? (
                      <span className="flex flex-wrap items-center gap-2">
                        <span className="max-w-xs text-xs text-slate-600">
                          {active
                            ? 'Trợ lý AI sẽ không còn trích dẫn văn bản này.'
                            : 'Trợ lý AI sẽ trích dẫn lại văn bản này.'}
                        </span>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => change(document)}
                          className="rounded-md bg-blue-700 px-3 py-1.5 font-medium text-white hover:bg-blue-800 disabled:opacity-60"
                        >
                          {busy ? 'Đang lưu…' : 'Xác nhận'}
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => setConfirmingId(null)}
                          className="rounded-md border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-100"
                        >
                          Huỷ
                        </button>
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => {
                          mutation.reset()
                          setConfirmingId(document.id)
                        }}
                        className="rounded-md border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-100"
                      >
                        {active ? 'Đánh dấu hết hiệu lực' : 'Bật lại'}
                      </button>
                    )}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      {mutation.isError && (
        <p role="alert" className="rounded-md bg-red-50 p-3 text-sm text-red-800">
          {errorText(mutation.error)}
        </p>
      )}
    </div>
  )
}
