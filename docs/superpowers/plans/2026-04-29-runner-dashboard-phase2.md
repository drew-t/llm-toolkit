# Runner Dashboard — Phase 2: Preact Frontend

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the read-only browser UI on top of the Phase 1 REST API. After this phase, `llm-toolkit ui` opens a usable dashboard at `http://127.0.0.1:7860/` with four pages: Hosts, Results (default), Run (placeholder), and Models. The Run page lights up in Phase 3 when the job runner and WebSocket land.

**Architecture:** A Vite-built Preact + TypeScript SPA lives at `web/` in the repo root. `npm run build` emits to `web/dist/`. FastAPI mounts that directory at `/` with a single-page-app fallback (any unknown non-`/api` route returns `index.html`). In dev, `vite dev` runs on `:5173` and proxies `/api` and `/ws` to the FastAPI server on `:7860`. Routing in the SPA uses `wouter-preact`; the Results table uses TanStack Table via the existing `preact/compat` alias trick. The Compare bar chart is hand-rolled SVG — no chart library.

**Tech Stack:** Preact 10, Vite 8, Tailwind v4 (`@tailwindcss/vite`), TypeScript 5.9, `wouter-preact`, `@tanstack/react-table`, Vitest + `@testing-library/preact` for unit tests.

**Out of scope (deferred to Phase 3):** Run page form, `POST /api/runs`, `DELETE /api/runs/{id}`, `WS /ws/runs/{id}`, the in-process asyncio job queue, the per-runner "Run benchmark" button on Hosts cards (it would prefill a form that does not exist yet), and the per-row "log viewer" link on Results (logs are produced by the Phase 3 job runner). The Run route renders a "coming in Phase 3" placeholder.

---

## File structure (Phase 2)

**New frontend files (all under `web/`):**

```
web/
  package.json
  package-lock.json            (generated)
  index.html
  vite.config.ts
  tsconfig.json
  tsconfig.app.json
  tsconfig.node.json
  vitest.config.ts
  .gitignore
  src/
    main.tsx                   Preact mount + global CSS import
    app.tsx                    Router + AppShell
    index.css                  Tailwind v4 + @theme tokens
    api.ts                     fetch wrappers (typed)
    types.ts                   TS shapes mirroring backend JSON
    hooks/
      useApi.ts                generic fetch+refresh hook
      useHosts.ts
      useResults.ts
      useModels.ts
    components/
      Sidebar.tsx              nav + collapsible host status
      RunnerStatusDot.tsx      red/green dot + tooltip
      AppShell.tsx             sidebar + main layout
      Spinner.tsx
      ErrorBanner.tsx
    pages/
      HostsPage.tsx
      ModelsPage.tsx
      RunPage.tsx              Phase-3 placeholder
      ResultsPage.tsx
      results/
        ResultsTable.tsx
        ResultsFilters.tsx
        CompareDrawer.tsx
        MetricBars.tsx         hand-rolled SVG
    utils/
      format.ts                bytes / relative time / numbers
      metrics.ts               primary-metric picker (mirrors backend)
    __tests__/
      format.test.ts
      metrics.test.ts
      useApi.test.tsx
      ResultsTable.test.tsx
      CompareDrawer.test.tsx
```

**Modified Python files:**
- `src/llm_toolkit/web/app.py` — mount `web/dist/` with SPA fallback when the directory exists.
- `tests/web/test_app.py` — add tests for the static mount + SPA fallback.

**Modified config:**
- `.gitignore` (repo root) — add `web/node_modules/`, `web/dist/`, `web/.vite/`, `web/coverage/`.

---

## Task 1: gitignore the frontend artifacts

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Append frontend ignore patterns**

Open `.gitignore` and append these lines at the bottom (preserve existing content):

```gitignore
web/node_modules/
web/dist/
web/.vite/
web/coverage/
```

- [ ] **Step 2: Verify**

Run: `git check-ignore -v web/node_modules/foo web/dist/index.html`
Expected: both paths report as ignored (output shows the `.gitignore` line that matched).

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: gitignore frontend build artifacts under web/"
```

---

## Task 2: Scaffold the Vite project (package.json, tsconfig, vite, index.html)

**Files:**
- Create: `web/package.json`
- Create: `web/index.html`
- Create: `web/vite.config.ts`
- Create: `web/tsconfig.json`
- Create: `web/tsconfig.app.json`
- Create: `web/tsconfig.node.json`
- Create: `web/vitest.config.ts`
- Create: `web/.gitignore` (npm conventions)

- [ ] **Step 1: Create `web/package.json`**

```json
{
  "name": "llm-toolkit-web",
  "private": true,
  "version": "0.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "@tanstack/react-table": "^8.20.5",
    "clsx": "^2.1.1",
    "preact": "^10.29.0",
    "wouter-preact": "^3.3.5"
  },
  "devDependencies": {
    "@preact/preset-vite": "^2.10.4",
    "@tailwindcss/vite": "^4.2.2",
    "@testing-library/preact": "^3.2.4",
    "@types/node": "^24.12.0",
    "jsdom": "^25.0.1",
    "tailwindcss": "^4.2.2",
    "typescript": "~5.9.3",
    "vite": "^8.0.1",
    "vitest": "^2.1.5"
  }
}
```

- [ ] **Step 2: Create `web/vite.config.ts`**

```ts
import { defineConfig } from 'vite'
import preact from '@preact/preset-vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [preact(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: 'http://127.0.0.1:7860' },
      '/ws':  { target: 'ws://127.0.0.1:7860', ws: true },
    },
  },
  build: { outDir: 'dist', emptyOutDir: true },
})
```

- [ ] **Step 3: Create `web/tsconfig.json`**

```json
{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
```

- [ ] **Step 4: Create `web/tsconfig.app.json`**

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.app.tsbuildinfo",
    "target": "ES2023",
    "module": "ESNext",
    "lib": ["ES2023", "DOM", "DOM.Iterable"],
    "types": ["vite/client", "vitest/globals"],
    "skipLibCheck": true,
    "paths": {
      "react": ["./node_modules/preact/compat/"],
      "react-dom": ["./node_modules/preact/compat/"]
    },
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "jsxImportSource": "preact",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["src"]
}
```

- [ ] **Step 5: Create `web/tsconfig.node.json`**

```json
{
  "compilerOptions": {
    "tsBuildInfoFile": "./node_modules/.tmp/tsconfig.node.tsbuildinfo",
    "target": "ES2023",
    "module": "ESNext",
    "lib": ["ES2023"],
    "types": ["node"],
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "verbatimModuleSyntax": true,
    "moduleDetection": "force",
    "noEmit": true,
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "erasableSyntaxOnly": true,
    "noFallthroughCasesInSwitch": true,
    "noUncheckedSideEffectImports": true
  },
  "include": ["vite.config.ts", "vitest.config.ts"]
}
```

- [ ] **Step 6: Create `web/vitest.config.ts`**

```ts
import { defineConfig, mergeConfig } from 'vitest/config'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      globals: true,
      environment: 'jsdom',
      include: ['src/**/*.{test,spec}.{ts,tsx}'],
    },
    resolve: {
      alias: {
        react: 'preact/compat',
        'react-dom': 'preact/compat',
      },
    },
  }),
)
```

- [ ] **Step 7: Create `web/index.html`**

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>llm-toolkit</title>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 8: Install and verify the build pipeline**

Run: `cd web && npm install`
Expected: installs cleanly, produces `web/package-lock.json` and `web/node_modules/`.

Run: `cd web && npx tsc -b`
Expected: zero output (success). The `src/` directory is empty so there's nothing to type-check yet — but the project references must resolve.

- [ ] **Step 9: Commit**

```bash
git add web/package.json web/package-lock.json web/index.html web/vite.config.ts \
        web/tsconfig.json web/tsconfig.app.json web/tsconfig.node.json web/vitest.config.ts
git commit -m "feat(web): scaffold Vite + Preact + Tailwind project at web/"
```

---

## Task 3: Global CSS theme + minimal main.tsx + placeholder app.tsx

**Files:**
- Create: `web/src/index.css`
- Create: `web/src/main.tsx`
- Create: `web/src/app.tsx`

- [ ] **Step 1: Create `web/src/index.css`**

```css
@import "tailwindcss";

@theme {
  --color-bg: #0d0e12;
  --color-panel: #15171d;
  --color-surface: #1b1d25;
  --color-raised: #23252f;
  --color-border: #2a2c37;
  --color-text: #d6d6df;
  --color-text-muted: #8c8c99;
  --color-text-ghost: #5a5a66;
  --color-accent: #6db3ff;
  --color-good: #4ade80;
  --color-bad: #f87171;
  --color-warn: #fbbf24;

  --font-mono: ui-monospace, "JetBrains Mono", Menlo, monospace;
  --font-sans: ui-sans-serif, system-ui, sans-serif;
}

html, body, #app {
  height: 100%;
}

body {
  font-family: var(--font-sans);
  background: var(--color-bg);
  color: var(--color-text);
  -webkit-font-smoothing: antialiased;
}

#app {
  display: flex;
  min-height: 100dvh;
}
```

- [ ] **Step 2: Create `web/src/main.tsx`**

```tsx
import { render } from 'preact'
import './index.css'
import { App } from './app'

const root = document.getElementById('app')
if (!root) throw new Error('#app element missing from index.html')
render(<App />, root)
```

- [ ] **Step 3: Create `web/src/app.tsx`** (placeholder; replaced in Task 8)

```tsx
export function App() {
  return (
    <main class="m-auto p-8 text-center">
      <h1 class="text-2xl font-semibold">llm-toolkit</h1>
      <p class="text-text-muted mt-2">Bootstrapping…</p>
    </main>
  )
}
```

- [ ] **Step 4: Verify build**

Run: `cd web && npm run build`
Expected: `web/dist/index.html` and `web/dist/assets/*.js` and `web/dist/assets/*.css` are produced; no TS errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/index.css web/src/main.tsx web/src/app.tsx
git commit -m "feat(web): add Tailwind theme tokens and Preact entrypoint"
```

---

## Task 4: Static-file mount on FastAPI with SPA fallback

**Files:**
- Modify: `src/llm_toolkit/web/app.py`
- Modify: `tests/web/test_app.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/web/test_app.py`:

```python
def test_serves_spa_index_when_dist_present(tmp_path, monkeypatch):
    """When web/dist/index.html exists at the resolved location, GET / returns it."""
    from fastapi.testclient import TestClient

    from llm_toolkit.web import app as app_module

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text("<html><body>SPA</body></html>")
    (fake_dist / "assets").mkdir()
    (fake_dist / "assets" / "x.js").write_text("console.log('x')")

    monkeypatch.setattr(app_module, "_resolve_web_dist", lambda: fake_dist)

    db_path = tmp_path / "results.db"
    hosts_path = tmp_path / "hosts.toml"
    hosts_path.write_text("")

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path)
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    assert "SPA" in r.text

    r = client.get("/assets/x.js")
    assert r.status_code == 200
    assert "console.log" in r.text


