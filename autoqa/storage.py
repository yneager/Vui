from __future__ import annotations

import json
from pathlib import Path
from threading import RLock

from .config import DATA_DIR
from .models import ScanReport

_lock = RLock()
_memory: dict[str, ScanReport] = {}


def save(report: ScanReport) -> None:
    with _lock:
        _memory[report.scan_id] = report
        path = DATA_DIR / f"{report.scan_id}.json"
        path.write_text(json.dumps(report.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")


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
    paths = sorted(DATA_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]
    reports: list[ScanReport] = []
    for path in paths:
        try:
            reports.append(ScanReport.model_validate_json(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return reports
