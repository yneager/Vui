from __future__ import annotations

import asyncio
import html
import json
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import ALLOW_PRIVATE_TARGETS, MAX_CONCURRENT_SCANS, MAX_SCAN_PAGES, STATIC_DIR
from .demo import router as demo_router
from .models import ScanReport, ScanRequest, utc_now
from .scanner import run_scan
from .security import same_origin, validate_target_url
from .storage import get, list_reports, save

app = FastAPI(title="AutoQA UAE", version=__version__, docs_url="/api/docs", redoc_url=None)
app.include_router(demo_router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
_running_tasks: dict[str, asyncio.Task] = {}
_scan_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SCANS)


def _bundled_demo_allowed(target: str, request: Request) -> bool:
    raw = target if "://" in target else "https://" + target
    target_parts = urlsplit(raw)
    base = str(request.base_url).rstrip("/")
    return target_parts.path.startswith("/demo/") and same_origin(raw, base)


async def _run_limited(report: ScanReport, payload: ScanRequest, allow_private: bool) -> None:
    report.progress_message = "Waiting for an available browser slot"
    save(report)
    try:
        async with _scan_semaphore:
            await run_scan(report, payload, allow_private=allow_private)
    except asyncio.CancelledError:
        # A queued scan can be canceled before run_scan gets a chance to update status.
        if report.status == "queued":
            report.status = "canceled"
            report.progress_message = "Canceled"
            report.finished_at = utc_now()
            save(report)
        raise


def _report_or_404(scan_id: str) -> ScanReport:
    report = get(scan_id)
    if not report:
        raise HTTPException(status_code=404, detail="Scan not found")
    return report


@app.get("/api/health")
async def health():
    return {"status": "ok", "version": __version__, "max_concurrent_scans": MAX_CONCURRENT_SCANS}


@app.post("/api/scans", status_code=202)
async def create_scan(payload: ScanRequest, request: Request):
    is_bundled_demo = _bundled_demo_allowed(payload.target_url, request)
    try:
        normalized = validate_target_url(payload.target_url, allow_private=ALLOW_PRIVATE_TARGETS or is_bundled_demo)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    payload.max_pages = min(payload.max_pages, MAX_SCAN_PAGES)
    payload.target_url = normalized
    report = ScanReport(
        scan_id=uuid4().hex,
        target_url=normalized,
        options=payload.model_dump(exclude={"target_url"}),
    )
    save(report)
    task = asyncio.create_task(_run_limited(report, payload, allow_private=ALLOW_PRIVATE_TARGETS or is_bundled_demo))
    _running_tasks[report.scan_id] = task
    task.add_done_callback(lambda _task, sid=report.scan_id: _running_tasks.pop(sid, None))
    return {"scan_id": report.scan_id, "status": report.status, "target_url": report.target_url}


@app.delete("/api/scans/{scan_id}")
async def cancel_scan(scan_id: str):
    report = _report_or_404(scan_id)
    task = _running_tasks.get(scan_id)
    if not task or task.done():
        return {"scan_id": scan_id, "status": report.status, "canceled": False}
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    updated = _report_or_404(scan_id)
    return {"scan_id": scan_id, "status": updated.status, "canceled": updated.status == "canceled"}


@app.get("/api/scans/{scan_id}")
async def scan_status(scan_id: str):
    return _report_or_404(scan_id).model_dump()


@app.get("/api/scans/{scan_id}/export.json")
async def export_json(scan_id: str):
    report = _report_or_404(scan_id)
    body = json.dumps(report.model_dump(), ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="autoqa-{scan_id[:8]}.json"'},
    )


@app.get("/api/scans/{scan_id}/export.html")
async def export_html(scan_id: str):
    report = _report_or_404(scan_id)
    issue_rows = "".join(
        f"<tr><td>{html.escape(i.severity.upper())}</td><td>{html.escape(i.title)}</td>"
        f"<td>{html.escape(i.page_url)}</td><td>{html.escape(i.recommendation)}</td></tr>"
        for i in sorted(report.issues, key=lambda x: {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}[x.severity])
    ) or "<tr><td colspan='4'>No issues detected.</td></tr>"
    regression = "No baseline available."
    if report.baseline_scan_id:
        regression = (
            f"Baseline {html.escape(report.baseline_scan_id[:8])}: "
            f"{len(report.new_issue_ids)} new, {len(report.resolved_issue_ids)} resolved, "
            f"{len(report.unchanged_issue_ids)} unchanged."
        )
    body = f"""<!doctype html><html><head><meta charset='utf-8'><title>AutoQA report</title>
<style>body{{font-family:Arial,sans-serif;margin:36px;color:#172033}}h1{{margin-bottom:4px}}.muted{{color:#667085}}.score{{font-size:42px;font-weight:800}}table{{border-collapse:collapse;width:100%;margin-top:24px}}th,td{{padding:10px;border:1px solid #dfe3ea;text-align:left;vertical-align:top}}th{{background:#f5f7fa}}</style></head><body>
<h1>AutoQA UAE report</h1><p class='muted'>{html.escape(report.target_url)}</p><p class='score'>{report.score if report.score is not None else '—'} / 100</p>
<p>{report.pages_scanned} pages · {len(report.issues)} issues · {html.escape(report.status)}</p><p>{regression}</p>
<table><thead><tr><th>Severity</th><th>Issue</th><th>Page</th><th>Recommended fix</th></tr></thead><tbody>{issue_rows}</tbody></table>
</body></html>"""
    return HTMLResponse(
        body,
        headers={"Content-Disposition": f'attachment; filename="autoqa-{scan_id[:8]}.html"'},
    )


@app.get("/api/reports")
async def reports(limit: int = 10):
    limit = max(1, min(limit, 50))
    return [r.model_dump() for r in list_reports(limit)]


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")
