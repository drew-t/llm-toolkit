// Mirrors backend JSON shapes. Keep in sync with src/llm_toolkit/web/routes/*.

export interface ModelInfo {
  tag: string
  size_bytes: number | null
  modified: number | null
}

export interface LoadedModel {
  tag: string
  vram_bytes: number | null
  expires_at: number | null
}

export interface RunnerSnapshot {
  runner: string
  base_url: string
  gpu: string | null
  version: string | null
  reachable: boolean
  error: string | null
  installed_models: ModelInfo[]
  loaded_models: LoadedModel[]
  raw: Record<string, unknown>
}

export interface HostSnapshot {
  name: string
  runners: RunnerSnapshot[]
}

export interface HostsResponse {
  hosts: HostSnapshot[]
}

export interface ResultRow {
  id: number
  benchmark: string
  model: string
  host: string | null
  runner: string | null
  gpu: string | null
  run_id: number | null
  timestamp: number
  metrics: Record<string, number | string | null>
  metadata: Record<string, unknown>
}

export interface ResultsResponse {
  results: ResultRow[]
}

export interface CompareRow extends ResultRow {
  diff_pct: number | null
}

export interface CompareResponse {
  primary_metric: string
  rows: CompareRow[]
}

export interface RunRow {
  id: number
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  benchmark: string
  model: string
  host: string | null
  runner: string | null
  gpu: string | null
  runner_version: string | null
  args?: unknown
  config?: unknown
  started_at: number | null
  finished_at: number | null
  exit_code: number | null
  log_path: string | null
}

export interface RunsResponse {
  runs: RunRow[]
}

export interface ModelIndexRow {
  tag: string
  host: string
  runner: string
  gpu: string | null
  loaded: boolean
  size_bytes: number | null
}

export interface ModelsResponse {
  models: ModelIndexRow[]
}

export interface ResultsQuery {
  benchmark?: string
  model?: string
  host?: string
  runner?: string
  gpu?: string
  since?: number
  sort?: 'timestamp' | 'benchmark' | 'model' | 'host' | 'runner' | 'gpu'
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export interface CreateRunRequest {
  benchmark: string
  model: string
  host: string
  runner: string
  gpu: string | null
  base_url: string
  args: Record<string, unknown>
}

export interface CreateRunResponse {
  id: number
  status: 'pending'
}

export type RunEvent =
  | { type: 'log'; line: string }
  | { type: 'status'; status: string }
  | { type: 'result'; result_id: number; benchmark: string; model: string;
      metrics: Record<string, number | string | null> }
  | { type: 'finished'; status: string; exit_code: number | null;
      results_imported: number }
