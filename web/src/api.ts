import type {
  CompareResponse,
  CreateRunRequest,
  CreateRunResponse,
  HostsResponse,
  ModelsResponse,
  ResultRow,
  ResultsQuery,
  ResultsResponse,
  RunRow,
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

export function runWsUrl(id: number): string {
  const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${proto}//${window.location.host}/ws/runs/${id}`
}

export function runHref(host: string, runner: string, gpu: string | null): string {
  const u = new URLSearchParams({ host, runner })
  if (gpu) u.set('gpu', gpu)
  return `/run?${u.toString()}`
}

export const api = {
  hosts: () => getJson<HostsResponse>('/api/hosts'),
  refreshHosts: () => getJson<HostsResponse>('/api/hosts/refresh', { method: 'POST' }),

  results: (q: ResultsQuery = {}) =>
    getJson<ResultsResponse>(`/api/results${qs(q as Record<string, string | number | undefined>)}`),
  result: (id: number) => getJson<ResultRow>(`/api/results/${id}`),
  compare: (ids: number[]) =>
    getJson<CompareResponse>('/api/results/compare', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids }),
    }),

  runs: (q: { status?: string; limit?: number; offset?: number } = {}) =>
    getJson<RunsResponse>(`/api/runs${qs(q)}`),
  run: (id: number) => getJson<RunRow>(`/api/runs/${id}`),
  createRun: (body: CreateRunRequest) =>
    getJson<CreateRunResponse>('/api/runs', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify(body),
    }),
  cancelRun: (id: number) =>
    getJson<{ id: number; cancelled: boolean }>(`/api/runs/${id}`, { method: 'DELETE' }),

  models: () => getJson<ModelsResponse>('/api/models'),
}