def test_spa_fallback_for_unknown_route(tmp_path, monkeypatch):
    """Unknown non-/api routes return index.html so client routing works."""
    from fastapi.testclient import TestClient

    from llm_toolkit.web import app as app_module

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text("<html><body>SPA</body></html>")
    monkeypatch.setattr(app_module, "_resolve_web_dist", lambda: fake_dist)

    db_path = tmp_path / "results.db"
    hosts_path = tmp_path / "hosts.toml"
    hosts_path.write_text("")

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path)
    client = TestClient(app)

    r = client.get("/results")
    assert r.status_code == 200
    assert "SPA" in r.text


def test_api_routes_take_priority_over_spa(tmp_path, monkeypatch):
    """A real /api/* route must not be shadowed by the SPA fallback."""
    from fastapi.testclient import TestClient

    from llm_toolkit.web import app as app_module

    fake_dist = tmp_path / "dist"
    fake_dist.mkdir()
    (fake_dist / "index.html").write_text("<html>SPA</html>")
    monkeypatch.setattr(app_module, "_resolve_web_dist", lambda: fake_dist)

    db_path = tmp_path / "results.db"
    hosts_path = tmp_path / "hosts.toml"
    hosts_path.write_text("")

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path)
    client = TestClient(app)

    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_works_without_dist_dir(tmp_path, monkeypatch):
    """When web/dist/ is missing (dev mode), the API still works; / returns 404."""
    from fastapi.testclient import TestClient

    from llm_toolkit.web import app as app_module

    monkeypatch.setattr(app_module, "_resolve_web_dist", lambda: tmp_path / "nonexistent")

    db_path = tmp_path / "results.db"
    hosts_path = tmp_path / "hosts.toml"
    hosts_path.write_text("")

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path)
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/web/test_app.py -v`
Expected: the four new tests fail (`AttributeError: module 'llm_toolkit.web.app' has no attribute '_resolve_web_dist'` or similar).

- [ ] **Step 3: Implement static mount in `src/llm_toolkit/web/app.py`**

Replace the whole file with:

```python
"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

import llm_toolkit
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from llm_toolkit.db import DEFAULT_DB_PATH, init_db
from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
from llm_toolkit.web.deps import make_context


def _resolve_web_dist() -> Path:
    """Locate web/dist/ relative to the installed package (repo root in dev)."""
    return Path(llm_toolkit.__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    hosts_path: Path | str = DEFAULT_HOSTS_PATH,
) -> FastAPI:
    db = Path(db_path)
    hosts = Path(hosts_path)
    init_db(db)

    app = FastAPI(title="llm-toolkit")
    app.state.ctx = make_context(db_path=db, hosts_path=hosts)

    from llm_toolkit.web.routes import hosts as hosts_routes
    app.include_router(hosts_routes.router)

    from llm_toolkit.web.routes import results as results_routes
    app.include_router(results_routes.router)

    from llm_toolkit.web.routes import runs as runs_routes
    app.include_router(runs_routes.router)

    from llm_toolkit.web.routes import models as models_routes
    app.include_router(models_routes.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    dist = _resolve_web_dist()
    index_html = dist / "index.html"
    if index_html.exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(index_html)

    return app
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/web/test_app.py -v`
Expected: all tests in `test_app.py` pass (the four new ones plus pre-existing ones).

- [ ] **Step 5: Run full Python suite to confirm no regressions**

Run: `uv run pytest -q`
Expected: all 109+ tests pass; ruff still clean (`uv run ruff check src/ tests/`).

- [ ] **Step 6: Commit**

```bash
git add src/llm_toolkit/web/app.py tests/web/test_app.py
git commit -m "feat(web): mount web/dist with SPA fallback when present"
```

---

## Task 5: Shared TS types + API client

**Files:**
- Create: `web/src/types.ts`
- Create: `web/src/api.ts`

- [ ] **Step 1: Create `web/src/types.ts`**

```ts
// Mirrors backend JSON shapes. Keep in sync with src/llm_toolkit/web/routes/*.

export interface ModelInfo {
  tag: string
  size_bytes: number | null
  modified: number | null
}

export interface LoadedModel {
  tag: string
  vram_bytes: number | null
  expires_at: number | null
}

export interface RunnerSnapshot {
  runner: string
  base_url: string
  gpu: string | null
  version: string | null
  reachable: boolean
  error: string | null
  installed_models: ModelInfo[]
  loaded_models: LoadedModel[]
  raw: Record<string, unknown>
}

export interface HostSnapshot {
  name: string
  runners: RunnerSnapshot[]
}

export interface HostsResponse {
  hosts: HostSnapshot[]
}

export interface ResultRow {
  id: number
  benchmark: string
  model: string
  host: string | null
  runner: string | null
  gpu: string | null
  run_id: number | null
  timestamp: number
  metrics: Record<string, number | string | null>
  metadata: Record<string, unknown>
}

export interface ResultsResponse {
  results: ResultRow[]
}

export interface CompareRow extends ResultRow {
  diff_pct: number | null
}

export interface CompareResponse {
  primary_metric: string
  rows: CompareRow[]
}

export interface RunRow {
  id: number
  status: 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
  benchmark: string
  model: string
  host: string | null
  runner: string | null
  gpu: string | null
  runner_version: string | null
  args?: unknown
  config?: unknown
  started_at: number | null
  finished_at: number | null
  exit_code: number | null
  log_path: string | null
}

export interface RunsResponse {
  runs: RunRow[]
}

export interface ModelIndexRow {
  tag: string
  host: string
  runner: string
  gpu: string | null
  loaded: boolean
  size_bytes: number | null
}

export interface ModelsResponse {
  models: ModelIndexRow[]
}

export interface ResultsQuery {
  benchmark?: string
  model?: string
  host?: string
  runner?: string
  gpu?: string
  since?: number
  sort?: 'timestamp' | 'benchmark' | 'model' | 'host' | 'runner' | 'gpu'
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}
```

- [ ] **Step 2: Create `web/src/api.ts`**

```ts
import type {
  CompareResponse,
  HostsResponse,
  ModelsResponse,
  ResultRow,
  ResultsQuery,
  ResultsResponse,
  RunsResponse,
} from './types'

async function getJson<T>(url: string, init?: RequestInit): Promise<T> {
  const r = await fetch(url, init)
  if (!r.ok) {
    const body = await r.text().catch(() => '')
    throw new Error(`${r.status} ${r.statusText}: ${body || url}`)
  }
  return r.json() as Promise<T>
}

function qs(params: Record<string, string | number | undefined>): string {
  const usp = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== '') usp.set(k, String(v))
  }
  const s = usp.toString()
  return s ? `?${s}` : ''
}

