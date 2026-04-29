export function ErrorBanner({ error }: { error: Error | string }) {
  const msg = typeof error === 'string' ? error : error.message
  return (
    <div class="rounded border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
      {msg}
    </div>
  )
}
