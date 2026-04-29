export function formatBytes(n: number | null | undefined): string {
  if (n === null || n === undefined) return '—'
  if (n < 1024) return `${n} B`
  const units = ['KiB', 'MiB', 'GiB', 'TiB']
  let v = n / 1024
  let i = 0
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024
    i++
  }
  return `${v.toFixed(1)} ${units[i]}`
}

export function formatNumber(
  n: number | null | undefined,
  precision = 2,
): string {
  if (n === null || n === undefined) return '—'
  if (Number.isInteger(n)) return String(n)
  return n.toFixed(precision)
}

export function formatRelativeTime(
  epochSeconds: number,
  nowSeconds: number = Date.now() / 1000,
): string {
  const delta = Math.max(0, nowSeconds - epochSeconds)
  if (delta < 30) return 'just now'
  if (delta < 60 * 60) return `${Math.floor(delta / 60)}m ago`
  if (delta < 60 * 60 * 24) return `${Math.floor(delta / 3600)}h ago`
  return `${Math.floor(delta / 86400)}d ago`
}
