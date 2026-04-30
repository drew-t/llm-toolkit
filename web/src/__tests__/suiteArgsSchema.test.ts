import { describe, expect, it } from 'vitest'
import { argsForBenchmark, parseListField, SUITE_ARGS } from '../pages/run/suiteArgsSchema'

describe('suiteArgsSchema', () => {
  it('exposes throughput_benchy fields', () => {
    expect(argsForBenchmark('throughput_benchy').map(f => f.name))
      .toEqual(expect.arrayContaining(['pp', 'tg', 'concurrency', 'tokenizer']))
  })

  it('returns empty list for accuracy benchmarks', () => {
    expect(argsForBenchmark('context_scaling')).toEqual([])
  })

  it('parses list fields from comma-separated input', () => {
    expect(parseListField('2048, 4096')).toEqual([2048, 4096])
    expect(parseListField('')).toEqual(null)
    expect(parseListField('abc')).toEqual(null)
  })

  it('SUITE_ARGS keys match known benchmarks', () => {
    expect(Object.keys(SUITE_ARGS)).toEqual(
      expect.arrayContaining([
        'throughput_benchy', 'context_scaling', 'classifier', 'coding',
      ]),
    )
  })
})