export const api = {
  hosts: () => getJson<HostsResponse>('/api/hosts'),
  refreshHosts: () => getJson<HostsResponse>('/api/hosts/refresh', { method: 'POST' }),

  results: (q: ResultsQuery = {}) => getJson<ResultsResponse>(`/api/results${qs(q)}`),
  result: (id: number) => getJson<ResultRow>(`/api/results/${id}`),
  compare: (ids: number[]) =>
    getJson<CompareResponse>('/api/results/compare', {
      method: 'POST',
      headers: { 'content-type': 'application/json' },
      body: JSON.stringify({ ids }),
    }),

  runs: (q: { status?: string; limit?: number; offset?: number } = {}) =>
    getJson<RunsResponse>(`/api/runs${qs(q)}`),

  models: () => getJson<ModelsResponse>('/api/models'),
}
```

- [ ] **Step 3: Type-check**

Run: `cd web && npx tsc -b`
Expected: zero errors.

- [ ] **Step 4: Commit**

```bash
git add web/src/types.ts web/src/api.ts
git commit -m "feat(web): add typed API client + JSON shapes mirroring backend"
```

---

## Task 6: Format + metrics utilities (TDD)

**Files:**
- Create: `web/src/utils/format.ts`
- Create: `web/src/utils/metrics.ts`
- Create: `web/src/__tests__/format.test.ts`
- Create: `web/src/__tests__/metrics.test.ts`

- [ ] **Step 1: Write the failing tests for format.ts**

Create `web/src/__tests__/format.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { formatBytes, formatNumber, formatRelativeTime } from '../utils/format'

describe('formatBytes', () => {
  it('returns "—" for null', () => {
    expect(formatBytes(null)).toBe('—')
  })
  it('formats bytes under 1KiB', () => {
    expect(formatBytes(512)).toBe('512 B')
  })
  it('formats KiB', () => {
    expect(formatBytes(2048)).toBe('2.0 KiB')
  })
  it('formats MiB', () => {
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MiB')
  })
  it('formats GiB', () => {
    expect(formatBytes(7 * 1024 ** 3)).toBe('7.0 GiB')
  })
})

describe('formatNumber', () => {
  it('returns "—" for null/undefined', () => {
    expect(formatNumber(null)).toBe('—')
    expect(formatNumber(undefined)).toBe('—')
  })
  it('rounds to 2 fraction digits by default', () => {
    expect(formatNumber(3.14159)).toBe('3.14')
  })
  it('respects precision option', () => {
    expect(formatNumber(3.14159, 4)).toBe('3.1416')
  })
  it('does not pad integers', () => {
    expect(formatNumber(42)).toBe('42')
  })
})

describe('formatRelativeTime', () => {
  it('says "just now" for <30s ago', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 5, now)).toBe('just now')
  })
  it('formats minutes', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 90, now)).toBe('1m ago')
    expect(formatRelativeTime(now - 60 * 12, now)).toBe('12m ago')
  })
  it('formats hours', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 60 * 60 * 3, now)).toBe('3h ago')
  })
  it('formats days', () => {
    const now = Date.now() / 1000
    expect(formatRelativeTime(now - 60 * 60 * 24 * 5, now)).toBe('5d ago')
  })
})
```

- [ ] **Step 2: Write the failing tests for metrics.ts**

Create `web/src/__tests__/metrics.test.ts`:

```ts
import { describe, expect, it } from 'vitest'
import { primaryMetric, secondaryMetric } from '../utils/metrics'

describe('primaryMetric', () => {
  it('returns tg_throughput for throughput_benchy', () => {
    expect(primaryMetric('throughput_benchy')).toBe('tg_throughput')
  })
  it('returns score for accuracy suites', () => {
    expect(primaryMetric('context_scaling')).toBe('score')
    expect(primaryMetric('classifier')).toBe('score')
    expect(primaryMetric('coding')).toBe('score')
  })
  it('falls back to tg_throughput for unknown suites', () => {
    expect(primaryMetric('something_new')).toBe('tg_throughput')
  })
})

describe('secondaryMetric', () => {
  it('returns pp_throughput for perf suite', () => {
    expect(secondaryMetric('throughput_benchy')).toBe('pp_throughput')
  })
  it('returns null for accuracy suites', () => {
    expect(secondaryMetric('classifier')).toBeNull()
    expect(secondaryMetric('context_scaling')).toBeNull()
  })
})
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `cd web && npm test`
Expected: tests fail with module-not-found errors for `../utils/format` and `../utils/metrics`.

- [ ] **Step 4: Implement `web/src/utils/format.ts`**

```ts
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
```

- [ ] **Step 5: Implement `web/src/utils/metrics.ts`**

```ts
// Mirrors PRIMARY_METRICS in src/llm_toolkit/web/routes/results.py.
const PRIMARY: Record<string, string> = {
  throughput_benchy: 'tg_throughput',
  context_scaling: 'score',
  classifier: 'score',
  coding: 'score',
}

const SECONDARY: Record<string, string | null> = {
  throughput_benchy: 'pp_throughput',
  context_scaling: null,
  classifier: null,
  coding: null,
}

export function primaryMetric(benchmark: string): string {
  return PRIMARY[benchmark] ?? 'tg_throughput'
}

export function secondaryMetric(benchmark: string): string | null {
  return benchmark in SECONDARY ? SECONDARY[benchmark] : null
}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd web && npm test`
Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add web/src/utils/ web/src/__tests__/format.test.ts web/src/__tests__/metrics.test.ts
git commit -m "feat(web): add format + metrics utils with vitest coverage"
```

---

## Task 7: useApi hook (TDD)

**Files:**
- Create: `web/src/hooks/useApi.ts`
- Create: `web/src/__tests__/useApi.test.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/__tests__/useApi.test.tsx`:

```tsx
import { renderHook, waitFor } from '@testing-library/preact'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useApi } from '../hooks/useApi'

