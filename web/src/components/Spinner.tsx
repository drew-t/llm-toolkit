export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div class="flex items-center gap-2 text-text-muted">
      <span
        class="inline-block h-3 w-3 animate-spin rounded-full border-2 border-text-ghost border-t-text"
        aria-hidden
      />
      <span>{label}</span>
    </div>
  )
}
