import { fireEvent, render, screen, waitFor } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { RunForm } from '../pages/run/RunForm'
import * as apiModule from '../api'

const HOSTS = {
  hosts: [{
    name: 'localhost',
    runners: [{
      runner: 'ollama',
      base_url: 'http://127.0.0.1:11434',
      gpu: 'm3-max',
      version: '0.5.7',
      reachable: true, error: null,
      installed_models: [{ tag: 'qwen3:8b', size_bytes: null, modified: null }],
      loaded_models: [],
      raw: {},
    }],
  }],
}

beforeEach(() => {
  vi.spyOn(apiModule.api, 'hosts').mockResolvedValue(HOSTS as any)
})
afterEach(() => vi.restoreAllMocks())

describe('RunForm', () => {
  it('lets the user submit a valid run', async () => {
    const createRun = vi.spyOn(apiModule.api, 'createRun')
      .mockResolvedValue({ id: 11, status: 'pending' } as any)
    const onCreated = vi.fn()
    render(<RunForm onCreated={onCreated} initial={null} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    fireEvent.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() => expect(createRun).toHaveBeenCalled())
    const arg = createRun.mock.calls[0][0]
    expect(arg.benchmark).toBe('throughput_benchy')
    expect(arg.host).toBe('localhost')
    expect(arg.runner).toBe('ollama')
    expect(arg.model).toBe('qwen3:8b')
    expect(arg.base_url).toContain('11434')
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(11))
  })

  it('honours initial pre-fill', async () => {
    render(<RunForm onCreated={() => {}}
      initial={{ host: 'localhost', runner: 'ollama', gpu: 'm3-max' }} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    expect((screen.getByLabelText(/host/i) as HTMLSelectElement).value).toBe('localhost')
  })

  it('disables submit while a request is in flight', async () => {
    let resolve!: (v: any) => void
    vi.spyOn(apiModule.api, 'createRun').mockImplementation(
      () => new Promise(r => { resolve = r }) as any,
    )
    render(<RunForm onCreated={() => {}} initial={null} />)
    await waitFor(() => screen.getByText(/qwen3:8b/i))
    fireEvent.click(screen.getByRole('button', { name: /run/i }))
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /running…|run/i })
        .hasAttribute('disabled')).toBe(true))
    resolve({ id: 1, status: 'pending' })
  })
})