describe('useApi', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('starts in loading state and resolves', async () => {
    const fetcher = vi.fn().mockResolvedValue({ value: 42 })
    const { result } = renderHook(() => useApi(fetcher, []))

    expect(result.current.loading).toBe(true)
    expect(result.current.data).toBeNull()

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toEqual({ value: 42 })
    expect(result.current.error).toBeNull()
  })

  it('captures errors', async () => {
    const fetcher = vi.fn().mockRejectedValue(new Error('boom'))
    const { result } = renderHook(() => useApi(fetcher, []))

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(result.current.data).toBeNull()
    expect(result.current.error?.message).toBe('boom')
  })

  it('refetches when refresh() is called', async () => {
    const fetcher = vi.fn()
      .mockResolvedValueOnce({ n: 1 })
      .mockResolvedValueOnce({ n: 2 })
    const { result } = renderHook(() => useApi(fetcher, []))

    await vi.runAllTimersAsync()
    await waitFor(() => expect(result.current.data).toEqual({ n: 1 }))

    await result.current.refresh()
    await waitFor(() => expect(result.current.data).toEqual({ n: 2 }))
    expect(fetcher).toHaveBeenCalledTimes(2)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- useApi`
Expected: fails — module `../hooks/useApi` not found.

- [ ] **Step 3: Implement `web/src/hooks/useApi.ts`**

```ts
import { useCallback, useEffect, useRef, useState } from 'preact/hooks'

export interface ApiState<T> {
  data: T | null
  error: Error | null
  loading: boolean
  refresh: () => Promise<void>
}

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: ReadonlyArray<unknown>,
): ApiState<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<Error | null>(null)
  const [loading, setLoading] = useState(true)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const run = useCallback(async () => {
    setLoading(true)
    try {
      const v = await fetcherRef.current()
      setData(v)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e : new Error(String(e)))
    } finally {
      setLoading(false)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    void run()
  }, [run])

  return { data, error, loading, refresh: run }
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test -- useApi`
Expected: all three tests pass.

- [ ] **Step 5: Commit**

```bash
git add web/src/hooks/useApi.ts web/src/__tests__/useApi.test.tsx
git commit -m "feat(web): add useApi hook (loading + error + refresh)"
```

---

## Task 8: AppShell + Sidebar + wouter routing skeleton

**Files:**
- Create: `web/src/components/Spinner.tsx`
- Create: `web/src/components/ErrorBanner.tsx`
- Create: `web/src/components/RunnerStatusDot.tsx`
- Create: `web/src/components/Sidebar.tsx`
- Create: `web/src/components/AppShell.tsx`
- Create: `web/src/hooks/useHosts.ts`
- Create: `web/src/pages/HostsPage.tsx` (stub)
- Create: `web/src/pages/ResultsPage.tsx` (stub)
- Create: `web/src/pages/RunPage.tsx` (Phase-3 placeholder)
- Create: `web/src/pages/ModelsPage.tsx` (stub)
- Modify: `web/src/app.tsx`

- [ ] **Step 1: Create `web/src/components/Spinner.tsx`**

```tsx
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
```

- [ ] **Step 2: Create `web/src/components/ErrorBanner.tsx`**

```tsx
export function ErrorBanner({ error }: { error: Error | string }) {
  const msg = typeof error === 'string' ? error : error.message
  return (
    <div class="rounded border border-bad/40 bg-bad/10 px-3 py-2 text-sm text-bad">
      {msg}
    </div>
  )
}
```

- [ ] **Step 3: Create `web/src/components/RunnerStatusDot.tsx`**

```tsx
import type { RunnerSnapshot } from '../types'

export function RunnerStatusDot({ snap }: { snap: RunnerSnapshot }) {
  const color = snap.reachable ? 'bg-good' : 'bg-bad'
  const title = snap.reachable
    ? `${snap.runner} reachable${snap.version ? ` (${snap.version})` : ''}`
    : `${snap.runner} unreachable: ${snap.error ?? 'unknown error'}`
  return <span class={`inline-block h-2 w-2 rounded-full ${color}`} title={title} />
}
```

- [ ] **Step 4: Create `web/src/hooks/useHosts.ts`**

```ts
import { api } from '../api'
import { useApi } from './useApi'

export function useHosts() {
  return useApi(() => api.hosts(), [])
}
```

- [ ] **Step 5: Create `web/src/components/Sidebar.tsx`**

```tsx
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
          const active = location === item.href || (item.href !== '/' && location.startsWith(item.href))
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
```

- [ ] **Step 6: Create `web/src/components/AppShell.tsx`**

```tsx
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
```

- [ ] **Step 7: Create page stubs**

`web/src/pages/HostsPage.tsx`:
```tsx
export function HostsPage() {
  return <div class="p-6"><h1 class="text-xl font-semibold">Hosts</h1></div>
}
```

`web/src/pages/ResultsPage.tsx`:
```tsx
export function ResultsPage() {
  return <div class="p-6"><h1 class="text-xl font-semibold">Results</h1></div>
}
```

`web/src/pages/ModelsPage.tsx`:
```tsx
export function ModelsPage() {
  return <div class="p-6"><h1 class="text-xl font-semibold">Models</h1></div>
}
```

`web/src/pages/RunPage.tsx`:
```tsx
export function RunPage() {
  return (
    <div class="p-6 max-w-xl">
      <h1 class="text-xl font-semibold">Run</h1>
      <p class="mt-2 text-text-muted">
        Live benchmark triggering arrives in Phase 3 (job runner + WebSocket).
        For now, run benchmarks from the CLI.
      </p>
    </div>
  )
}
```

- [ ] **Step 8: Replace `web/src/app.tsx`**

```tsx
import { Route, Switch } from 'wouter-preact'
import { AppShell } from './components/AppShell'
import { HostsPage } from './pages/HostsPage'
import { ModelsPage } from './pages/ModelsPage'
import { ResultsPage } from './pages/ResultsPage'
import { RunPage } from './pages/RunPage'

export function App() {
  return (
    <AppShell>
      <Switch>
        <Route path="/" component={ResultsPage} />
        <Route path="/hosts" component={HostsPage} />
        <Route path="/run" component={RunPage} />
        <Route path="/models" component={ModelsPage} />
        <Route>
          <div class="p-6 text-text-muted">Page not found.</div>
        </Route>
      </Switch>
    </AppShell>
  )
}
```

- [ ] **Step 9: Build + manual smoke**

Run: `cd web && npm run build`
Expected: zero TS errors, dist produced.

Start the API server in another terminal: `uv run llm-toolkit ui --port 7860`
Then `cd web && npm run dev` and open `http://localhost:5173`.
Expected: sidebar shows nav links + host status dots from your local hosts.toml, clicking each nav link routes to the right placeholder page.

- [ ] **Step 10: Commit**

```bash
git add web/src/components/ web/src/hooks/useHosts.ts web/src/pages/ web/src/app.tsx
git commit -m "feat(web): AppShell + sidebar + wouter routing skeleton"
```

---

## Task 9: Hosts page (host cards)

**Files:**
- Modify: `web/src/pages/HostsPage.tsx`

- [ ] **Step 1: Replace `web/src/pages/HostsPage.tsx`**

```tsx
import { useHosts } from '../hooks/useHosts'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { formatBytes } from '../utils/format'
import type { HostSnapshot, RunnerSnapshot } from '../types'

export function HostsPage() {
  const { data, error, loading, refresh } = useHosts()

  return (
    <div class="p-6">
      <div class="mb-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold">Hosts</h1>
        <button
          class="rounded border border-border bg-surface px-3 py-1 text-sm hover:bg-raised"
          onClick={() => {
            void fetch('/api/hosts/refresh', { method: 'POST' }).then(() => refresh())
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
          <ModelGroup label="Loaded" rows={snap.loaded_models.map((m) => ({
            tag: m.tag,
            extra: m.vram_bytes ? formatBytes(m.vram_bytes) : '',
          }))} />
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
```

- [ ] **Step 2: Type-check + manual smoke**

Run: `cd web && npx tsc -b`
Expected: zero errors.

Start dev server (`npm run dev`) and visit `http://localhost:5173/hosts`.
Expected: each configured host renders a card; reachable runners show loaded/installed models with sizes; unreachable runners show their error in red. Refresh button hits `/api/hosts/refresh` and updates the timestamps.

- [ ] **Step 3: Commit**

```bash
git add web/src/pages/HostsPage.tsx
git commit -m "feat(web): Hosts page with runner cards + loaded/installed models"
```

---

## Task 10: Results table (basic listing, no filters yet)

**Files:**
- Create: `web/src/hooks/useResults.ts`
- Create: `web/src/pages/results/ResultsTable.tsx`
- Create: `web/src/__tests__/ResultsTable.test.tsx`
- Modify: `web/src/pages/ResultsPage.tsx`

- [ ] **Step 1: Create `web/src/hooks/useResults.ts`**

```ts
import { api } from '../api'
import type { ResultsQuery } from '../types'
import { useApi } from './useApi'

export function useResults(q: ResultsQuery) {
  const key = JSON.stringify(q)
  return useApi(() => api.results(q), [key])
}
```

- [ ] **Step 2: Write the failing test**

Create `web/src/__tests__/ResultsTable.test.tsx`:

```tsx
import { render, screen } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'
import { ResultsTable } from '../pages/results/ResultsTable'
import type { ResultRow } from '../types'

const ROWS: ResultRow[] = [
  {
    id: 1,
    benchmark: 'throughput_benchy',
    model: 'qwen3.5:9b',
    host: 'drubuntu',
    runner: 'ollama',
    gpu: '3080ti',
    run_id: null,
    timestamp: 1_714_300_000,
    metrics: { tg_throughput: 42.5, pp_throughput: 100.1 },
    metadata: {},
  },
  {
    id: 2,
    benchmark: 'throughput_benchy',
    model: 'qwen3.5:9b',
    host: 'localhost',
    runner: 'ollama',
    gpu: 'm3-max',
    run_id: null,
    timestamp: 1_714_400_000,
    metrics: { tg_throughput: 31.2, pp_throughput: 80.0 },
    metadata: {},
  },
]

describe('ResultsTable', () => {
  it('renders one row per result and shows the primary metric', () => {
    render(<ResultsTable rows={ROWS} selected={new Set()} onToggle={() => {}} />)
    expect(screen.getAllByRole('row')).toHaveLength(3) // header + 2 rows
    expect(screen.getByText('42.50')).toBeTruthy()
    expect(screen.getByText('31.20')).toBeTruthy()
  })

  it('renders host/runner/gpu in a combined cell', () => {
    render(<ResultsTable rows={ROWS} selected={new Set()} onToggle={() => {}} />)
    expect(screen.getByText(/drubuntu \/ ollama \/ 3080ti/)).toBeTruthy()
  })

  it('reflects selected ids via the checkbox', () => {
    render(<ResultsTable rows={ROWS} selected={new Set([1])} onToggle={() => {}} />)
    const checkboxes = screen.getAllByRole('checkbox') as HTMLInputElement[]
    // checkboxes[0] is the header "select all", [1] is row 1, [2] is row 2.
    expect(checkboxes[1].checked).toBe(true)
    expect(checkboxes[2].checked).toBe(false)
  })
})
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web && npm test -- ResultsTable`
Expected: fails — module not found.

- [ ] **Step 4: Create `web/src/pages/results/ResultsTable.tsx`**

```tsx
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { useState } from 'preact/hooks'
import type { ResultRow } from '../../types'
import { formatNumber, formatRelativeTime } from '../../utils/format'
import { primaryMetric, secondaryMetric } from '../../utils/metrics'

interface Props {
  rows: ResultRow[]
  selected: Set<number>
  onToggle: (id: number) => void
}

export function ResultsTable({ rows, selected, onToggle }: Props) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'timestamp', desc: true },
  ])

  const columns: ColumnDef<ResultRow>[] = [
    {
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={
            rows.length > 0 && rows.every((r) => selected.has(r.id))
          }
          onChange={() => {
            const allSelected = rows.every((r) => selected.has(r.id))
            for (const r of rows) {
              if (allSelected) {
                if (selected.has(r.id)) onToggle(r.id)
              } else {
                if (!selected.has(r.id)) onToggle(r.id)
              }
            }
            table.resetRowSelection()
          }}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selected.has(row.original.id)}
          onChange={() => onToggle(row.original.id)}
        />
      ),
    },
    { accessorKey: 'benchmark', header: 'Benchmark' },
    { accessorKey: 'model', header: 'Model' },
    {
      id: 'host_combo',
      header: 'Host / Runner / GPU',
      cell: ({ row }) => {
        const r = row.original
        const parts = [r.host ?? '—', r.runner ?? '—', r.gpu ?? '—']
        return <span class="font-mono text-xs">{parts.join(' / ')}</span>
      },
    },
    {
      id: 'primary',
      header: 'Primary',
      cell: ({ row }) => {
        const r = row.original
        const key = primaryMetric(r.benchmark)
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'secondary',
      header: 'Secondary',
      cell: ({ row }) => {
        const r = row.original
        const key = secondaryMetric(r.benchmark)
        if (!key) return <span class="text-text-ghost">—</span>
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'timestamp',
      header: 'When',
      accessorFn: (r) => r.timestamp,
      cell: ({ row }) => (
        <span class="text-xs text-text-muted">
          {formatRelativeTime(row.original.timestamp)}
        </span>
      ),
    },
  ]

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <table class="w-full border-collapse text-sm">
      <thead class="bg-panel text-left text-xs uppercase tracking-wide text-text-ghost">
        {table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>
            {hg.headers.map((h) => (
              <th
                key={h.id}
                class="cursor-pointer px-3 py-2 select-none"
                onClick={h.column.getToggleSortingHandler()}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted() as string] ?? ''}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => (
          <tr
            key={row.id}
            class={`border-t border-border ${
              selected.has(row.original.id) ? 'bg-surface' : 'hover:bg-surface'
            }`}
          >
            {row.getVisibleCells().map((cell) => (
              <td key={cell.id} class="px-3 py-2">
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  )
}
```

- [ ] **Step 5: Replace `web/src/pages/ResultsPage.tsx`**

```tsx
import { useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const { data, error, loading } = useResults({})

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Results</h1>
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
    </div>
  )
}
```

- [ ] **Step 6: Run tests + type-check**

Run: `cd web && npm test`
Expected: all tests pass (including the three new ResultsTable tests).

Run: `cd web && npx tsc -b`
Expected: zero errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/hooks/useResults.ts web/src/pages/results/ResultsTable.tsx \
        web/src/__tests__/ResultsTable.test.tsx web/src/pages/ResultsPage.tsx
git commit -m "feat(web): Results table via TanStack Table (sort + multi-select)"
```

---

## Task 11: Results filters

**Files:**
- Create: `web/src/pages/results/ResultsFilters.tsx`
- Modify: `web/src/pages/ResultsPage.tsx`

- [ ] **Step 1: Create `web/src/pages/results/ResultsFilters.tsx`**

```tsx
import type { ResultsQuery } from '../../types'

interface Props {
  value: ResultsQuery
  onChange: (next: ResultsQuery) => void
  facets: {
    benchmarks: string[]
    models: string[]
    hosts: string[]
    runners: string[]
    gpus: string[]
  }
}

const SINCE_OPTIONS: { label: string; seconds: number | null }[] = [
  { label: 'All time', seconds: null },
  { label: 'Last 24h', seconds: 60 * 60 * 24 },
  { label: 'Last 7d', seconds: 60 * 60 * 24 * 7 },
  { label: 'Last 30d', seconds: 60 * 60 * 24 * 30 },
]

export function ResultsFilters({ value, onChange, facets }: Props) {
  function set<K extends keyof ResultsQuery>(key: K, v: ResultsQuery[K]) {
    onChange({ ...value, [key]: v || undefined })
  }

  return (
    <div class="mb-3 flex flex-wrap items-center gap-2 text-xs">
      <Pick label="Benchmark" value={value.benchmark} options={facets.benchmarks} onChange={(v) => set('benchmark', v)} />
      <Pick label="Model" value={value.model} options={facets.models} onChange={(v) => set('model', v)} />
      <Pick label="Host" value={value.host} options={facets.hosts} onChange={(v) => set('host', v)} />
      <Pick label="Runner" value={value.runner} options={facets.runners} onChange={(v) => set('runner', v)} />
      <Pick label="GPU" value={value.gpu} options={facets.gpus} onChange={(v) => set('gpu', v)} />
      <select
        class="rounded border border-border bg-surface px-2 py-1"
        value={value.since ? String(value.since) : ''}
        onChange={(e) => {
          const sec = (e.currentTarget as HTMLSelectElement).value
          if (!sec) {
            onChange({ ...value, since: undefined })
          } else {
            onChange({ ...value, since: Date.now() / 1000 - Number(sec) })
          }
        }}
      >
        {SINCE_OPTIONS.map((o) => (
          <option key={o.label} value={o.seconds ?? ''}>{o.label}</option>
        ))}
      </select>
      {Object.values(value).some((v) => v !== undefined) && (
        <button
          class="text-text-muted underline hover:text-text"
          onClick={() => onChange({})}
        >
          Clear
        </button>
      )}
    </div>
  )
}

function Pick({
  label,
  value,
  options,
  onChange,
}: {
  label: string
  value: string | undefined
  options: string[]
  onChange: (v: string) => void
}) {
  return (
    <select
      class="rounded border border-border bg-surface px-2 py-1"
      value={value ?? ''}
      onChange={(e) => onChange((e.currentTarget as HTMLSelectElement).value)}
    >
      <option value="">{label}: any</option>
      {options.map((o) => (
        <option key={o} value={o}>{o}</option>
      ))}
    </select>
  )
}
```

- [ ] **Step 2: Update `web/src/pages/ResultsPage.tsx`**

Replace the file with:

```tsx
import { useMemo, useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'
import { ResultsFilters } from './results/ResultsFilters'
import type { ResultsQuery } from '../types'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [query, setQuery] = useState<ResultsQuery>({})
  const { data, error, loading } = useResults(query)

  const facets = useMemo(() => {
    const rows = data?.results ?? []
    const uniq = (arr: (string | null | undefined)[]) =>
      Array.from(new Set(arr.filter((s): s is string => !!s))).sort()
    return {
      benchmarks: uniq(rows.map((r) => r.benchmark)),
      models: uniq(rows.map((r) => r.model)),
      hosts: uniq(rows.map((r) => r.host)),
      runners: uniq(rows.map((r) => r.runner)),
      gpus: uniq(rows.map((r) => r.gpu)),
    }
  }, [data])

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Results</h1>
      <ResultsFilters value={query} onChange={setQuery} facets={facets} />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
    </div>
  )
}
```

- [ ] **Step 3: Type-check + manual smoke**

Run: `cd web && npx tsc -b && npm test`
Expected: zero errors, all tests pass.

Manually: select a benchmark from the dropdown; the table re-fetches with the right query params (network tab confirms `?benchmark=throughput_benchy`).

- [ ] **Step 4: Commit**

```bash
git add web/src/pages/results/ResultsFilters.tsx web/src/pages/ResultsPage.tsx
git commit -m "feat(web): Results filter chips (benchmark/model/host/runner/gpu/since)"
```

---

## Task 12: Compare drawer + MetricBars (TDD on diff math)

**Files:**
- Create: `web/src/pages/results/MetricBars.tsx`
- Create: `web/src/pages/results/CompareDrawer.tsx`
- Create: `web/src/__tests__/CompareDrawer.test.tsx`
- Modify: `web/src/pages/ResultsPage.tsx`

- [ ] **Step 1: Write the failing test**

Create `web/src/__tests__/CompareDrawer.test.tsx`:

```tsx
import { render, screen } from '@testing-library/preact'
import { describe, expect, it } from 'vitest'
import { CompareDrawer } from '../pages/results/CompareDrawer'
import type { CompareResponse } from '../types'

const RESP: CompareResponse = {
  primary_metric: 'tg_throughput',
  rows: [
    {
      id: 1, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'drubuntu', runner: 'ollama', gpu: '3080ti',
      run_id: null, timestamp: 1_714_300_000,
      metrics: { tg_throughput: 100 }, metadata: {}, diff_pct: 0,
    },
    {
      id: 2, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'localhost', runner: 'ollama', gpu: 'm3-max',
      run_id: null, timestamp: 1_714_300_500,
      metrics: { tg_throughput: 80 }, metadata: {}, diff_pct: -20,
    },
    {
      id: 3, benchmark: 'throughput_benchy', model: 'qwen3.5:9b',
      host: 'drubuntu', runner: 'llama-server', gpu: '3080ti',
      run_id: null, timestamp: 1_714_300_900,
      metrics: { tg_throughput: 120 }, metadata: {}, diff_pct: 20,
    },
  ],
}

describe('CompareDrawer', () => {
  it('renders one card per row with the primary metric value', () => {
    render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(screen.getByText(/Compare/i)).toBeTruthy()
    expect(screen.getAllByText('100').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('80').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('120').length).toBeGreaterThanOrEqual(1)
  })

  it('renders the diff_pct labels (baseline + others)', () => {
    render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(screen.getByText('baseline')).toBeTruthy()
    expect(screen.getByText('-20.00%')).toBeTruthy()
    expect(screen.getByText('+20.00%')).toBeTruthy()
  })

  it('renders an SVG bar per row', () => {
    const { container } = render(<CompareDrawer data={RESP} onClose={() => {}} />)
    expect(container.querySelectorAll('rect').length).toBe(3)
  })
})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test -- CompareDrawer`
Expected: fails — module not found.

- [ ] **Step 3: Create `web/src/pages/results/MetricBars.tsx`**

```tsx
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
```

- [ ] **Step 4: Create `web/src/pages/results/CompareDrawer.tsx`**

```tsx
import type { CompareResponse, CompareRow } from '../../types'
import { MetricBars } from './MetricBars'

interface Props {
  data: CompareResponse
  onClose: () => void
}

export function CompareDrawer({ data, onClose }: Props) {
  const bars = data.rows.map((r) => ({
    label: shortLabel(r),
    value: numericMetric(r, data.primary_metric),
  }))

  return (
    <aside class="fixed right-0 top-0 z-30 flex h-full w-[28rem] flex-col border-l border-border bg-panel p-4 shadow-xl">
      <div class="mb-3 flex items-center justify-between">
        <h2 class="text-base font-semibold">Compare</h2>
        <button class="text-text-muted hover:text-text" onClick={onClose}>
          ✕
        </button>
      </div>
      <p class="mb-3 text-xs text-text-muted">
        Primary metric: <span class="font-mono">{data.primary_metric}</span>
      </p>
      <MetricBars bars={bars} unit={data.primary_metric} />
      <div class="mt-4 flex flex-col gap-2 overflow-y-auto">
        {data.rows.map((r, i) => (
          <CompareCard key={r.id} row={r} primary={data.primary_metric} isBaseline={i === 0} />
        ))}
      </div>
    </aside>
  )
}

function CompareCard({
  row,
  primary,
  isBaseline,
}: {
  row: CompareRow
  primary: string
  isBaseline: boolean
}) {
  const value = numericMetric(row, primary)
  return (
    <div class="rounded border border-border bg-surface p-3 text-xs">
      <div class="flex items-center justify-between">
        <span class="font-mono">{shortLabel(row)}</span>
        <span class={diffClass(row.diff_pct, isBaseline)}>
          {isBaseline ? 'baseline' : formatDiff(row.diff_pct)}
        </span>
      </div>
      <div class="mt-1 text-text-muted">
        {row.benchmark} · {row.model}
      </div>
      <div class="mt-1 font-mono text-text">{value} {primary}</div>
    </div>
  )
}

function shortLabel(r: { host: string | null; runner: string | null; gpu: string | null }) {
  return [r.host ?? '?', r.runner ?? '?', r.gpu ?? '?'].join(' / ')
}

function numericMetric(r: CompareRow, key: string): number {
  const v = r.metrics[key]
  return typeof v === 'number' ? v : 0
}

function formatDiff(pct: number | null): string {
  if (pct === null) return '—'
  const sign = pct >= 0 ? '+' : ''
  return `${sign}${pct.toFixed(2)}%`
}

function diffClass(pct: number | null, isBaseline: boolean): string {
  if (isBaseline) return 'text-text-muted'
  if (pct === null) return 'text-text-ghost'
  if (pct > 0) return 'text-good'
  if (pct < 0) return 'text-bad'
  return 'text-text-muted'
}
```

- [ ] **Step 5: Update `web/src/pages/ResultsPage.tsx` to wire selection → Compare**

Replace the file:

```tsx
import { useEffect, useMemo, useState } from 'preact/hooks'
import { useResults } from '../hooks/useResults'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { ResultsTable } from './results/ResultsTable'
import { ResultsFilters } from './results/ResultsFilters'
import { CompareDrawer } from './results/CompareDrawer'
import type { CompareResponse, ResultsQuery } from '../types'
import { api } from '../api'

export function ResultsPage() {
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [query, setQuery] = useState<ResultsQuery>({})
  const [compare, setCompare] = useState<CompareResponse | null>(null)
  const [compareError, setCompareError] = useState<string | null>(null)
  const { data, error, loading } = useResults(query)

  const facets = useMemo(() => {
    const rows = data?.results ?? []
    const uniq = (arr: (string | null | undefined)[]) =>
      Array.from(new Set(arr.filter((s): s is string => !!s))).sort()
    return {
      benchmarks: uniq(rows.map((r) => r.benchmark)),
      models: uniq(rows.map((r) => r.model)),
      hosts: uniq(rows.map((r) => r.host)),
      runners: uniq(rows.map((r) => r.runner)),
      gpus: uniq(rows.map((r) => r.gpu)),
    }
  }, [data])

  // Drop selections that disappear after a filter change.
  useEffect(() => {
    if (!data) return
    const visible = new Set(data.results.map((r) => r.id))
    setSelected((prev) => new Set([...prev].filter((id) => visible.has(id))))
  }, [data])

  function toggle(id: number) {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  async function openCompare() {
    setCompareError(null)
    try {
      const ids = [...selected]
      const resp = await api.compare(ids)
      setCompare(resp)
    } catch (e) {
      setCompareError(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Results</h1>
      <ResultsFilters value={query} onChange={setQuery} facets={facets} />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {compareError && <ErrorBanner error={compareError} />}
      {data && (
        <ResultsTable rows={data.results} selected={selected} onToggle={toggle} />
      )}
      {selected.size >= 2 && !compare && (
        <div class="sticky bottom-0 mt-3 flex items-center justify-between rounded border border-border bg-panel px-4 py-2 text-sm shadow">
          <span>{selected.size} selected</span>
          <button
            class="rounded bg-accent px-3 py-1 text-bg hover:opacity-90"
            onClick={() => void openCompare()}
          >
            Compare
          </button>
        </div>
      )}
      {compare && <CompareDrawer data={compare} onClose={() => setCompare(null)} />}
    </div>
  )
}
```

- [ ] **Step 6: Run tests + type-check**

Run: `cd web && npm test && npx tsc -b`
Expected: all tests pass; zero TS errors.

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/results/MetricBars.tsx \
        web/src/pages/results/CompareDrawer.tsx \
        web/src/__tests__/CompareDrawer.test.tsx \
        web/src/pages/ResultsPage.tsx
git commit -m "feat(web): Compare drawer with hand-rolled SVG bars + diff cards"
```

---

## Task 13: Row-expand on Results table (raw metrics + run link)

**Files:**
- Modify: `web/src/pages/results/ResultsTable.tsx`
- Modify: `web/src/__tests__/ResultsTable.test.tsx`

The spec calls for "Row click expands inline (raw metrics blob, link to runs row + log)." Logs are produced by the Phase 3 job runner, so we render the run link only when `run_id` is set, and skip the log viewer for now.

- [ ] **Step 1: Extend the existing test**

Open `web/src/__tests__/ResultsTable.test.tsx` and add this test case at the end of the `describe('ResultsTable', ...)` block:

```tsx
import { fireEvent } from '@testing-library/preact'
// ... existing imports unchanged

  it('expands a row inline when clicked, showing raw metrics', () => {
    render(<ResultsTable rows={ROWS} selected={new Set()} onToggle={() => {}} />)
    const dataCells = screen.getAllByText('throughput_benchy')
    fireEvent.click(dataCells[0])
    // Raw metrics JSON contains the tg_throughput key/value pair.
    expect(screen.getByText(/"tg_throughput": 42\.5/)).toBeTruthy()
  })

  it('renders a run link when run_id is set', () => {
    const withRun = [{ ...ROWS[0], run_id: 9 }]
    render(<ResultsTable rows={withRun} selected={new Set()} onToggle={() => {}} />)
    fireEvent.click(screen.getAllByText('throughput_benchy')[0])
    expect(screen.getByText('Run #9')).toBeTruthy()
  })
```

If `fireEvent` is not yet imported at the top of the file, change the import line to:

```tsx
import { fireEvent, render, screen } from '@testing-library/preact'
```

- [ ] **Step 2: Run the new tests to confirm they fail**

Run: `cd web && npm test -- ResultsTable`
Expected: the two new tests fail (no expand UI yet).

- [ ] **Step 3: Update `web/src/pages/results/ResultsTable.tsx`**

Add inline expand behavior. Replace the file with:

```tsx
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from '@tanstack/react-table'
import { Fragment } from 'preact'
import { useState } from 'preact/hooks'
import type { ResultRow } from '../../types'
import { formatNumber, formatRelativeTime } from '../../utils/format'
import { primaryMetric, secondaryMetric } from '../../utils/metrics'

interface Props {
  rows: ResultRow[]
  selected: Set<number>
  onToggle: (id: number) => void
}

export function ResultsTable({ rows, selected, onToggle }: Props) {
  const [sorting, setSorting] = useState<SortingState>([
    { id: 'timestamp', desc: true },
  ])
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  function toggleExpanded(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const columns: ColumnDef<ResultRow>[] = [
    {
      id: 'select',
      header: ({ table }) => (
        <input
          type="checkbox"
          checked={
            rows.length > 0 && rows.every((r) => selected.has(r.id))
          }
          onChange={() => {
            const allSelected = rows.every((r) => selected.has(r.id))
            for (const r of rows) {
              if (allSelected) {
                if (selected.has(r.id)) onToggle(r.id)
              } else {
                if (!selected.has(r.id)) onToggle(r.id)
              }
            }
            table.resetRowSelection()
          }}
          onClick={(e) => e.stopPropagation()}
        />
      ),
      cell: ({ row }) => (
        <input
          type="checkbox"
          checked={selected.has(row.original.id)}
          onChange={() => onToggle(row.original.id)}
          onClick={(e) => e.stopPropagation()}
        />
      ),
    },
    { accessorKey: 'benchmark', header: 'Benchmark' },
    { accessorKey: 'model', header: 'Model' },
    {
      id: 'host_combo',
      header: 'Host / Runner / GPU',
      cell: ({ row }) => {
        const r = row.original
        const parts = [r.host ?? '—', r.runner ?? '—', r.gpu ?? '—']
        return <span class="font-mono text-xs">{parts.join(' / ')}</span>
      },
    },
    {
      id: 'primary',
      header: 'Primary',
      cell: ({ row }) => {
        const r = row.original
        const key = primaryMetric(r.benchmark)
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'secondary',
      header: 'Secondary',
      cell: ({ row }) => {
        const r = row.original
        const key = secondaryMetric(r.benchmark)
        if (!key) return <span class="text-text-ghost">—</span>
        const v = r.metrics[key]
        return (
          <span class="font-mono">
            {formatNumber(typeof v === 'number' ? v : null)}
            <span class="ml-1 text-xs text-text-ghost">{key}</span>
          </span>
        )
      },
    },
    {
      id: 'timestamp',
      header: 'When',
      accessorFn: (r) => r.timestamp,
      cell: ({ row }) => (
        <span class="text-xs text-text-muted">
          {formatRelativeTime(row.original.timestamp)}
        </span>
      ),
    },
  ]

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  })

  return (
    <table class="w-full border-collapse text-sm">
      <thead class="bg-panel text-left text-xs uppercase tracking-wide text-text-ghost">
        {table.getHeaderGroups().map((hg) => (
          <tr key={hg.id}>
            {hg.headers.map((h) => (
              <th
                key={h.id}
                class="cursor-pointer px-3 py-2 select-none"
                onClick={h.column.getToggleSortingHandler()}
              >
                {flexRender(h.column.columnDef.header, h.getContext())}
                {{ asc: ' ↑', desc: ' ↓' }[h.column.getIsSorted() as string] ?? ''}
              </th>
            ))}
          </tr>
        ))}
      </thead>
      <tbody>
        {table.getRowModel().rows.map((row) => {
          const r = row.original
          const isOpen = expanded.has(r.id)
          return (
            <Fragment key={row.id}>
              <tr
                class={`cursor-pointer border-t border-border ${
                  selected.has(r.id) ? 'bg-surface' : 'hover:bg-surface'
                }`}
                onClick={() => toggleExpanded(r.id)}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} class="px-3 py-2">
                    {flexRender(cell.column.columnDef.cell, cell.getContext())}
                  </td>
                ))}
              </tr>
              {isOpen && (
                <tr class="border-t border-border bg-bg">
                  <td colspan={columns.length} class="px-6 py-3">
                    <div class="flex flex-col gap-2 text-xs">
                      {r.run_id !== null && (
                        <div>
                          <span class="text-text-muted">Run: </span>
                          <a
                            href={`#run-${r.run_id}`}
                            class="text-accent hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            Run #{r.run_id}
                          </a>
                        </div>
                      )}
                      <div>
                        <div class="text-text-muted">metrics</div>
                        <pre class="mt-1 overflow-x-auto rounded border border-border bg-panel p-2 font-mono text-xs">
                          {JSON.stringify(r.metrics, null, 2)}
                        </pre>
                      </div>
                      {Object.keys(r.metadata ?? {}).length > 0 && (
                        <div>
                          <div class="text-text-muted">metadata</div>
                          <pre class="mt-1 overflow-x-auto rounded border border-border bg-panel p-2 font-mono text-xs">
                            {JSON.stringify(r.metadata, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              )}
            </Fragment>
          )
        })}
      </tbody>
    </table>
  )
}
```

- [ ] **Step 4: Run tests + type-check**

Run: `cd web && npm test`
Expected: all `ResultsTable` tests pass — the original three plus the two new expand tests.

Run: `cd web && npx tsc -b`
Expected: zero errors.

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/results/ResultsTable.tsx web/src/__tests__/ResultsTable.test.tsx
git commit -m "feat(web): inline row-expand on Results showing raw metrics + run link"
```

