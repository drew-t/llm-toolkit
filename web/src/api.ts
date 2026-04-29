import type {
  CompareResponse,
  HostsResponse,
  ModelsResponse,
  ResultRow,
  ResultsQuery,
  ResultsResponse,
  RunsResponse,
} from './types'

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new Error(`${r.status} ${r.statusText}: ${body || url}`)
  }
  return r.json() as Promise<T>
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  hosts: () => getJson<HostsResponse>('/api/hosts'),
  refreshHosts: () => getJson<HostsResponse>('/api/hosts/refresh', { method: 'POST' }),

  results: (q: ResultsQuery = {}) => getJson<ResultsResponse>(`/api/results${qs(q as Record<string, string | number | undefined>)}`),
  result: (id: number) => getJson<ResultRow>(`/api/results/${id}`),
  compare: (ids: number[]) =>
    getJson<CompareResponse>('/api/results/compare', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids }),
    }),

  runs: (q: { status?: string; limit?: number; offset?: number } = {}) =>
    getJson<RunsResponse>(`/api/runs${qs(q)}`),

  models: () => getJson<ModelsResponse>('/api/models'),
}
