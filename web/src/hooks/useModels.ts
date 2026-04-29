import { api } from '../api'
import { useApi } from './useApi'

export function useModels() {
  return useApi(() => api.models(), [])
}