---

## Task 14: Models page

**Files:**
- Create: `web/src/hooks/useModels.ts`
- Modify: `web/src/pages/ModelsPage.tsx`

- [ ] **Step 1: Create `web/src/hooks/useModels.ts`**

```ts
import { api } from '../api'
import { useApi } from './useApi'

export function useModels() {
  return useApi(() => api.models(), [])
}
```

- [ ] **Step 2: Replace `web/src/pages/ModelsPage.tsx`**

```tsx
import { useState } from 'preact/hooks'
import { useLocation } from 'wouter-preact'
import { useModels } from '../hooks/useModels'
import { Spinner } from '../components/Spinner'
import { ErrorBanner } from '../components/ErrorBanner'
import { formatBytes } from '../utils/format'

export function ModelsPage() {
  const { data, error, loading } = useModels()
  const [, navigate] = useLocation()
  const [filter, setFilter] = useState('')

  const rows = (data?.models ?? []).filter((m) =>
    !filter || m.tag.toLowerCase().includes(filter.toLowerCase()),
  )

  function jumpToResults(tag: string) {
    const qs = new URLSearchParams({ model: tag }).toString()
    navigate(`/?${qs}`)
  }

  return (
    <div class="p-6">
      <h1 class="mb-4 text-xl font-semibold">Models</h1>
      <input
        class="mb-3 w-64 rounded border border-border bg-surface px-2 py-1 text-sm"
        placeholder="Filter by tag…"
        value={filter}
        onInput={(e) => setFilter((e.currentTarget as HTMLInputElement).value)}
      />
      {loading && <Spinner />}
      {error && <ErrorBanner error={error} />}
      {data && (
        <table class="w-full border-collapse text-sm">
          <thead class="bg-panel text-left text-xs uppercase tracking-wide text-text-ghost">
            <tr>
              <th class="px-3 py-2">Tag</th>
              <th class="px-3 py-2">Host</th>
              <th class="px-3 py-2">Runner</th>
              <th class="px-3 py-2">GPU</th>
              <th class="px-3 py-2">Loaded</th>
              <th class="px-3 py-2">Size</th>
              <th class="px-3 py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((m, i) => (
              <tr key={`${m.host}-${m.runner}-${m.tag}-${i}`} class="border-t border-border">
                <td class="px-3 py-2 font-mono">{m.tag}</td>
                <td class="px-3 py-2">{m.host}</td>
                <td class="px-3 py-2">{m.runner}</td>
                <td class="px-3 py-2">{m.gpu ?? '—'}</td>
                <td class="px-3 py-2">
                  <span class={m.loaded ? 'text-good' : 'text-text-ghost'}>
                    {m.loaded ? 'yes' : 'no'}
                  </span>
                </td>
                <td class="px-3 py-2 font-mono text-xs">{formatBytes(m.size_bytes)}</td>
                <td class="px-3 py-2">
                  <button
                    class="text-accent hover:underline"
                    onClick={() => jumpToResults(m.tag)}
                  >
                    Results →
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
```

