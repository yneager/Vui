from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.async_api import async_playwright, Page, Browser, Route

from .checks import (
    SAFE_TEXT, RISKY_TEXT, analyze_dom, analyze_mobile, analyze_runtime,
    analyze_status, compare_parity, score_report, issue,
)
from .config import CHROMIUM_PATH, DATA_DIR
from .models import PageResult, ScanReport, ScanRequest, utc_now
from .security import same_origin, is_obviously_private_url
from .storage import save

JS_SNAPSHOT = r"""
() => {
  const text = (document.body?.innerText || '').replace(/\s+/g, ' ').trim();
  const els = [...document.querySelectorAll('[id]')];
  const counts = {};
  for (const el of els) counts[el.id] = (counts[el.id] || 0) + 1;
  const duplicateIds = Object.entries(counts).filter(([,n]) => n > 1).map(([id]) => id);
  const labelFor = (el) => {
    const id = el.id;
    return !!(el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') ||
      (id && document.querySelector(\`label[for="\${CSS.escape(id)}"]\`)) || el.closest('label') || el.title);
  };
  const unlabeled = [...document.querySelectorAll('input:not([type="hidden"]), select, textarea')]
    .filter(el => !labelFor(el)).map(el => ({tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || ''}));
  const nameless = [...document.querySelectorAll('button, [role="button"]')]
    .filter(el => !(el.innerText || el.getAttribute('aria-label') || el.getAttribute('aria-labelledby') || el.title || '').trim())
    .map(el => ({tag: el.tagName, id: el.id || '', class: el.className || ''}));
  const links = [...document.querySelectorAll('a[href]')].map(a => ({href: a.href, text: (a.innerText || '').trim().slice(0,120)}));
  const nums = (text.match(/(?:AED\s*)?\b\d[\d,.]*\b/gi) || []).slice(0,60);
  const navCount = document.querySelectorAll('nav a[href], header a[href]').length;
  const controls = document.querySelectorAll('input:not([type="hidden"]), select, textarea').length;
  const buttons = document.querySelectorAll('button, [role="button"]').length;
  const images = document.images.length;
  return {
    title: document.title || '',
    lang: document.documentElement.lang || '',
    dir: document.documentElement.dir || getComputedStyle(document.documentElement).direction || '',
    visible_text: text.slice(0, 100000),
    text_chars: text.length,
    h1_texts: [...document.querySelectorAll('h1')].map(x => (x.innerText || '').trim()).filter(Boolean),
    images_missing_alt: [...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.currentSrc || i.src || '(inline)').slice(0,30),
    unlabeled_controls: unlabeled.slice(0,30),
    nameless_buttons: nameless.slice(0,30),
    duplicate_ids: duplicateIds.slice(0,30),
    password_forms_insecure: location.protocol !== 'https:' ? [...document.querySelectorAll('input[type="password"]')].map(i => i.name || i.id || 'password') : [],
    links,
    nav_count: navCount,
    form_control_count: controls,
    button_count: buttons,
    image_count: images,
    important_numbers: nums,
  };
}
"""

JS_MOBILE = r"""
() => {
  const vw = window.innerWidth;
  const overflowing = [...document.querySelectorAll('body *')].filter(el => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return s.position !== 'fixed' && (r.right > vw + 2 || r.left < -2) && r.width > 0 && r.height > 0;
  }).slice(0,20).map(el => ({tag: el.tagName, id: el.id || '', class: String(el.className || '').slice(0,80), right: Math.round(el.getBoundingClientRect().right)}));
  const tiny = [...document.querySelectorAll('a[href], button, input, select, textarea, [role="button"]')]
    .filter(el => { const r = el.getBoundingClientRect(); return r.width > 0 && r.height > 0 && (r.width < 36 || r.height < 36); })
    .slice(0,20).map(el => ({tag: el.tagName, text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0,60)}));
  return {
    horizontal_overflow: document.documentElement.scrollWidth > vw + 2,
    scroll_width: document.documentElement.scrollWidth,
    viewport_width: vw,
    overflowing_elements: overflowing,
    tiny_click_targets: tiny,
  };
}
"""


