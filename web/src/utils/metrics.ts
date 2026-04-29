// Mirrors PRIMARY_METRICS in src/llm_toolkit/web/routes/results.py.
const PRIMARY: Record<string, string> = {
  throughput_benchy: 'tg_throughput',
  context_scaling: 'score',
  classifier: 'score',
  coding: 'score',
}

const SECONDARY: Record<string, string | null> = {
  throughput_benchy: 'pp_throughput',
  context_scaling: null,
  classifier: null,
  coding: null,
}

export function primaryMetric(benchmark: string): string {
  return PRIMARY[benchmark] ?? 'tg_throughput'
}

export function secondaryMetric(benchmark: string): string | null {
  return benchmark in SECONDARY ? SECONDARY[benchmark] : null
}
