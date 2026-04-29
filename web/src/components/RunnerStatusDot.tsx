import type { RunnerSnapshot } from '../types'

export function RunnerStatusDot({ snap }: { snap: RunnerSnapshot }) {
  const color = snap.reachable ? 'bg-good' : 'bg-bad'
  const title = snap.reachable
    ? `${snap.runner} reachable${snap.version ? ` (${snap.version})` : ''}`
    : `${snap.runner} unreachable: ${snap.error ?? 'unknown error'}`
  return <span class={`inline-block h-2 w-2 rounded-full ${color}`} title={title} />
}