- [ ] **Step 3: Wire query-param prefill on the Results page**

Open `web/src/pages/ResultsPage.tsx` and change the initial state line from:

```tsx
  const [query, setQuery] = useState<ResultsQuery>({})
```

to:

```tsx
  const [query, setQuery] = useState<ResultsQuery>(() => {
    const usp = new URLSearchParams(window.location.search)
    const out: ResultsQuery = {}
    const model = usp.get('model'); if (model) out.model = model
    const host = usp.get('host'); if (host) out.host = host
    const runner = usp.get('runner'); if (runner) out.runner = runner
    const gpu = usp.get('gpu'); if (gpu) out.gpu = gpu
    const benchmark = usp.get('benchmark'); if (benchmark) out.benchmark = benchmark
    return out
  })
```

- [ ] **Step 4: Type-check + manual smoke**

Run: `cd web && npx tsc -b && npm test`
Expected: zero errors, all tests pass.

Visit `/models` and click a "Results →" link.
Expected: navigates to `/?model=<tag>` and the Results page loads pre-filtered.

- [ ] **Step 5: Commit**

```bash
git add web/src/hooks/useModels.ts web/src/pages/ModelsPage.tsx web/src/pages/ResultsPage.tsx
git commit -m "feat(web): Models page + cross-link to Results filtered by tag"
```

