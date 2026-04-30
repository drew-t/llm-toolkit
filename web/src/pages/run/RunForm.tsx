import { useEffect, useMemo, useState } from 'preact/hooks'
import { api } from '../../api'
import type { HostsResponse, ModelInfo } from '../../types'
import { SuiteArgs } from './SuiteArgs'

const BENCHMARKS = [
  'throughput_benchy', 'context_scaling', 'classifier', 'coding',
] as const

export interface RunFormPrefill {
  host?: string
  runner?: string
  gpu?: string | null
  model?: string
  benchmark?: string
}

interface Props {
  onCreated: (runId: number) => void
  initial: RunFormPrefill | null
  disabled?: boolean
}

export function RunForm({ onCreated, initial, disabled }: Props) {
  const [hosts, setHosts] = useState<HostsResponse | null>(null)
  const [benchmark, setBenchmark] = useState<string>(initial?.benchmark ?? 'throughput_benchy')
  const [hostState, setHostState] = useState<string>(initial?.host ?? '')
  const [runnerState, setRunnerState] = useState<string>(initial?.runner ?? '')
  const [gpuState, setGpuState] = useState<string | null>(initial?.gpu ?? null)
  const [modelState, setModelState] = useState<string>(initial?.model ?? '')
  const [args, setArgs] = useState<Record<string, unknown>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => { void api.hosts().then(setHosts).catch(e => setError(String(e))) }, [])

  // Effective values: fall back to first available option when state is empty
  const hostNames = hosts?.hosts.map(h => h.name) ?? []
  const host = hostState || hostNames[0] || ''

  const selectedHost = useMemo(
    () => hosts?.hosts.find(h => h.name === host) ?? null, [hosts, host])
  const runners = selectedHost?.runners ?? []

  // Derive effective runner/gpu: use state if set, otherwise first runner
  const runnerKey = runnerState
    ? `${runnerState}|${gpuState ?? ''}`
    : runners[0] ? `${runners[0].runner}|${runners[0].gpu ?? ''}` : ''
  const [runner, gpu] = runnerKey
    ? [runnerKey.split('|')[0], runnerKey.split('|')[1] || null]
    : ['', null]

  const selectedRunner = useMemo(
    () => runners.find(r => r.runner === runner && (gpu == null || r.gpu === gpu)) ?? null,
    [runners, runner, gpu])
  const models: ModelInfo[] = selectedRunner?.installed_models ?? []

  // Effective model: use state if set, otherwise first model
  const model = modelState || models[0]?.tag || ''

  // Keep state in sync for controlled selects (only when empty + default available)
  useEffect(() => {
    if (!hostState && hostNames[0]) setHostState(hostNames[0])
  }, [hostState, hostNames.join(',')])
  useEffect(() => {
    if (!runnerState && runners[0]) {
      setRunnerState(runners[0].runner)
      setGpuState(runners[0].gpu ?? null)
    }
  }, [runnerState, runners])
  useEffect(() => {
    if (!modelState && models[0]) setModelState(models[0].tag)
  }, [modelState, models])

  async function submit() {
    if (!selectedRunner) return
    setSubmitting(true)
    setError(null)
    try {
      const resp = await api.createRun({
        benchmark, model, host, runner,
        gpu: selectedRunner.gpu,
        base_url: selectedRunner.base_url,
        args,
      })
      onCreated(resp.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form class="space-y-4" onSubmit={(e: any) => { e.preventDefault(); void submit() }}>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
        <Field label="Suite">
          <select value={benchmark} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => setBenchmark(e.currentTarget.value)}>
            {BENCHMARKS.map(b => <option key={b} value={b}>{b}</option>)}
          </select>
        </Field>
        <Field label="Host">
          <select value={host} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => {
                    setHostState(e.currentTarget.value)
                    setRunnerState(''); setGpuState(null); setModelState('')
                  }}>
            {hostNames.map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </Field>
        <Field label="Runner">
          <select value={runnerKey} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => {
                    const [rt, g] = String(e.currentTarget.value).split('|')
                    setRunnerState(rt); setGpuState(g || null); setModelState('')
                  }}>
            {runners.map(r => (
              <option key={`${r.runner}|${r.gpu ?? ''}`}
                      value={`${r.runner}|${r.gpu ?? ''}`}>
                {r.runner}{r.gpu ? ` · ${r.gpu}` : ''}
                {r.reachable ? '' : ' (unreachable)'}
              </option>
            ))}
          </select>
        </Field>
        <Field label="Model">
          <select value={model} class="border rounded px-2 py-1 bg-bg-base"
                  onChange={(e: any) => setModelState(e.currentTarget.value)}>
            {models.map(m => <option key={m.tag} value={m.tag}>{m.tag}</option>)}
          </select>
        </Field>
      </div>

      <div>
        <h3 class="text-sm font-semibold mb-2">Suite arguments</h3>
        <SuiteArgs benchmark={benchmark} value={args} onChange={setArgs} />
      </div>

      {error && <div class="text-red-600 text-sm">{error}</div>}

      <button
        type="submit"
        class="bg-blue-600 text-white px-4 py-2 rounded disabled:opacity-50"
        disabled={disabled || submitting || !host || !runner || !model}
      >
        {submitting ? 'Running…' : 'Run'}
      </button>
    </form>
  )
}

function Field({ label, children }: { label: string; children: any }) {
  return (
    <label class="flex flex-col gap-1 text-sm">
      <span class="text-text-muted">{label}</span>
      {children}
    </label>
  )
}
