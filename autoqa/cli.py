from __future__ import annotations

import argparse
import asyncio
import json
from uuid import uuid4

from .models import ScanReport, ScanRequest
from .scanner import run_scan
from .security import validate_target_url

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def main() -> None:
    parser = argparse.ArgumentParser(description="AutoQA UAE autonomous website scanner")
    parser.add_argument("url", help="Website URL to scan")
    parser.add_argument("--max-pages", type=int, default=8)
    parser.add_argument("--no-mobile", action="store_true")
    parser.add_argument("--no-parity", action="store_true")
    parser.add_argument("--no-interactions", action="store_true")
    parser.add_argument("--allow-private", action="store_true", help="Allow localhost/private networks you control")
    parser.add_argument(
        "--fail-on", choices=["critical", "high", "medium", "low", "none"], default="none",
        help="Exit with status 1 when an issue at or above this severity is detected (useful in CI).",
    )
    args = parser.parse_args()

    target = validate_target_url(args.url, allow_private=args.allow_private)
    req = ScanRequest(
        target_url=target,
        max_pages=args.max_pages,
        mobile_check=not args.no_mobile,
        bilingual_parity=not args.no_parity,
        safe_interactions=not args.no_interactions,
    )
    report = ScanReport(scan_id=uuid4().hex, target_url=target, options=req.model_dump(exclude={"target_url"}))
    asyncio.run(run_scan(report, req, allow_private=args.allow_private))
    print(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))

    if report.status != "completed":
        raise SystemExit(2)
    if args.fail_on != "none":
        threshold = SEVERITY_RANK[args.fail_on]
        if any(SEVERITY_RANK[i.severity] <= threshold for i in report.issues):
            raise SystemExit(1)


if __name__ == "__main__":
    main()