---

## Task 15: Document the dev workflow + final smoke

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/superpowers/HANDOFF.md`

- [ ] **Step 1: Append a "Web UI" section to `CLAUDE.md`**

Append at the end of `CLAUDE.md`:

```markdown

## Web UI (Phase 2)

```bash
# One-time install
cd web && npm install

# Dev (two terminals)
uv run llm-toolkit ui --port 7860     # API server
cd web && npm run dev                 # Vite dev server on :5173 with /api + /ws proxy

# Production-ish: build the SPA, then ui serves it from /
cd web && npm run build
uv run llm-toolkit ui --port 7860     # now also serves the SPA at http://127.0.0.1:7860/

# Tests
cd web && npm test
```
```

- [ ] **Step 2: Update `docs/superpowers/HANDOFF.md`**

Replace the file content with:

```markdown
# Runner Dashboard — Handoff

**Status as of 2026-04-29:** Phase 1 (backend foundation) and Phase 2 (Preact frontend) are complete and committed to `main`. Phase 3 (Run/jobs/WebSocket) is designed but not yet planned in detail or implemented.

## Where we are

- **Spec** (approved, locked): [`specs/2026-04-28-runner-dashboard-design.md`](specs/2026-04-28-runner-dashboard-design.md)
- **Phase 1 plan** (executed): [`plans/2026-04-28-runner-dashboard-phase1.md`](plans/2026-04-28-runner-dashboard-phase1.md)
- **Phase 2 plan** (executed): [`plans/2026-04-29-runner-dashboard-phase2.md`](plans/2026-04-29-runner-dashboard-phase2.md)
- **Phase 3 plan:** not yet written