def _canonical(raw: str) -> str:
    p = urlsplit(raw)
    path = p.path or "/"
    if path != "/": path = path.rstrip("/")
    return urlunsplit((p.scheme, p.netloc, path, p.query, ""))


def _locale_pair(url: str) -> tuple[str, str] | None:
    p = urlsplit(url)
    path = p.path
    m = re.search(r"(^|/)(en|ar)(?=/|$)", path, flags=re.I)
    if not m:
        return None
    lang = m.group(2).lower()
    other = "ar" if lang == "en" else "en"
    other_path = path[:m.start(2)] + other + path[m.end(2):]
    other_url = urlunsplit((p.scheme, p.netloc, other_path, p.query, ""))
    return (url, other_url) if lang == "en" else (other_url, url)


async def _route_guard(route: Route) -> None:
    if is_obviously_private_url(route.request.url) and route.request.resource_type in {"document", "xhr", "fetch", "script"}:
        await route.abort("blockedbyclient")
    else:
        await route.continue_()


async def _safe_interactions(page: Page, max_clicks: int = 4) -> int:
    tested = 0
    loc = page.locator('button[type="button"], [role="button"]')
    count = min(await loc.count(), 20)
    for i in range(count):
        if tested >= max_clicks:
            break
        el = loc.nth(i)
        try:
            label = ((await el.inner_text(timeout=500)) or (await el.get_attribute("aria-label")) or "").strip()
            if RISKY_TEXT.search(label):
                continue
            if label and not SAFE_TEXT.search(label):
                continue
            if not await el.is_visible() or not await el.is_enabled():
                continue
            await el.click(timeout=900)
            tested += 1
            await page.wait_for_timeout(120)
        except Exception:
            continue
    return tested


