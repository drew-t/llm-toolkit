import { api } from '../api'
import type { ResultsQuery } from '../types'
import { useApi } from './useApi'

export function useResults(q: ResultsQuery) {
  const key = JSON.stringify(q)
  return useApi(() => api.results(q), [key])
}
