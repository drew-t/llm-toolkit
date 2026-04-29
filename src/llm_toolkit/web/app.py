"""FastAPI app factory."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from llm_toolkit.db import DEFAULT_DB_PATH, init_db
from llm_toolkit.discovery.hosts import DEFAULT_HOSTS_PATH
from llm_toolkit.web.deps import make_context


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

    return app
