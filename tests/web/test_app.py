"""Smoke tests for the FastAPI app."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from llm_toolkit.web.app import create_app


def test_healthz(tmp_path: Path):
    app = create_app(
        db_path=tmp_path / "r.db",
        hosts_path=tmp_path / "hosts.toml",
        runs_dir=tmp_path / "runs",
    )
    client = TestClient(app)
    r = client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"ok": True}


def test_app_creates_db_on_first_request(tmp_path: Path):
    db = tmp_path / "r.db"
    app = create_app(
        db_path=db,
        hosts_path=tmp_path / "hosts.toml",
        runs_dir=tmp_path / "runs",
    )
    client = TestClient(app)
    client.get("/healthz")
    assert db.exists()


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

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path, runs_dir=tmp_path / "runs")
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

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path, runs_dir=tmp_path / "runs")
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

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path, runs_dir=tmp_path / "runs")
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

    app = app_module.create_app(db_path=db_path, hosts_path=hosts_path, runs_dir=tmp_path / "runs")
    client = TestClient(app)

    assert client.get("/healthz").status_code == 200
    assert client.get("/").status_code == 404


def test_app_context_has_queue_and_runs_dir(tmp_path):
    app = create_app(
        db_path=tmp_path / "r.db",
        hosts_path=tmp_path / "h.toml",
        runs_dir=tmp_path / "runs",
    )
    ctx = app.state.ctx
    assert ctx.queue is not None
    assert ctx.runs_dir.exists()
