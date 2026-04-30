import { useEffect, useState } from 'preact/hooks'
import { useLocation } from 'wouter-preact'
import { RunDetail } from './run/RunDetail'
import { RunForm, type RunFormPrefill } from './run/RunForm'

function parseQuery(search: string): URLSearchParams {
  return new URLSearchParams(search)
}

export function RunPage() {
  const [location] = useLocation()
  const search = typeof window !== 'undefined' ? window.location.search : ''
  const params = parseQuery(search)
  const idParam = params.get('id')
  const [activeId, setActiveId] = useState<number | null>(
    idParam ? Number(idParam) : null,
  )
  const [prefill] = useState<RunFormPrefill | null>(() => {
    const host = params.get('host')
    const runner = params.get('runner')
    const gpu = params.get('gpu')
    const model = params.get('model')
    const benchmark = params.get('benchmark')
    if (!host && !runner && !model && !benchmark) return null
    return {
      host: host ?? undefined,
      runner: runner ?? undefined,
      gpu: gpu,
      model: model ?? undefined,
      benchmark: benchmark ?? undefined,
    }
  })

  useEffect(() => {
    if (idParam) setActiveId(Number(idParam))
  }, [location, idParam])

  return (
    <div class="p-6 space-y-6 max-w-3xl">
      <h1 class="text-xl font-semibold">Run a benchmark</h1>
      {activeId == null ? (
        <RunForm onCreated={setActiveId} initial={prefill} />
      ) : (
        <RunDetail runId={activeId} onCleared={() => setActiveId(null)} />
      )}
    </div>
  )
}
