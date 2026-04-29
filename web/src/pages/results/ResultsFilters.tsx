import type { ResultsQuery } from '../../types'

interface Props {
  value: ResultsQuery
  onChange: (next: ResultsQuery) => void
  facets: {
    benchmarks: string[]
    models: string[]
    hosts: string[]
    runners: string[]
    gpus: string[]
  }
}

const SINCE_OPTIONS: { label: string; seconds: number | null }[] = [
  { label: 'All time', seconds: null },
  { label: 'Last 24h', seconds: 60 * 60 * 24 },
  { label: 'Last 7d', seconds: 60 * 60 * 24 * 7 },
  { label: 'Last 30d', seconds: 60 * 60 * 24 * 30 },
]

export function ResultsFilters({ value, onChange, facets }: Props) {
  function set<K extends keyof ResultsQuery>(key: K, v: ResultsQuery[K]) {
    onChange({ ...value, [key]: v || undefined })
  }

  return (
    <div class="mb-3 flex flex-wrap items-center gap-2 text-xs">
      <Pick label="Benchmark" value={value.benchmark} options={facets.benchmarks} onChange={(v) => set('benchmark', v)} />
      <Pick label="Model" value={value.model} options={facets.models} onChange={(v) => set('model', v)} />
      <Pick label="Host" value={value.host} options={facets.hosts} onChange={(v) => set('host', v)} />
      <Pick label="Runner" value={value.runner} options={facets.runners} onChange={(v) => set('runner', v)} />
      <Pick label="GPU" value={value.gpu} options={facets.gpus} onChange={(v) => set('gpu', v)} />
      <select
        class="rounded border border-border bg-surface px-2 py-1"
        value={value.since ? String(value.since) : ''}
        onChange={(e) => {
          const sec = (e.currentTarget as HTMLSelectElement).value
          if (!sec) {
            onChange({ ...value, since: undefined })
          } else {
            onChange({ ...value, since: Date.now() / 1000 - Number(sec) })
          }
        }}
      >
        {SINCE_OPTIONS.map((o) => (
          <option key={o.label} value={o.seconds ?? ''}>{o.label}</option>
        ))}
      </select>
      {Object.values(value).some((v) => v !== undefined) && (
        <button
          class="text-text-muted underline hover:text-text"
          onClick={() => onChange({})}
        >
          Clear
        </button>
      )}
    </div>
  )
}

function Pick({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: string[]
  onChange: (v: string) => void
}) {
  return (
    <select
      class="rounded border border-border bg-surface px-2 py-1"
      value={value ?? ''}
      onChange={(e) => onChange((e.currentTarget as HTMLSelectElement).value)}
    >
      <option value="">{label}: any</option>
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  )
}
