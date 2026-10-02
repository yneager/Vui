"""Browser-level probe that requires no network access.

Useful in restricted environments: launches Chromium, renders a seeded page in-memory,
and exercises the same DOM/mobile extraction used by the scanner.
"""
from __future__ import annotations

from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import asyncio
from playwright.async_api import async_playwright

from autoqa.checks import analyze_dom, analyze_mobile, analyze_runtime
from autoqa.config import CHROMIUM_PATH
from autoqa.scanner import JS_MOBILE, JS_SNAPSHOT

HTML = """<!doctype html><html><head><title></title><style>.wide{width:1200px}</style></head>
<body><div class='wide'><p>مرحبا بكم</p></div><img src='data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='>
<input type='email'><button></button><script>console.error('SEEDED_PROBE_ERROR')</script></body></html>"""


async def run() -> int:
    errors: list[str] = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path=CHROMIUM_PATH, args=["--no-sandbox", "--disable-dev-shm-usage"])
        page = await browser.new_page(viewport={"width": 390, "height": 844})
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        await page.set_content(HTML, wait_until="domcontentloaded")
        dom = await page.evaluate(JS_SNAPSHOT)
        mobile = await page.evaluate(JS_MOBILE)
        issues = analyze_dom(dom, "about:blank") + analyze_mobile(mobile, "about:blank") + analyze_runtime(errors, [], "about:blank")
        names = {i.title for i in issues}
        expected = {
            "Missing document language", "Arabic page is not RTL", "Images missing alt text",
            "Form controls missing labels", "Buttons without accessible names", "Horizontal overflow on mobile",
            "JavaScript console errors",
        }
        detected = names & expected
        print(f"browser_probe={len(detected)}/{len(expected)} detected")
        print(sorted(detected))
        await browser.close()
        return 0 if len(detected) == len(expected) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run()))
