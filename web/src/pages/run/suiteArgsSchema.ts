export type FieldKind = 'list-int' | 'string' | 'boolean' | 'int'

export interface SuiteArgField {
  name: string
  label: string
  kind: FieldKind
  placeholder?: string
  help?: string
}

export const SUITE_ARGS: Record<string, SuiteArgField[]> = {
  throughput_benchy: [
    { name: 'pp',  label: 'pp (prompt-processing tokens)',
      kind: 'list-int', placeholder: '2048, 4096' },
    { name: 'tg',  label: 'tg (generation tokens)',
      kind: 'list-int', placeholder: '128, 256' },
    { name: 'depth', label: 'depth',
      kind: 'list-int', placeholder: '0, 4096' },
    { name: 'concurrency', label: 'concurrency',
      kind: 'list-int', placeholder: '1, 4' },
    { name: 'runs', label: 'runs', kind: 'int', placeholder: '3' },
    { name: 'tokenizer', label: 'tokenizer (HF repo)',
      kind: 'string', placeholder: 'Qwen/Qwen3-8B' },
    { name: 'served_model_name', label: 'served-model-name',
      kind: 'string' },
    { name: 'prefix_caching', label: 'enable prefix caching', kind: 'boolean' },
    { name: 'no_cache',       label: 'no cache',              kind: 'boolean' },
    { name: 'skip_coherence', label: 'skip coherence check',  kind: 'boolean' },
    { name: 'no_warmup',      label: 'no warmup',             kind: 'boolean' },
  ],
  context_scaling: [],
  classifier: [],
  coding: [],
}

export function argsForBenchmark(benchmark: string): SuiteArgField[] {
  return SUITE_ARGS[benchmark] ?? []
}

export function parseListField(raw: string): number[] | null {
  const trimmed = raw.trim()
  if (!trimmed) return null
  const parts = trimmed.split(',').map(s => s.trim()).filter(Boolean)
  const nums = parts.map(p => Number(p))
  if (nums.some(n => Number.isNaN(n))) return null
  return nums
}
