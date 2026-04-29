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
