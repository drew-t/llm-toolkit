import { describe, expect, it } from 'vitest'
import { formatBytes, formatNumber, formatRelativeTime } from '../utils/format'

describe('formatBytes', () => {
  it('returns "—" for null', () => {
    expect(formatBytes(null)).toBe('—')
  })
  it('formats bytes under 1KiB', () => {
    expect(formatBytes(512)).toBe('512 B')
  })
  it('formats KiB', () => {
    expect(formatBytes(2048)).toBe('2.0 KiB')
  })
  it('formats MiB', () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MiB')
  })
  it('formats GiB', () => {
    expect(formatBytes(7 * 1024 ** 3)).toBe('7.0 GiB')
  })
})

describe('formatNumber', () => {
  it('returns "—" for null/undefined', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
  })
  it('rounds to 2 fraction digits by default', () => {
    expect(formatNumber(3.14159)).toBe('3.14')
  })
  it('respects precision option', () => {
    expect(formatNumber(3.14159, 4)).toBe('3.1416')
  })
  it('does not pad integers', () => {
    expect(formatNumber(42)).toBe('42')
  })
})

describe('formatRelativeTime', () => {
  it('says "just now" for <30s ago', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 5, now)).toBe('just now')
  })
  it('formats minutes', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 90, now)).toBe('1m ago')
    expect(formatRelativeTime(now - 60 * 12, now)).toBe('12m ago')
  })
  it('formats hours', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 60 * 60 * 3, now)).toBe('3h ago')
  })
  it('formats days', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 60 * 60 * 24 * 5, now)).toBe('5d ago')
  })
})
