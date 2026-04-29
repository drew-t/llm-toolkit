import { api } from '../api'
import { useApi } from './useApi'

export function useHosts() {
  return useApi(() => api.hosts(), [])
}
