from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .config import DATA_DIR
from .models import ScanReport

_lock = RLock()
_memory: dict[str, ScanReport] = {}


def save(report: ScanReport) -> None:
    """Persist a report atomically so an interrupted write cannot corrupt history."""
    with _lock:
        _memory[report.scan_id] = report
        path = DATA_DIR / f"{report.scan_id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)


def get(scan_id: str) -> ScanReport | None:
    with _lock:
        if scan_id in _memory:
            return _memory[scan_id]
        path = DATA_DIR / f"{scan_id}.json"
        if not path.exists():
            return None
        report = ScanReport.model_validate_json(path.read_text(encoding="utf-8"))
        _memory[scan_id] = report
        return report


def list_reports(limit: int = 20) -> list[ScanReport]:
    paths = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    reports: list[ScanReport] = []
    for path in paths:
        if len(reports) >= limit:
            break
        try:
            reports.append(ScanReport.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return reports


def previous_completed(target_url: str, exclude_scan_id: str) -> ScanReport | None:
    for report in list_reports(limit=200):
        if report.scan_id != exclude_scan_id and report.status == "completed" and report.target_url == target_url:
            return report
    return None
