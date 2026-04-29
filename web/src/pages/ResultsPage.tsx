import { useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const { data, error, loading } = useResults({})

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
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
    </div>
  )
}
