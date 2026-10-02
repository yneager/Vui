from __future__ import annotations

import asyncio
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import ALLOW_PRIVATE_TARGETS, MAX_SCAN_PAGES, STATIC_DIR
from .demo import router as demo_router
from .models import ScanReport, ScanRequest
from .scanner import run_scan
from .security import validate_target_url
from .storage import get, list_reports, save

app = FastAPI(title="AutoQA UAE", version=__version__, docs_url="/api/docs", redoc_url=None)
app.include_router(demo_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_running_tasks: set[asyncio.Task] = set()


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": __version__}


@app.post("/api/scans", status_code=202)
async def create_scan(payload: ScanRequest):
    raw_parts = urlsplit(payload.target_url if "://" in payload.target_url else "https://" + payload.target_url)
    is_bundled_demo = raw_parts.hostname in {"localhost", "127.0.0.1", "::1"} and raw_parts.path.startswith("/demo/")
    try:
        normalized = validate_target_url(payload.target_url, allow_private=ALLOW_PRIVATE_TARGETS or is_bundled_demo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    payload.max_pages = min(payload.max_pages, MAX_SCAN_PAGES)
    report = ScanReport(
        scan_id=uuid4().hex,
        target_url=normalized,
        options=payload.model_dump(exclude={"target_url"}),
    )
    save(report)
    task = asyncio.create_task(run_scan(report, payload, allow_private=ALLOW_PRIVATE_TARGETS or is_bundled_demo))
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return {"scan_id": report.scan_id, "status": report.status, "target_url": report.target_url}


@app.get("/api/scans/{scan_id}")
async def scan_status(scan_id: str):
    report = get(scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scan not found")
    return report.model_dump()


@app.get("/api/reports")
async def reports(limit: int = 10):
    limit = max(1, min(limit, 50))
    return [r.model_dump() for r in list_reports(limit)]


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
