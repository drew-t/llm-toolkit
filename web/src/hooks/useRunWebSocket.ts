import { useEffect, useRef, useState } from 'preact/hooks'
import { runWsUrl } from '../api'
import type { RunEvent } from '../types'

export interface UseRunWebSocket {
  logs: string[]
  status: string | null
  finished: boolean
  resultsImported: number
  error: string | null
}

export function useRunWebSocket(id: number | null): UseRunWebSocket {
  const [logs, setLogs] = useState<string[]>([])
  const [status, setStatus] = useState<string | null>(null)
  const [finished, setFinished] = useState(false)
  const [resultsImported, setResultsImported] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    setLogs([])
    setStatus(null)
    setFinished(false)
    setResultsImported(0)
    setError(null)
    if (id == null) return

    const ws = new WebSocket(runWsUrl(id))
    wsRef.current = ws

    ws.onmessage = (ev: MessageEvent) => {
      let parsed: RunEvent
      try {
        parsed = JSON.parse(ev.data) as RunEvent
      } catch {
        return
      }
      if (parsed.type === 'log') {
        setLogs(prev => [...prev, parsed.line])
      } else if (parsed.type === 'status') {
        setStatus(parsed.status)
      } else if (parsed.type === 'finished') {
        setStatus(parsed.status)
        setResultsImported(parsed.results_imported)
        setFinished(true)
      }
    }
    ws.onerror = () => setError('WebSocket error')

    return () => {
      ws.close()
      wsRef.current = null
    }
  }, [id])

  return { logs, status, finished, resultsImported, error }
}
