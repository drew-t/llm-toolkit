"""/api/models — flat cross-host model index."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/models")


@router.get("")
async def list_models(request: Request) -> dict:
    ctx = request.app.state.ctx
    cfg = ctx.hosts()
    rows: list[dict] = []
    for host in cfg.hosts:
        coros = []
        entries = []
        for entry in host.runners:
            adapter = ctx.adapters.get(entry.type)
            if adapter is None:
                continue
            entries.append(entry)
            coros.append(
                ctx.cache.get(host.name, entry.type, entry.url, entry.gpu, adapter.probe)
            )
        snaps = await asyncio.gather(*coros, return_exceptions=False)
        for entry, snap in zip(entries, snaps, strict=True):
            loaded_tags = {m.tag for m in snap.loaded_models}
            for m in snap.installed_models:
                rows.append({
                    "tag": m.tag,
                    "host": host.name,
                    "runner": entry.type,
                    "gpu": entry.gpu,
                    "loaded": m.tag in loaded_tags,
                    "size_bytes": m.size_bytes,
                })
    return {"models": rows}
