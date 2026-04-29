import { useEffect, useMemo, useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'
import { ResultsFilters } from './results/ResultsFilters'
import { CompareDrawer } from './results/CompareDrawer'
import type { CompareResponse, ResultsQuery } from '../types'
import { api } from '../api'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [query, setQuery] = useState<ResultsQuery>(() => {
    const usp = new URLSearchParams(window.location.search)
    const out: ResultsQuery = {}
    const model = usp.get('model'); if (model) out.model = model
    const host = usp.get('host'); if (host) out.host = host
    const runner = usp.get('runner'); if (runner) out.runner = runner
    const gpu = usp.get('gpu'); if (gpu) out.gpu = gpu
    const benchmark = usp.get('benchmark'); if (benchmark) out.benchmark = benchmark
    return out
  })
  const [compare, setCompare] = useState<CompareResponse | null>(null)
  const [compareError, setCompareError] = useState<string | null>(null)
  const { data, error, loading } = useResults(query)

  const facets = useMemo(() => {
    const rows = data?.results ?? []
    const uniq = (arr: (string | null | undefined)[]) =>
      Array.from(new Set(arr.filter((s): s is string => !!s))).sort()
    return {
      benchmarks: uniq(rows.map((r) => r.benchmark)),
      models: uniq(rows.map((r) => r.model)),
      hosts: uniq(rows.map((r) => r.host)),
      runners: uniq(rows.map((r) => r.runner)),
      gpus: uniq(rows.map((r) => r.gpu)),
    }
  }, [data])

  // Drop selections that disappear after a filter change.
  useEffect(() => {
    if (!data) return
    const visible = new Set(data.results.map((r) => r.id))
    setSelected((prev) => new Set([...prev].filter((id) => visible.has(id))))
  }, [data])

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function openCompare() {
    setCompareError(null)
    try {
      const ids = [...selected]
      const resp = await api.compare(ids)
      setCompare(resp)
    } catch (e) {
      setCompareError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Results</h1>
      <ResultsFilters value={query} onChange={setQuery} facets={facets} />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {compareError && <ErrorBanner error={compareError} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
      {selected.size >= 2 && !compare && (
        <div class="sticky bottom-0 mt-3 flex items-center justify-between rounded border border-border bg-panel px-4 py-2 text-sm shadow">
          <span>{selected.size} selected</span>
          <button
            class="rounded bg-accent px-3 py-1 text-bg hover:opacity-90"
            onClick={() => void openCompare()}
          >
            Compare
          </button>
        </div>
      )}
      {compare && <CompareDrawer data={compare} onClose={() => setCompare(null)} />}
    </div>
  )
}
