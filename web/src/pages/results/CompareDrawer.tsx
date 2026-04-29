import type { CompareResponse, CompareRow } from '../../types'
import { MetricBars } from './MetricBars'

interface Props {
  data: CompareResponse
  onClose: () => void
}

export function CompareDrawer({ data, onClose }: Props) {
  const bars = data.rows.map((r) => ({
    label: shortLabel(r),
    value: numericMetric(r, data.primary_metric),
  }))

  return (
    <aside class="fixed right-0 top-0 z-30 flex h-full w-[28rem] flex-col border-l border-border bg-panel p-4 shadow-xl">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-base font-semibold">Compare</h2>
        <button class="text-text-muted hover:text-text" onClick={onClose}>
          ✕
        </button>
      </div>
      <p class="mb-3 text-xs text-text-muted">
        Primary metric: <span class="font-mono">{data.primary_metric}</span>
      </p>
      <MetricBars bars={bars} unit={data.primary_metric} />
      <div class="mt-4 flex flex-col gap-2 overflow-y-auto">
        {data.rows.map((r, i) => (
          <CompareCard key={r.id} row={r} primary={data.primary_metric} isBaseline={i === 0} />
        ))}
      </div>
    </aside>
  )
}

function CompareCard({
  row,
  primary,
  isBaseline,
}: {
  row: CompareRow
  primary: string
  isBaseline: boolean
}) {
  const value = numericMetric(row, primary)
  return (
    <div class="rounded border border-border bg-surface p-3 text-xs">
      <div class="flex items-center justify-between">
        <span class="font-mono">{shortLabel(row)}</span>
        <span class={diffClass(row.diff_pct, isBaseline)}>
          {isBaseline ? 'baseline' : formatDiff(row.diff_pct)}
        </span>
      </div>
      <div class="mt-1 text-text-muted">
        {row.benchmark} · {row.model}
      </div>
      <div class="mt-1 font-mono text-text"><span>{value}</span> {primary}</div>
    </div>
  )
}

function shortLabel(r: { host: string | null; runner: string | null; gpu: string | null }) {
  return [r.host ?? '?', r.runner ?? '?', r.gpu ?? '?'].join(' / ')
}

function numericMetric(r: CompareRow, key: string): number {
  const v = r.metrics[key]
  return typeof v === 'number' ? v : 0
}

function formatDiff(pct: number | null): string {
  if (pct === null) return '—'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function diffClass(pct: number | null, isBaseline: boolean): string {
  if (isBaseline) return 'text-text-muted'
  if (pct === null) return 'text-text-ghost'
  if (pct > 0) return 'text-good'
  if (pct < 0) return 'text-bad'
  return 'text-text-muted'
}
