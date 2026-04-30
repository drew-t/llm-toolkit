"""FastAPI app factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

import llm_toolkit
from llm_toolkit.db import DEFAULT_DB_PATH, init_db
from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
from llm_toolkit.web.deps import DEFAULT_RUNS_DIR, make_context


def _resolve_web_dist() -> Path:
    return Path(llm_toolkit.__file__).resolve().parent.parent.parent / "web" / "dist"


def create_app(
    *,
    db_path: Path | str = DEFAULT_DB_PATH,
    hosts_path: Path | str = DEFAULT_HOSTS_PATH,
    runs_dir: Path | str = DEFAULT_RUNS_DIR,
) -> FastAPI:
    db = Path(db_path)
    hosts = Path(hosts_path)
    runs = Path(runs_dir)
    init_db(db)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await app.state.ctx.queue.start()
        try:
            yield
        finally:
            await app.state.ctx.queue.stop()

    app = FastAPI(title="llm-toolkit", lifespan=lifespan)
    app.state.ctx = make_context(db_path=db, hosts_path=hosts, runs_dir=runs)

    from llm_toolkit.web.routes import hosts as hosts_routes

    app.include_router(hosts_routes.router)

    from llm_toolkit.web.routes import results as results_routes

    app.include_router(results_routes.router)

    from llm_toolkit.web.routes import runs as runs_routes

    app.include_router(runs_routes.router)
    from llm_toolkit.web.routes.runs import runs_websocket_endpoint

    app.add_api_websocket_route("/ws/runs/{rid}", runs_websocket_endpoint)

    from llm_toolkit.web.routes import models as models_routes

    app.include_router(models_routes.router)

    @app.get("/healthz")
    def healthz() -> dict:
        return {"ok": True}

    dist = _resolve_web_dist()
    index_html = dist / "index.html"
    if index_html.exists():
        assets_dir = dist / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_fallback(full_path: str) -> FileResponse:
            return FileResponse(index_html)

    return app
