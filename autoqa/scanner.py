from __future__ import annotations

import asyncio
import re
import time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from playwright.async_api import Browser, BrowserContext, Page, Route, async_playwright

from .checks import (
    RISKY_TEXT,
    SAFE_TEXT,
    analyze_dom,
    analyze_mobile,
    analyze_runtime,
    analyze_security_headers,
    analyze_site,
    analyze_status,
    compare_parity,
    issue,
    score_report,
)
from .config import CHROMIUM_PATH, DATA_DIR
from .models import PageResult, ScanReport, ScanRequest, utc_now
from .security import host_resolves_public, same_origin
from .storage import previous_completed, save

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
      (id && document.querySelector(`label[for="${CSS.escape(id)}"]`)) || el.closest('label') || el.title);
  };
  const accessibleName = (el) => {
    const labelledBy = (el.getAttribute('aria-labelledby') || '').trim().split(/\s+/).filter(Boolean)
      .map(id => document.getElementById(id)?.innerText || '').join(' ');
    const imageAlt = [...el.querySelectorAll('img[alt]')].map(i => i.alt).join(' ');
    return (el.innerText || el.getAttribute('aria-label') || labelledBy || el.title || imageAlt || '').trim();
  };
  const unlabeled = [...document.querySelectorAll('input:not([type="hidden"]), select, textarea')]
    .filter(el => !labelFor(el)).map(el => ({tag: el.tagName, type: el.type || '', name: el.name || '', id: el.id || ''}));
  const nameless = [...document.querySelectorAll('button, [role="button"]')]
    .filter(el => !accessibleName(el))
    .map(el => ({tag: el.tagName, id: el.id || '', class: String(el.className || '').slice(0,80)}));
  const namelessLinks = [...document.querySelectorAll('a[href]')]
    .filter(el => !accessibleName(el))
    .map(el => ({href: el.href, id: el.id || '', class: String(el.className || '').slice(0,80)}));
  const links = [...document.querySelectorAll('a[href]')].map(a => ({href: a.href, text: accessibleName(a).slice(0,120)}));
  const important = [...text.matchAll(/(?:AED\s*[\d,.]+|[\d,.]+\s*(?:AED|%))/gi)]
    .map(m => m[0].replace(/\s+/g, ' ').trim().toUpperCase()).slice(0,60);
  const navCount = document.querySelectorAll('nav a[href], header a[href]').length;
  const controls = document.querySelectorAll('input:not([type="hidden"]), select, textarea').length;
  const buttons = document.querySelectorAll('button, [role="button"]').length;
  const images = document.images.length;
  const brokenAria = [];
  for (const el of document.querySelectorAll('[aria-labelledby], [aria-describedby]')) {
    for (const attr of ['aria-labelledby', 'aria-describedby']) {
      const value = el.getAttribute(attr);
      if (!value) continue;
      for (const id of value.trim().split(/\s+/)) {
        if (id && !document.getElementById(id)) brokenAria.push({tag: el.tagName, attr, missing_id: id});
      }
    }
  }
  const unsafeBlank = [...document.querySelectorAll('a[target="_blank"][href]')]
    .filter(a => !(a.rel || '').toLowerCase().split(/\s+/).includes('noopener'))
    .map(a => ({href: a.href, text: accessibleName(a).slice(0,80)}));
  const resourceEntries = performance.getEntriesByType('resource');
  const allResourceUrls = new Set(resourceEntries.map(r => r.name));
  for (const el of document.querySelectorAll('[src], link[href]')) {
    const u = el.src || el.href;
    if (u) allResourceUrls.add(u);
  }
  const mixedContent = location.protocol === 'https:'
    ? [...allResourceUrls].filter(u => /^http:\/\//i.test(u)).slice(0,30)
    : [];
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const transferBytes = resourceEntries.reduce((sum, r) => sum + (r.transferSize || 0), 0) + (nav.transferSize || 0);
  return {
    title: document.title || '',
    lang: document.documentElement.lang || '',
    dir: document.documentElement.dir || getComputedStyle(document.documentElement).direction || '',
    viewport_meta: !!document.querySelector('meta[name="viewport"]'),
    visible_text: text.slice(0, 100000),
    text_chars: text.length,
    h1_texts: [...document.querySelectorAll('h1')].map(x => (x.innerText || '').trim()).filter(Boolean),
    images_missing_alt: [...document.images].filter(i => !i.hasAttribute('alt')).map(i => i.currentSrc || i.src || '(inline)').slice(0,30),
    unlabeled_controls: unlabeled.slice(0,30),
    nameless_buttons: nameless.slice(0,30),
    nameless_links: namelessLinks.slice(0,30),
    duplicate_ids: duplicateIds.slice(0,30),
    broken_aria_references: brokenAria.slice(0,30),
    unsafe_blank_links: unsafeBlank.slice(0,30),
    mixed_content: mixedContent,
    password_forms_insecure: location.protocol !== 'https:' ? [...document.querySelectorAll('input[type="password"]')].map(i => i.name || i.id || 'password') : [],
    links,
    nav_count: navCount,
    form_control_count: controls,
    button_count: buttons,
    image_count: images,
    important_numbers: important,
    dom_elements: document.getElementsByTagName('*').length,
    resource_count: resourceEntries.length,
    transfer_kb: Math.round(transferBytes / 1024),
    dom_content_loaded_ms: nav.domContentLoadedEventEnd ? Math.round(nav.domContentLoadedEventEnd) : null,
    load_event_ms: nav.loadEventEnd ? Math.round(nav.loadEventEnd) : null,
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
    if path != "/":
        path = path.rstrip("/")
    return urlunsplit((p.scheme, p.netloc, path, p.query, ""))


def _locale_pair(url: str) -> tuple[str, str] | None:
    p = urlsplit(url)
    m = re.search(r"(^|/)(en|ar)(?=/|$)", p.path, flags=re.I)
    if not m:
        return None
    lang = m.group(2).lower()
    other = "ar" if lang == "en" else "en"
    other_path = p.path[:m.start(2)] + other + p.path[m.end(2):]
    other_url = urlunsplit((p.scheme, p.netloc, other_path, p.query, ""))
    return (url, other_url) if lang == "en" else (other_url, url)


class RequestGuard:
    """DNS-aware browser request guard with per-scan hostname caching."""

    def __init__(self) -> None:
        self._cache: dict[tuple[str, int], bool] = {}

    async def handle(self, route: Route) -> None:
        try:
            parsed = urlsplit(route.request.url)
            if parsed.scheme not in {"http", "https"}:
                await route.continue_()
                return
            host = (parsed.hostname or "").lower()
            port = parsed.port or (443 if parsed.scheme == "https" else 80)
            key = (host, port)
            allowed = self._cache.get(key)
            if allowed is None:
                allowed = await asyncio.to_thread(host_resolves_public, host, port)
                self._cache[key] = allowed
            if not allowed:
                await route.abort("blockedbyclient")
                return
            await route.continue_()
        except Exception:
            # Fail closed: a malformed/unresolvable request should not reach private infrastructure.
            try:
                await route.abort("blockedbyclient")
            except Exception:
                pass


async def _safe_interactions(context: BrowserContext, url: str, max_clicks: int = 4) -> tuple[int, list[str], list[dict[str, str]]]:
    """Exercise only explicitly safe, labelled controls on an isolated page.

    Isolation keeps exploration from mutating the crawler page or changing which links
    are discovered. Empty/unlabelled controls are deliberately skipped.
    """
    tested = 0
    errors: list[str] = []
    failures: list[dict[str, str]] = []
    page = await context.new_page()
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("requestfailed", lambda req: failures.append({"url": req.url, "failure": req.failure or "failed"}))
    try:
        response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
        if not response or response.status >= 400:
            return 0, errors, failures
        await page.wait_for_timeout(100)
        loc = page.locator('button[type="button"], [role="button"][aria-expanded]')
        count = min(await loc.count(), 30)
        for i in range(count):
            if tested >= max_clicks:
                break
            el = loc.nth(i)
            try:
                label = ((await el.inner_text(timeout=500)) or (await el.get_attribute("aria-label")) or "").strip()
                if not label or RISKY_TEXT.search(label) or not SAFE_TEXT.search(label):
                    continue
                if not await el.is_visible() or not await el.is_enabled():
                    continue
                await el.click(timeout=900)
                tested += 1
                await page.wait_for_timeout(120)
            except Exception:
                continue
        return tested, errors, failures
    finally:
        await page.close()


def _apply_regression(report: ScanReport) -> None:
    baseline = previous_completed(report.target_url, report.scan_id)
    if not baseline:
        return
    current_ids = {item.id for item in report.issues}
    baseline_ids = {item.id for item in baseline.issues}
    report.baseline_scan_id = baseline.scan_id
    report.new_issue_ids = sorted(current_ids - baseline_ids)
    report.resolved_issue_ids = sorted(baseline_ids - current_ids)
    report.unchanged_issue_ids = sorted(current_ids & baseline_ids)


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
                guard = RequestGuard()
                await desktop.route("**/*", guard.handle)
                if mobile:
                    await mobile.route("**/*", guard.handle)

            crawl_origin = _canonical(report.target_url)
            queue = deque([crawl_origin])
            visited: set[str] = set()
            snapshots: dict[str, dict] = {}
            statuses: dict[str, int | None] = {}
            pair_candidates: set[tuple[str, str]] = set()

            while queue and len(report.pages) < request.max_pages:
                url = queue.popleft()
                if url in visited:
                    continue
                visited.add(url)
                page_index = len(report.pages) + 1
                report.progress_message = f"Scanning page {page_index}/{request.max_pages}: {url}"
                save(report)

                console_errors: list[str] = []
                failures: list[dict[str, str]] = []
                page = await desktop.new_page()
                page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
                page.on("requestfailed", lambda req: failures.append({"url": req.url, "failure": req.failure or "failed"}))
                t0 = time.perf_counter()
                snapshot: dict = {}
                status: int | None = None
                try:
                    response = await page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    await page.wait_for_timeout(250)
                    status = response.status if response else None
                    effective_url = _canonical(page.url) if page.url else url
                    if page_index == 1 and not same_origin(crawl_origin, effective_url):
                        # Common case: example.com -> www.example.com. Continue crawling the final canonical origin.
                        crawl_origin = effective_url
                    visited.add(effective_url)
                    statuses[effective_url] = status
                    report.issues.extend(analyze_status(status, effective_url))

                    if status is not None and status < 400:
                        snapshot = await page.evaluate(JS_SNAPSHOT)
                        snapshots[effective_url] = snapshot
                        headers = await response.all_headers() if response else {}
                        report.issues.extend(analyze_dom(snapshot, effective_url))
                        report.issues.extend(analyze_security_headers(headers, effective_url))

                        interactions = 0
                        if request.safe_interactions:
                            interactions, interaction_errors, interaction_failures = await _safe_interactions(desktop, effective_url)
                            console_errors.extend(interaction_errors)
                            failures.extend(interaction_failures)
                        report.issues.extend(analyze_runtime(console_errors, failures, effective_url))

                        if page_index <= 3:
                            try:
                                await page.screenshot(path=str(screenshots_dir / f"desktop-{page_index:02}.png"), full_page=True)
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
                            if same_origin(crawl_origin, joined) and joined not in visited and len(queue) < request.max_pages * 4:
                                queue.append(joined)

                        if request.bilingual_parity:
                            pair = _locale_pair(effective_url)
                            if pair:
                                en_url, ar_url = _canonical(pair[0]), _canonical(pair[1])
                                pair_candidates.add((en_url, ar_url))
                                other = ar_url if effective_url == en_url else en_url
                                if other not in visited:
                                    queue.appendleft(other)

                        if mobile:
                            mp = await mobile.new_page()
                            try:
                                mr = await mp.goto(effective_url, wait_until="domcontentloaded", timeout=15000)
                                if mr and mr.status < 400:
                                    await mp.wait_for_timeout(120)
                                    mobile_snapshot = await mp.evaluate(JS_MOBILE)
                                    report.issues.extend(analyze_mobile(mobile_snapshot, effective_url))
                            finally:
                                await mp.close()
                    else:
                        interactions = 0

                    load_ms = int((time.perf_counter() - t0) * 1000)
                    report.pages.append(PageResult(
                        url=effective_url,
                        status_code=status,
                        title=snapshot.get("title", ""),
                        lang=snapshot.get("lang", ""),
                        direction=snapshot.get("dir", ""),
                        load_ms=load_ms,
                        dom_content_loaded_ms=snapshot.get("dom_content_loaded_ms"),
                        load_event_ms=snapshot.get("load_event_ms"),
                        dom_elements=int(snapshot.get("dom_elements") or 0),
                        resource_count=int(snapshot.get("resource_count") or 0),
                        transfer_kb=int(snapshot.get("transfer_kb") or 0),
                        links_found=len(snapshot.get("links", [])),
                        console_errors=len(set(console_errors)),
                        request_failures=len({(x.get("url"), x.get("failure")) for x in failures}),
                        safe_interactions_tested=interactions,
                    ))
                except Exception as exc:
                    statuses[url] = None
                    report.issues.extend(analyze_status(None, url))
                    report.pages.append(PageResult(
                        url=url,
                        status_code=None,
                        load_ms=int((time.perf_counter() - t0) * 1000),
                        navigation_error=f"{type(exc).__name__}: {exc}",
                    ))
                finally:
                    await page.close()

            if request.bilingual_parity:
                checked = 0
                for en_url, ar_url in pair_candidates:
                    if en_url in snapshots and ar_url in snapshots:
                        report.issues.extend(compare_parity(snapshots[en_url], snapshots[ar_url], en_url, ar_url))
                        checked += 1
                    elif en_url in snapshots and statuses.get(ar_url) is not None and (statuses.get(ar_url) or 0) >= 400:
                        report.issues.append(issue(
                            "bilingual-parity", "high", "Arabic counterpart is missing",
                            "The English page exists, but the matching Arabic route returned an error.", ar_url,
                            {"english_url": en_url, "arabic_url": ar_url, "arabic_status": statuses.get(ar_url)},
                            "Create or restore the Arabic counterpart and keep routes synchronized.",
                        ))
                        checked += 1
                report.parity_pairs_checked = checked

            await desktop.close()
            if mobile:
                await mobile.close()
            await browser.close()

        report.issues.extend(analyze_site(report.pages, report.target_url))
        dedup: dict[tuple[str, str, str], object] = {}
        for item in report.issues:
            dedup.setdefault((item.page_url, item.title, item.viewport), item)
        report.issues = list(dedup.values())
        report.pages_scanned = len(report.pages)
        report.score = score_report(report.issues)
        _apply_regression(report)
        report.status = "completed"
        report.progress_message = "Completed"
    except asyncio.CancelledError:
        report.status = "canceled"
        report.progress_message = "Canceled"
        report.error = None
        raise
    except Exception as exc:
        report.status = "failed"
        report.error = f"{type(exc).__name__}: {exc}"
        report.progress_message = "Scan failed"
    finally:
        report.finished_at = utc_now()
        report.duration_ms = int((time.perf_counter() - started) * 1000)
        save(report)
