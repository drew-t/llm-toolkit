import { renderHook, waitFor } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useApi } from '../hooks/useApi'

describe('useApi', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts in loading state and resolves', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 })
    const { result } = renderHook(() => useApi(fetcher, []))

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ value: 42 })
    expect(result.current.error).toBeNull()
  })

  it('captures errors', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useApi(fetcher, []))

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.error?.message).toBe('boom')
  })

  it('refetches when refresh() is called', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ n: 1 })
      .mockResolvedValueOnce({ n: 2 })
    const { result } = renderHook(() => useApi(fetcher, []))

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }))

    const refreshPromise = result.current.refresh()
    await vi.runAllTimersAsync()
    await refreshPromise
    await waitFor(() => expect(result.current.data).toEqual({ n: 2 }))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
