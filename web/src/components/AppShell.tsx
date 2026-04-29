import type { ComponentChildren } from 'preact'
import { Sidebar } from './Sidebar'

export function AppShell({ children }: { children: ComponentChildren }) {
  return (
    <div class="flex h-full w-full">
      <Sidebar />
      <main class="flex-1 overflow-y-auto bg-bg">{children}</main>
    </div>
  )
}