async def run_scan(report: ScanReport, request: ScanRequest, allow_private: bool = False) -> None:
    started = time.perf_counter()
    report.status = "running"
    report.started_at = utc_now()
    report.progress_message = "Launching browser"
    save(report)

    screenshots_dir = DATA_DIR / report.scan_id / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    try:
        async with async_playwright() as p:
            browser: Browser = await p.chromium.launch(
                headless=True,
                executable_path=CHROMIUM_PATH if Path(CHROMIUM_PATH).exists() else None,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            desktop = await browser.new_context(viewport={"width": 1440, "height": 900}, ignore_https_errors=False)
            mobile = await browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True) if request.mobile_check else None
            if not allow_private:
                await desktop.route("**/*", _route_guard)
                if mobile:
                    await mobile.route("**/*", _route_guard)

            queue = deque([_canonical(report.target_url)])
            visited: set[str] = set()
            snapshots: dict[str, dict] = {}
            statuses: dict[str, int | None] = {}
            pair_candidates: set[tuple[str, str]] = set()

            while queue and len(visited) < request.max_pages:
                url = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                report.progress_message = f"Scanning page {len(visited)}/{request.max_pages}: {url}"
                save(report)

                console_errors: list[str] = []
                failures: list[dict[str, str]] = []
                page = await desktop.new_page()
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("requestfailed", lambda req: failures.append({"url": req.url, "failure": req.failure or "failed"}))
                t0 = time.perf_counter()
                response = None
                navigation_error: str | None = None
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(250)
                    status = response.status if response else None
                    statuses[url] = status
                    snapshot = await page.evaluate(JS_SNAPSHOT)
                    if status is not None and status < 400:
                        snapshots[url] = snapshot
                    interactions = await _safe_interactions(page) if request.safe_interactions and (status or 999) < 400 else 0
                    load_ms = int((time.perf_counter() - t0) * 1000)
                    report.issues.extend(analyze_status(status, url))
                    if status is not None and status < 400:
                        report.issues.extend(analyze_dom(snapshot, url))
                        report.issues.extend(analyze_runtime(console_errors, failures, url))
                        if len(visited) <= 3:
                            try:
                                await page.screenshot(path=str(screenshots_dir / f"desktop-{len(visited):02}.png"), full_page=True)
                            except Exception:
                                pass
                        for link in snapshot.get("links", []):
                            href = link.get("href") or ""
                            if href.startswith(("mailto:", "tel:", "javascript:", "data:")):
                                continue
                            try:
                                joined = _canonical(urljoin(url, href))
                            except Exception:
                                continue
                            if same_origin(report.target_url, joined) and joined not in visited and len(queue) < request.max_pages * 4:
                                queue.append(joined)
                        if request.bilingual_parity:
                            pair = _locale_pair(url)
                            if pair:
                                pair_candidates.add((_canonical(pair[0]), _canonical(pair[1])))
                                other = _canonical(pair[1] if url == _canonical(pair[0]) else pair[0])
                                if other not in visited:
                                    queue.appendleft(other)

                        if mobile:
                            mp = await mobile.new_page()
                            try:
                                mr = await mp.goto(url, wait_until="domcontentloaded", timeout=15000)
                                if mr and mr.status < 400:
                                    await mp.wait_for_timeout(120)
                                    mobile_snapshot = await mp.evaluate(JS_MOBILE)
                                    report.issues.extend(analyze_mobile(mobile_snapshot, url))
                            finally:
                                await mp.close()

                    report.pages.append(PageResult(
                        url=url, status_code=status, title=snapshot.get("title", "") if status and status < 400 else "",
                        lang=snapshot.get("lang", "") if status and status < 400 else "",
                        direction=snapshot.get("dir", "") if status and status < 400 else "",
                        load_ms=load_ms, links_found=len(snapshot.get("links", [])) if status and status < 400 else 0,
                        console_errors=len(console_errors), request_failures=len(failures), safe_interactions_tested=interactions,
                    ))
                except Exception as exc:
                    navigation_error = f"{type(exc).__name__}: {exc}"
                    statuses[url] = None
                    report.issues.extend(analyze_status(None, url))
                    report.pages.append(PageResult(url=url, status_code=None, load_ms=int((time.perf_counter()-t0)*1000), navigation_error=navigation_error))
                    console_errors.append(str(exc))
                finally:
                    await page.close()

            if request.bilingual_parity:
                checked = 0
                for en_url, ar_url in pair_candidates:
                    if en_url in snapshots and ar_url in snapshots:
                        report.issues.extend(compare_parity(snapshots[en_url], snapshots[ar_url], en_url, ar_url))
                        checked += 1
                    elif en_url in snapshots and statuses.get(ar_url, 200) is not None and (statuses.get(ar_url) or 0) >= 400:
                        report.issues.append(issue(
                            "bilingual-parity", "high", "Arabic counterpart is missing",
                            "The English page exists, but the matching Arabic route returned an error.", ar_url,
                            {"english_url": en_url, "arabic_url": ar_url, "arabic_status": statuses.get(ar_url)},
                            "Create or restore the Arabic counterpart and keep routes synchronized."
                        ))
                report.parity_pairs_checked = checked

            await desktop.close()
            if mobile:
                await mobile.close()
            await browser.close()

        dedup = {}
        for item in report.issues:
            key = (item.page_url, item.title, item.viewport)
            dedup.setdefault(key, item)
        report.issues = list(dedup.values())
        report.pages_scanned = len(report.pages)
        report.score = score_report(report.issues)
        report.status = "completed"
        report.progress_message = "Completed"
    except Exception as exc:
        report.status = "failed"
        report.error = f"{type(exc).__name__}: {exc}"
        report.progress_message = "Scan failed"
    finally:
        report.finished_at = utc_now()
        report.duration_ms = int((time.perf_counter() - started) * 1000)
        save(report)
