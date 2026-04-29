import { Link, useLocation } from 'wouter-preact'
import clsx from 'clsx'
import { useHosts } from '../hooks/useHosts'
import { RunnerStatusDot } from './RunnerStatusDot'

const NAV = [
  { href: '/', label: 'Results' },
  { href: '/hosts', label: 'Hosts' },
  { href: '/run', label: 'Run' },
  { href: '/models', label: 'Models' },
]

export function Sidebar() {
  const [location] = useLocation()
  const { data, error } = useHosts()

  return (
    <aside class="flex w-60 flex-col border-r border-border bg-panel">
      <div class="px-4 py-3 text-sm font-semibold tracking-wide text-text-muted">
        llm-toolkit
      </div>
      <nav class="flex flex-col">
        {NAV.map((item) => {
          const active = location === item.href || (item.href !== '/' && location.startsWith(item.href + '/'))
          return (
            <Link
              key={item.href}
              href={item.href}
              class={clsx(
                'px-4 py-2 text-sm',
                active ? 'bg-surface text-text' : 'text-text-muted hover:bg-surface',
              )}
            >
              {item.label}
            </Link>
          )
        })}
      </nav>
      <div class="mt-4 border-t border-border px-4 py-2 text-xs uppercase tracking-wide text-text-ghost">
        Hosts
      </div>
      <div class="flex-1 overflow-y-auto px-2 pb-2">
        {error && <div class="px-2 py-1 text-xs text-bad">{error.message}</div>}
        {data?.hosts.map((h) => (
          <div key={h.name} class="px-2 py-1">
            <div class="text-xs text-text">{h.name}</div>
            {h.runners.map((r) => (
              <div key={r.base_url} class="flex items-center gap-2 pl-2 py-0.5 text-xs text-text-muted">
                <RunnerStatusDot snap={r} />
                <span>{r.runner}</span>
                {r.gpu && <span class="text-text-ghost">· {r.gpu}</span>}
              </div>
            ))}
          </div>
        ))}
      </div>
    </aside>
  )
}
