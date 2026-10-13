import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError } from '../api/client'
import {
  fetchRegulations,
  searchRegulations,
  setRegulationStatus,
  uploadRegulation,
} from '../api/regulations'
import type { RegulationStatus } from '../api/regulations'
import { useAuth } from '../auth/context'

export function useRegulations() {
  const { token } = useAuth()
  return useQuery({
    queryKey: ['regulations', token],
    queryFn: ({ signal }) => fetchRegulations(signal),
    enabled: token !== null,
    retry: (failureCount, error) =>
      failureCount < 1 && !(error instanceof ApiError && error.status < 500),
  })
}

// Tải lên và đổi hiệu lực đều làm danh sách văn bản đổi, nên làm mới danh sách sau khi xong.
export function useUploadRegulation() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ name, file }: { name: string; file: File }) => uploadRegulation(name, file),
    onSuccess: () => client.invalidateQueries({ queryKey: ['regulations'] }),
  })
}

export function useSetRegulationStatus() {
  const client = useQueryClient()
  return useMutation({
    mutationFn: ({ id, status }: { id: number; status: RegulationStatus }) =>
      setRegulationStatus(id, status),
    onSuccess: () => client.invalidateQueries({ queryKey: ['regulations'] }),
  })
}

// "Thử tìm" chạy khi bấm nút, không tự chạy khi gõ (mỗi lần tìm phải tính vector của câu hỏi).
export function useRegulationSearch() {
  return useMutation({ mutationFn: (question: string) => searchRegulations(question) })
}
