import { render, screen } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'
import { ResultsTable } from '../pages/results/ResultsTable'
import type { ResultRow } from '../types'

const ROWS: ResultRow[] = [
  {
    id: 1,
    benchmark: 'throughput_benchy',
    model: 'qwen3.5:9b',
    host: 'drubuntu',
    runner: 'ollama',
    gpu: '3080ti',
    run_id: null,
    timestamp: 1_714_300_000,
    metrics: { tg_throughput: 42.5, pp_throughput: 100.1 },
    metadata: {},
  },
  {
    id: 2,
    benchmark: 'throughput_benchy',
    model: 'qwen3.5:9b',
    host: 'localhost',
    runner: 'ollama',
    gpu: 'm3-max',
    run_id: null,
    timestamp: 1_714_400_000,
    metrics: { tg_throughput: 31.2, pp_throughput: 80.0 },
    metadata: {},
  },
]

describe('ResultsTable', () => {
  it('renders one row per result and shows the primary metric', () => {
    render(<ResultsTable rows={ROWS} selected={new Set()} onToggle={() => {}} />)
    expect(screen.getAllByRole('row')).toHaveLength(3) // header + 2 rows
    expect(screen.getByText('42.50')).toBeTruthy()
    expect(screen.getByText('31.20')).toBeTruthy()
  })

  it('renders host/runner/gpu in a combined cell', () => {
    render(<ResultsTable rows={ROWS} selected={new Set()} onToggle={() => {}} />)
    expect(screen.getByText(/drubuntu \/ ollama \/ 3080ti/)).toBeTruthy()
  })

  it('reflects selected ids via the checkbox', () => {
    render(<ResultsTable rows={ROWS} selected={new Set([1])} onToggle={() => {}} />)
    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    // checkboxes[0] is the header "select all". With default sort timestamp DESC,
    // row id=2 (newer) renders first → checkboxes[1] = id=2, checkboxes[2] = id=1.
    expect(checkboxes[1].checked).toBe(false)  // id=2 not selected
    expect(checkboxes[2].checked).toBe(true)   // id=1 selected
  })
})
