import { useEffect, useRef } from 'preact/hooks'
import { Link } from 'wouter-preact'
import { api } from '../../api'
import { useRunWebSocket } from '../../hooks/useRunWebSocket'

const TAIL_LIMIT = 500

interface Props {
  runId: number
  onCleared: () => void
}

export function RunDetail({ runId, onCleared }: Props) {
  const { logs, status, finished, resultsImported, error } = useRunWebSocket(runId)
  const preRef = useRef<HTMLPreElement | null>(null)

  useEffect(() => {
    const el = preRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [logs])

  const visible = logs.length > TAIL_LIMIT ? logs.slice(-TAIL_LIMIT) : logs
  const cancelable = !finished && (status === 'pending' || status === 'running' || status == null)

  async function cancel() {
    try { await api.cancelRun(runId) } catch { /* WS will report */ }
  }

  return (
    <section class="border rounded p-3 space-y-3">
      <header class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h2 class="text-lg font-semibold">Run #{runId}</h2>
          <StatusBadge status={status} />
          {resultsImported > 0 && (
            <span class="text-text-muted text-sm">
              {resultsImported} result{resultsImported === 1 ? '' : 's'} imported
            </span>
          )}
        </div>
        <div class="flex items-center gap-2">
          {cancelable && (
            <button class="text-sm border rounded px-2 py-1" onClick={cancel}>
              Cancel
            </button>
          )}
          {finished && (
            <Link href={`/?run_id=${runId}`} class="text-sm text-blue-600 hover:underline">
              View results
            </Link>
          )}
          <button class="text-sm text-text-muted hover:underline" onClick={onCleared}>
            Close
          </button>
        </div>
      </header>

      {error && <div class="text-red-600 text-sm">{error}</div>}

      <pre
        ref={preRef}
        class="bg-bg-elevated border rounded p-2 text-xs font-mono whitespace-pre-wrap
               max-h-96 overflow-auto"
      >{visible.join('\n')}</pre>
    </section>
  )
}

function StatusBadge({ status }: { status: string | null }) {
  const colour = status === 'success' ? 'bg-green-600'
    : status === 'failed' ? 'bg-red-600'
    : status === 'cancelled' ? 'bg-yellow-600'
    : 'bg-blue-600'
  return (
    <span class={`text-xs uppercase tracking-wide text-white px-2 py-0.5 rounded ${colour}`}>
      {status ?? 'connecting'}
    </span>
  )
}
