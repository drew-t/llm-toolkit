# Runner Dashboard — Handoff

**Status as of 2026-04-29:** Phase 1 (backend foundation) is complete and committed to `main`. Phases 2 and 3 are designed but not yet planned in detail or implemented.

## Where we are

- **Spec** (approved, locked): [`specs/2026-04-28-runner-dashboard-design.md`](specs/2026-04-28-runner-dashboard-design.md)
- **Phase 1 plan** (executed): [`plans/2026-04-28-runner-dashboard-phase1.md`](plans/2026-04-28-runner-dashboard-phase1.md)
- **Phase 1 commits:** `768ed37..5b6481f` (17 commits, 109 tests, ruff clean)
- **Phase 2 plan:** not yet written
- **Phase 3 plan:** not yet written

## Resume in a new session

```
Read docs/superpowers/specs/2026-04-28-runner-dashboard-design.md
Read docs/superpowers/plans/2026-04-28-runner-dashboard-phase1.md (already executed — Phase 1 is done)

Then either:
  (a) write Phase 2 plan (Preact + Vite + Tailwind frontend)
  (b) write Phase 3 plan (Run page + jobs + WebSocket)
  (c) something else
```

The dashboard-progress memory entry summarizes locked decisions so a fresh session doesn't relitigate them.

## Try the live API

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
uv run llm-toolkit ui --port 7860
# in another terminal:
curl -s http://127.0.0.1:7860/api/hosts | jq
```

To import legacy JSONL into SQLite:
```bash
uv run llm-toolkit db migrate path/to/perf.jsonl --host drubuntu --runner ollama --gpu 3080ti
```
