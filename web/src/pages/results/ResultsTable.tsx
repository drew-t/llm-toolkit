import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
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
  const [sorting, setSorting] = useState<SortingState>([])

  const columns: ColumnDef<ResultRow>[] = [
    {
      id: 'select',
      header: ({ table }) => (
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
            table.resetRowSelection()
          }}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selected.has(row.original.id)}
          onChange={() => onToggle(row.original.id)}
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
        {table.getRowModel().rows.map((row) => (
          <tr
            key={row.id}
            class={`border-t border-border ${
              selected.has(row.original.id) ? 'bg-surface' : 'hover:bg-surface'
            }`}
          >
            {row.getVisibleCells().map((cell) => (
              <td key={cell.id} class="px-3 py-2">
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
