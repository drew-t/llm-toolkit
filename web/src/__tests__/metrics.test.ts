import { describe, expect, it } from 'vitest'
import { primaryMetric, secondaryMetric } from '../utils/metrics'

describe('primaryMetric', () => {
  it('returns tg_throughput for throughput_benchy', () => {
    expect(primaryMetric('throughput_benchy')).toBe('tg_throughput')
  })
  it('returns score for accuracy suites', () => {
    expect(primaryMetric('context_scaling')).toBe('score')
    expect(primaryMetric('classifier')).toBe('score')
    expect(primaryMetric('coding')).toBe('score')
  })
  it('falls back to tg_throughput for unknown suites', () => {
    expect(primaryMetric('something_new')).toBe('tg_throughput')
  })
})

describe('secondaryMetric', () => {
  it('returns pp_throughput for perf suite', () => {
    expect(secondaryMetric('throughput_benchy')).toBe('pp_throughput')
  })
  it('returns null for accuracy suites', () => {
    expect(secondaryMetric('classifier')).toBeNull()
    expect(secondaryMetric('context_scaling')).toBeNull()
  })
})
