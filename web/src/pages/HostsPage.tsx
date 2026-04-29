import { useHosts } from '../hooks/useHosts'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { formatBytes, formatRelativeTime } from '../utils/format'
import type { HostSnapshot, RunnerSnapshot } from '../types'
import { api } from '../api'

export function HostsPage() {
  const { data, error, loading, refresh } = useHosts()

  return (
    <div class="p-6">
      <div class="mb-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Hosts</h1>
        <button
          class="rounded border border-border bg-surface px-3 py-1 text-sm hover:bg-raised"
          onClick={() => {
            void api.refreshHosts()
              .then(() => refresh())
              .catch((err) => console.error('Refresh failed:', err))
          }}
        >
          Refresh
        </button>
      </div>
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {data.hosts.map((h) => (
            <HostCard key={h.name} host={h} />
          ))}
        </div>
      )}
    </div>
  )
}

function HostCard({ host }: { host: HostSnapshot }) {
  return (
    <section class="rounded border border-border bg-panel p-4">
      <h2 class="mb-3 text-sm font-semibold">{host.name}</h2>
      <div class="flex flex-col gap-3">
        {host.runners.map((r) => (
          <RunnerBlock key={r.base_url} snap={r} />
        ))}
      </div>
    </section>
  )
}

function RunnerBlock({ snap }: { snap: RunnerSnapshot }) {
  return (
    <div class="rounded border border-border bg-surface p-3">
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-2 text-sm">
          <span
            class={`inline-block h-2 w-2 rounded-full ${snap.reachable ? 'bg-good' : 'bg-bad'}`}
          />
          <span class="font-medium">{snap.runner}</span>
          {snap.gpu && <span class="text-text-muted">· {snap.gpu}</span>}
          {snap.version && <span class="text-text-ghost">· v{snap.version}</span>}
        </div>
        <a
          href={snap.base_url}
          target="_blank"
          rel="noreferrer"
          class="text-xs text-text-ghost hover:text-text"
        >
          {snap.base_url}
        </a>
      </div>
      {!snap.reachable && snap.error && (
        <p class="mt-2 text-xs text-bad">{snap.error}</p>
      )}
      {snap.reachable && (
        <>
          <ModelGroup label="Loaded" rows={snap.loaded_models.map((m) => {
            const parts: string[] = []
            if (m.vram_bytes) parts.push(formatBytes(m.vram_bytes))
            if (m.expires_at) parts.push(`expires ${formatRelativeTime(m.expires_at)}`)
            return { tag: m.tag, extra: parts.join(' · ') }
          })} />
          <ModelGroup label="Installed" rows={snap.installed_models.map((m) => ({
            tag: m.tag,
            extra: formatBytes(m.size_bytes),
          }))} collapsed />
        </>
      )}
    </div>
  )
}

function ModelGroup({
  label,
  rows,
  collapsed = false,
}: {
  label: string
  rows: { tag: string; extra: string }[]
  collapsed?: boolean
}) {
  if (rows.length === 0) return null
  if (collapsed) {
    return (
      <details class="mt-3">
        <summary class="cursor-pointer text-xs text-text-muted">
          {label} ({rows.length})
        </summary>
        <ModelList rows={rows} />
      </details>
    )
  }
  return (
    <div class="mt-3">
      <div class="text-xs uppercase tracking-wide text-text-ghost">{label}</div>
      <ModelList rows={rows} />
    </div>
  )
}

function ModelList({ rows }: { rows: { tag: string; extra: string }[] }) {
  return (
    <ul class="mt-1 flex flex-col gap-0.5">
      {rows.map((r) => (
        <li key={r.tag} class="flex justify-between text-xs">
          <span class="font-mono">{r.tag}</span>
          <span class="text-text-ghost">{r.extra}</span>
        </li>
      ))}
    </ul>
  )
}
