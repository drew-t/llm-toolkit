interface Bar {
  label: string
  value: number
}

export function MetricBars({ bars, unit }: { bars: Bar[]; unit: string }) {
  if (bars.length === 0) return null
  const max = Math.max(...bars.map((b) => b.value), 0)
  const width = 320
  const rowH = 22
  const labelW = 140

  return (
    <svg width={width} height={bars.length * rowH + 8} role="img" aria-label="metric bars">
      {bars.map((b, i) => {
        const w = max > 0 ? ((width - labelW - 60) * b.value) / max : 0
        return (
          <g key={b.label} transform={`translate(0, ${i * rowH})`}>
            <text x={0} y={14} font-size={11} fill="var(--color-text-muted)">
              {b.label}
            </text>
            <rect
              x={labelW}
              y={4}
              width={Math.max(0, w)}
              height={14}
              fill="var(--color-accent)"
              rx={2}
            />
            <text x={labelW + Math.max(0, w) + 4} y={14} font-size={11} fill="var(--color-text)">
              {b.value} {unit}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
