import { render, screen } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'
import { CompareDrawer } from '../pages/results/CompareDrawer'
import type { CompareResponse } from '../types'

const RESP: CompareResponse = {
  primary_metric: 'tg_throughput',
  rows: [
    {
      id: 1, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'drubuntu', runner: 'ollama', gpu: '3080ti',
      run_id: null, timestamp: 1_714_300_000,
      metrics: { tg_throughput: 100 }, metadata: {}, diff_pct: 0,
    },
    {
      id: 2, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'localhost', runner: 'ollama', gpu: 'm3-max',
      run_id: null, timestamp: 1_714_300_500,
      metrics: { tg_throughput: 80 }, metadata: {}, diff_pct: -20,
    },
    {
      id: 3, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'drubuntu', runner: 'llama-server', gpu: '3080ti',
      run_id: null, timestamp: 1_714_300_900,
      metrics: { tg_throughput: 120 }, metadata: {}, diff_pct: 20,
    },
  ],
}

describe('CompareDrawer', () => {
  it('renders one card per row with the primary metric value', () => {
    render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(screen.getByText(/Compare/i)).toBeTruthy()
    expect(screen.getAllByText('100').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('120').length).toBeGreaterThanOrEqual(1)
  })

  it('renders the diff_pct labels (baseline + others)', () => {
    render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(screen.getByText('baseline')).toBeTruthy()
    expect(screen.getByText('-20.00%')).toBeTruthy()
    expect(screen.getByText('+20.00%')).toBeTruthy()
  })

  it('renders an SVG bar per row', () => {
    const { container } = render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(container.querySelectorAll('rect').length).toBe(3)
  })
})
