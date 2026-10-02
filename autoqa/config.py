from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "scans"
STATIC_DIR = Path(__file__).resolve().parent / "static"
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = int(os.getenv("PORT", "4173"))
ALLOW_PRIVATE_TARGETS = os.getenv("ALLOW_PRIVATE_TARGETS", "0") == "1"
MAX_SCAN_PAGES = min(max(int(os.getenv("MAX_SCAN_PAGES", "12")), 1), 30)
MAX_CONCURRENT_SCANS = min(max(int(os.getenv("MAX_CONCURRENT_SCANS", "2")), 1), 4)
CHROMIUM_PATH = os.getenv("CHROMIUM_PATH", "/usr/bin/chromium")
