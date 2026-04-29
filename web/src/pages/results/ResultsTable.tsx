import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { Fragment } from 'preact'
import { useState } from 'preact/hooks'
import type { ResultRow } from '../../types'
import { formatNumber, formatRelativeTime } from '../../utils/format'
import { primaryMetric, secondaryMetric } from '../../utils/metrics'

interface Props {
  rows: ResultRow[]
  selected: Set<number>
  onToggle: (id: number) => void
}

export function ResultsTable({ rows, selected, onToggle }: Props) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'timestamp', desc: true },
  ])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  function toggleExpanded(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const columns: ColumnDef<ResultRow>[] = [
    {
      id: 'select',
      header: () => (
        <input
          type="checkbox"
          checked={
            rows.length > 0 && rows.every((r) => selected.has(r.id))
          }
          onChange={() => {
            const allSelected = rows.every((r) => selected.has(r.id))
            for (const r of rows) {
              if (allSelected) {
                if (selected.has(r.id)) onToggle(r.id)
              } else {
                if (!selected.has(r.id)) onToggle(r.id)
              }
            }
          }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selected.has(row.original.id)}
          onChange={() => onToggle(row.original.id)}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
    { accessorKey: 'benchmark', header: 'Benchmark' },
    { accessorKey: 'model', header: 'Model' },
    {
      id: 'host_combo',
      header: 'Host / Runner / GPU',
      cell: ({ row }) => {
        const r = row.original
        const parts = [r.host ?? '—', r.runner ?? '—', r.gpu ?? '—']
        return <span class="font-mono text-xs">{parts.join(' / ')}</span>
      },
    },
    {
      id: 'primary',
      header: 'Primary',
      cell: ({ row }) => {
        const r = row.original
        const key = primaryMetric(r.benchmark)
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'secondary',
      header: 'Secondary',
      cell: ({ row }) => {
        const r = row.original
        const key = secondaryMetric(r.benchmark)
        if (!key) return <span class="text-text-ghost">—</span>
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'timestamp',
      header: 'When',
      accessorFn: (r) => r.timestamp,
      cell: ({ row }) => (
        <span class="text-xs text-text-muted">
          {formatRelativeTime(row.original.timestamp)}
        </span>
      ),
    },
  ]

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <table class="w-full border-collapse text-sm">
      <thead class="bg-panel text-left text-xs uppercase tracking-wide text-text-ghost">
        {table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>
            {hg.headers.map((h) => (
              <th
                key={h.id}
                class="cursor-pointer px-3 py-2 select-none"
                onClick={h.column.getToggleSortingHandler()}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted() as string] ?? ''}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => {
          const r = row.original
          const isOpen = expanded.has(r.id)
          return (
            <Fragment key={row.id}>
              <tr
                class={`cursor-pointer border-t border-border ${
                  selected.has(r.id) ? 'bg-surface' : 'hover:bg-surface'
                }`}
                onClick={() => toggleExpanded(r.id)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} class="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {isOpen && (
                <tr class="border-t border-border bg-bg">
                  <td colspan={columns.length} class="px-6 py-3">
                    <div class="flex flex-col gap-2 text-xs">
                      {r.run_id !== null && (
                        <div>
                          <span class="text-text-muted">Run: </span>
                          <span class="font-mono text-text">Run #{r.run_id}</span>
                        </div>
                      )}
                      <div>
                        <div class="text-text-muted">metrics</div>
                        <pre class="mt-1 overflow-x-auto rounded border border-border bg-panel p-2 font-mono text-xs">
                          {JSON.stringify(r.metrics, null, 2)}
                        </pre>
                      </div>
                      {Object.keys(r.metadata ?? {}).length > 0 && (
                        <div>
                          <div class="text-text-muted">metadata</div>
                          <pre class="mt-1 overflow-x-auto rounded border border-border bg-panel p-2 font-mono text-xs">
                            {JSON.stringify(r.metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
