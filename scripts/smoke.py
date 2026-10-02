"""Deterministic end-to-end smoke test against the bundled seeded demo."""
from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
import os
import subprocess
import sys
import time
from uuid import uuid4

import httpx

from autoqa.models import ScanReport, ScanRequest
from autoqa.scanner import run_scan

PORT = 48731
BASE = f"http://127.0.0.1:{PORT}"


def wait_for_server() -> None:
    for _ in range(50):
        try:
            if httpx.get(f"{BASE}/api/health", timeout=0.5).status_code == 200:
                return
        except Exception:
            time.sleep(0.1)
    raise RuntimeError("Demo server did not start")


def main() -> int:
    env = dict(os.environ)
    env["ALLOW_PRIVATE_TARGETS"] = "1"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "autoqa.app:app", "--host", "127.0.0.1", "--port", str(PORT), "--log-level", "warning"],
        env=env,
    )
    try:
        wait_for_server()
        req = ScanRequest(target_url=f"{BASE}/demo/en", max_pages=8, mobile_check=True, bilingual_parity=True, safe_interactions=True)
        report = ScanReport(scan_id=uuid4().hex, target_url=req.target_url, options=req.model_dump(exclude={"target_url"}))
        asyncio.run(run_scan(report, req, allow_private=True))
        names = {x.title for x in report.issues}
        expected = {
            "JavaScript console errors",
            "Horizontal overflow on mobile",
            "Images missing alt text",
            "Buttons without accessible names",
            "Arabic page is not RTL",
            "Form controls missing labels",
            "Arabic counterpart is missing",
        }
        detected = expected & names
        print(f"status={report.status} pages={report.pages_scanned} score={report.score} issues={len(report.issues)}")
        print(f"seeded_detection={len(detected)}/{len(expected)} -> {sorted(detected)}")
        missing = expected - detected
        if missing:
            print(f"missing={sorted(missing)}")
        if report.status == "completed" and len(detected) >= 6:
            return 0
        blocked = any("ERR_BLOCKED_BY_ADMINISTRATOR" in (p.navigation_error or "") for p in report.pages)
        if blocked and os.getenv("GITHUB_ACTIONS") != "true":
            print("network_smoke=SKIPPED (host Chromium policy blocks navigation); browser_probe.py covers real browser DOM checks")
            return 0
        return 1
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    raise SystemExit(main())
