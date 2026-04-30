import { act, renderHook } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useRunWebSocket } from '../hooks/useRunWebSocket'

class MockWS {
  static instances: MockWS[] = []
  url: string
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null
  closed = false
  constructor(url: string) {
    this.url = url
    MockWS.instances.push(this)
  }
  close() {
    this.closed = true
    this.onclose?.(new CloseEvent('close'))
  }
  send() {}
}

beforeEach(() => {
  MockWS.instances = []
  ;(globalThis as any).WebSocket = MockWS
})
afterEach(() => {
  vi.restoreAllMocks()
})

describe('useRunWebSocket', () => {
  it('accumulates log lines and tracks last status', () => {
    const { result } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    act(() => {
      ws.onopen?.(new Event('open'))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'status', status: 'running' }),
      }))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'log', line: 'hello' }),
      }))
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({ type: 'log', line: 'world' }),
      }))
    })
    expect(result.current.logs).toEqual(['hello', 'world'])
    expect(result.current.status).toBe('running')
  })

  it('records terminal status on finished event', () => {
    const { result } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    act(() => {
      ws.onmessage?.(new MessageEvent('message', {
        data: JSON.stringify({
          type: 'finished', status: 'success',
          exit_code: 0, results_imported: 3,
        }),
      }))
    })
    expect(result.current.status).toBe('success')
    expect(result.current.resultsImported).toBe(3)
    expect(result.current.finished).toBe(true)
  })

  it('closes the socket on unmount', () => {
    const { unmount } = renderHook(() => useRunWebSocket(7))
    const ws = MockWS.instances[0]
    unmount()
    expect(ws.closed).toBe(true)
  })

  it('does not connect when id is null', () => {
    renderHook(() => useRunWebSocket(null))
    expect(MockWS.instances).toHaveLength(0)
  })
})
