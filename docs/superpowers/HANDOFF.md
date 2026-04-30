# Runner Dashboard — Handoff

**Status as of 2026-04-30:** Phases 1, 2, and 3 are complete and on `main`. The web UI at `llm-toolkit ui` is feature-complete for v1: hosts/runners discovery, results browser with compare drawer, runs page with live WebSocket streaming, and cross-page navigation via `run_id`.

## Where we are

- **Spec** (locked): [`specs/2026-04-28-runner-dashboard-design.md`](specs/2026-04-28-runner-dashboard-design.md)
- **Phase 1 plan** (executed): [`plans/2026-04-28-runner-dashboard-phase1.md`](plans/2026-04-28-runner-dashboard-phase1.md)
- **Phase 2 plan** (executed): [`plans/2026-04-29-runner-dashboard-phase2.md`](plans/2026-04-29-runner-dashboard-phase2.md)
- **Phase 3 plan** (executed): [`plans/2026-04-29-runner-dashboard-phase3.md`](plans/2026-04-29-runner-dashboard-phase3.md)

## Try it

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

## End-to-end smoke test (manual, with a real Ollama running locally)

1. Open http://127.0.0.1:7860/run.
2. Pick `throughput_benchy` / `localhost` / `ollama` / `m3-max` / `qwen3:8b`.
3. Add args: `pp = 2048`, `tg = 128`, `runs = 1`, `tokenizer = Qwen/Qwen3-8B`.
4. Click `Run`. Watch log lines stream in; status flips to `success`; "View results" link appears.
5. Click "View results" — the new row is on the Results page.
6. Expand the new row; "View run #N" link sends you back to RunDetail.
7. Trigger another run, then click `Cancel` while it's `running`; status flips to `cancelled`.

## Operational notes

- Run logs live at `~/.local/share/llm-toolkit/runs/<id>.log` (override via `LLM_TOOLKIT_RUNS_DIR`).
- Per-run JSONL output at `~/.local/share/llm-toolkit/runs/<id>.jsonl` (read once on subprocess exit, then re-imported into the SQLite `results` table tagged with `run_id`/`host`/`runner`/`gpu`).
- A run that's mid-flight survives WebSocket disconnects: reconnecting to `/ws/runs/<id>` replays the on-disk log and resumes live streaming.
- Single-concurrency is enforced inside the FastAPI process — submitting a second run while one is active queues it. There is no UI for queue depth in v1.
- The dev workflow uses Vite on `:5173` proxying `/api` and `/ws` to the FastAPI server on `:7860`.

## Possible v1.5 / v2 work

- One-job-per-(host, runner, gpu) concurrency relaxation.
- Auto-rotate / TTL on `runs/<id>.log`.
- "Rerun this run" button on completed runs.
- Streaming throughput chart (rather than just text log) during a run.
- A queue-depth indicator and per-run row in the UI for pending runs.
