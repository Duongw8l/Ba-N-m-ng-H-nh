import { useQuery } from '@tanstack/react-query'
import { fetchHealth } from '../api/health'

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: ({ signal }) => fetchHealth(signal),
    refetchInterval: 15_000,
    retry: 1,
  })
}