## Resume in a new session

```
Read docs/superpowers/specs/2026-04-28-runner-dashboard-design.md
Then write Phase 3 plan (Run page + jobs + WebSocket).
```

## Try the live UI

```bash
mkdir -p ~/.config/llm-toolkit
cat > ~/.config/llm-toolkit/hosts.toml <<'EOF'
[[host]]
name = "localhost"
[[host.runner]]
type = "ollama"
url  = "http://127.0.0.1:11434"
gpu  = "m3-max"
EOF

uv sync --extra dev --extra web
cd web && npm install && npm run build && cd ..
uv run llm-toolkit ui --port 7860
# open http://127.0.0.1:7860
```

To import legacy JSONL into SQLite:
```bash
uv run llm-toolkit db migrate path/to/perf.jsonl --host drubuntu --runner ollama --gpu 3080ti
```
```

- [ ] **Step 3: Final smoke**

Run: `uv run pytest -q && uv run ruff check src/ tests/`
Expected: all green.

Run: `cd web && npm run build && npm test && npx tsc -b`
Expected: build succeeds, tests pass, no TS errors.

Then `uv run llm-toolkit ui --port 7860` and open `http://127.0.0.1:7860` in a browser.
Expected:
- Sidebar lists Results / Hosts / Run / Models with status dots for each configured runner.
- Results page renders rows from `~/.local/share/llm-toolkit/results.db` (empty if none yet — run a benchmark or import JSONL first).
- Hosts page renders one card per host with reachable runners showing loaded models.
- Selecting 2+ rows on Results, then clicking Compare, opens the drawer with bars and diff percentages.
- Models page filters work; "Results →" link navigates with the right query string.
- Run page renders the "coming in Phase 3" placeholder.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/superpowers/HANDOFF.md
git commit -m "docs: Phase 2 handoff + web dev workflow"
```

---

## Self-review checklist (post-implementation)

After all tasks land, verify each spec item from `specs/2026-04-28-runner-dashboard-design.md` is covered:

- [x] Sidebar with persistent nav + collapsible host status — Task 8
- [x] Results page (sortable filterable table over `results`) — Tasks 10–11
- [x] Row click expands inline (raw metrics + run link) — Task 13
- [x] Compare drawer with bar chart + diff vs baseline — Task 12
- [x] Hosts page with per-runner cards + loaded/installed models — Task 9
- [x] Models page (cross-host index, click → Results filter) — Task 14
- [x] Vite + Preact + Tailwind v4 + TS, mirrors `~/projects/tmnt/web` — Tasks 2–3
- [x] TanStack Table via `preact/compat` — Task 10
- [x] Hand-rolled SVG bar chart — Task 12
- [x] `wouter-preact` router — Task 8
- [x] FastAPI mounts `web/dist/` with SPA fallback — Task 4
- [x] Dev: Vite on :5173 proxies /api + /ws to FastAPI — Task 2
- [x] Vitest + component tests for Results — Tasks 6–7, 10, 12, 13
- [ ] Run page (Phase 3) — placeholder only this phase
- [ ] Per-runner "Run benchmark" button on Hosts cards — deferred to Phase 3 (depends on Run form)
- [ ] Log viewer link in row expand — deferred to Phase 3 (logs are produced by the job runner)

Any spec item that lacks a task is a gap — open a follow-up before claiming Phase 2 complete.
