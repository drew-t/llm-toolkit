import { useMemo, useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'
import { ResultsFilters } from './results/ResultsFilters'
import type { ResultsQuery } from '../types'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [query, setQuery] = useState<ResultsQuery>({})
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

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Results</h1>
      <ResultsFilters value={query} onChange={setQuery} facets={facets} />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
    </div>
  )
}
