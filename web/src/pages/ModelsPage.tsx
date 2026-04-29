import { useState } from 'preact/hooks'
import { useLocation } from 'wouter-preact'
import { useModels } from '../hooks/useModels'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { formatBytes } from '../utils/format'

export function ModelsPage() {
  const { data, error, loading } = useModels()
  const [, navigate] = useLocation()
  const [filter, setFilter] = useState('')

  const rows = (data?.models ?? []).filter((m) =>
    !filter || m.tag.toLowerCase().includes(filter.toLowerCase()),
  )

  function jumpToResults(tag: string) {
    const qs = new URLSearchParams({ model: tag }).toString()
    navigate(`/?${qs}`)
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Models</h1>
      <input
        class="mb-3 w-64 rounded border border-border bg-surface px-2 py-1 text-sm"
        placeholder="Filter by tag…"
        value={filter}
        onInput={(e) => setFilter((e.currentTarget as HTMLInputElement).value)}
      />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <table class="w-full border-collapse text-sm">
          <thead class="bg-panel text-left text-xs uppercase tracking-wide text-text-ghost">
            <tr>
              <th class="px-3 py-2">Tag</th>
              <th class="px-3 py-2">Host</th>
              <th class="px-3 py-2">Runner</th>
              <th class="px-3 py-2">GPU</th>
              <th class="px-3 py-2">Loaded</th>
              <th class="px-3 py-2">Size</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m, i) => (
              <tr key={`${m.host}-${m.runner}-${m.tag}-${i}`} class="border-t border-border">
                <td class="px-3 py-2 font-mono">{m.tag}</td>
                <td class="px-3 py-2">{m.host}</td>
                <td class="px-3 py-2">{m.runner}</td>
                <td class="px-3 py-2">{m.gpu ?? '—'}</td>
                <td class="px-3 py-2">
                  <span class={m.loaded ? 'text-good' : 'text-text-ghost'}>
                    {m.loaded ? 'yes' : 'no'}
                  </span>
                </td>
                <td class="px-3 py-2 font-mono text-xs">{formatBytes(m.size_bytes)}</td>
                <td class="px-3 py-2">
                  <button
                    class="text-accent hover:underline"
                    onClick={() => jumpToResults(m.tag)}
                  >
                    Results →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
