"""GET /api/hosts and POST /api/hosts/refresh."""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from fastapi import APIRouter, Request

from llm_toolkit.discovery.types import RunnerSnapshot

router = APIRouter(prefix="/api/hosts")


def _snapshot_to_dict(snap: RunnerSnapshot) -> dict:
    return {
        "runner": snap.runner,
        "base_url": snap.base_url,
        "gpu": snap.gpu,
        "version": snap.version,
        "reachable": snap.reachable,
        "error": snap.error,
        "installed_models": [asdict(m) for m in snap.installed_models],
        "loaded_models": [asdict(m) for m in snap.loaded_models],
        "raw": snap.raw,
    }


async def _probe_all(ctx, *, force: bool) -> list[dict]:
    cfg = ctx.hosts()
    out: list[dict] = []
    for host in cfg.hosts:
        runner_dicts: list[dict] = []
        coros = []
        entries = []
        for entry in host.runners:
            adapter = ctx.adapters.get(entry.type)
            if adapter is None:
                continue
            entries.append(entry)
            coros.append(
                ctx.cache.get(
                    host.name, entry.type, entry.url, entry.gpu, adapter.probe, force=force
                )
            )
        snaps = await asyncio.gather(*coros, return_exceptions=False)
        for snap in snaps:
            runner_dicts.append(_snapshot_to_dict(snap))
        out.append({"name": host.name, "runners": runner_dicts})
    return out


@router.get("")
async def list_hosts(request: Request) -> dict:
    return {"hosts": await _probe_all(request.app.state.ctx, force=False)}


@router.post("/refresh")
async def refresh_hosts(request: Request) -> dict:
    return {"hosts": await _probe_all(request.app.state.ctx, force=True)}
