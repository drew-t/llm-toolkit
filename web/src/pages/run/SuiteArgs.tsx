import { argsForBenchmark, parseListField, type SuiteArgField } from './suiteArgsSchema'

interface Props {
  benchmark: string
  value: Record<string, unknown>
  onChange: (next: Record<string, unknown>) => void
}

export function SuiteArgs({ benchmark, value, onChange }: Props) {
  const fields = argsForBenchmark(benchmark)
  if (fields.length === 0) {
    return <p class="text-text-muted text-sm">No extra arguments for this suite.</p>
  }
  function set(name: string, v: unknown) {
    const next = { ...value }
    if (v === undefined || v === null || v === '') {
      delete next[name]
    } else {
      next[name] = v
    }
    onChange(next)
  }
  return (
    <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
      {fields.map(f => (
        <FieldRow key={f.name} field={f} value={value[f.name]} onChange={v => set(f.name, v)} />
      ))}
    </div>
  )
}

function FieldRow({
  field, value, onChange,
}: { field: SuiteArgField; value: unknown; onChange: (v: unknown) => void }) {
  const id = `arg-${field.name}`
  if (field.kind === 'boolean') {
    return (
      <label class="flex items-center gap-2 text-sm">
        <input id={id} type="checkbox"
               checked={Boolean(value)}
               onChange={(e: any) => onChange(e.currentTarget.checked)} />
        {field.label}
      </label>
    )
  }
  return (
    <label class="flex flex-col gap-1 text-sm">
      <span>{field.label}</span>
      <input
        id={id}
        type="text"
        class="border rounded px-2 py-1 bg-bg-base"
        placeholder={field.placeholder}
        value={renderValue(value)}
        onInput={(e: any) => {
          const raw = e.currentTarget.value as string
          if (field.kind === 'list-int') onChange(parseListField(raw))
          else if (field.kind === 'int') {
            const n = Number(raw)
            onChange(raw === '' ? undefined : Number.isNaN(n) ? null : n)
          } else {
            onChange(raw === '' ? undefined : raw)
          }
        }}
      />
    </label>
  )
}

function renderValue(v: unknown): string {
  if (v == null) return ''
  if (Array.isArray(v)) return v.join(', ')
  return String(v)
}
