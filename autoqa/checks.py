from __future__ import annotations

import hashlib
import re
from collections import Counter, defaultdict
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from .models import Issue, PageResult

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
RISKY_TEXT = re.compile(r"delete|remove|purchase|buy|pay|checkout|submit|send|logout|sign\s*out|unsubscribe|confirm|save|book|reserve", re.I)
SAFE_TEXT = re.compile(r"menu|open|close|expand|collapse|details|more|next|previous|search|filter|tab|accordion|toggle", re.I)


def _stable_url(raw: str) -> str:
    p = urlsplit(raw)
    return urlunsplit((p.scheme.lower(), (p.netloc or "").lower(), p.path.rstrip("/") or "/", p.query, ""))


def issue(category: str, severity: str, title: str, description: str, page_url: str,
          evidence: dict[str, Any] | None = None, recommendation: str = "", viewport: str = "desktop") -> Issue:
    fingerprint = hashlib.sha1(
        f"{category}|{title}|{_stable_url(page_url)}|{viewport}".encode("utf-8")
    ).hexdigest()[:12]
    return Issue(
        id=fingerprint, category=category, severity=severity, title=title,
        description=description, page_url=page_url, evidence=evidence or {},
        recommendation=recommendation, viewport=viewport,
    )


def analyze_dom(snapshot: dict[str, Any], url: str) -> list[Issue]:
    out: list[Issue] = []
    title = (snapshot.get("title") or "").strip()
    lang = (snapshot.get("lang") or "").strip().lower()
    direction = (snapshot.get("dir") or "").strip().lower()
    text = snapshot.get("visible_text") or ""

    if not title:
        out.append(issue("seo-accessibility", "medium", "Missing page title",
                         "The page has no meaningful <title>, which hurts accessibility and navigation.", url,
                         recommendation="Add a concise, unique <title> to every page."))
    if not lang:
        out.append(issue("accessibility", "medium", "Missing document language",
                         "The <html> element does not declare a lang attribute.", url,
                         recommendation="Set <html lang=\"en\"> or the correct page language."))
    if not snapshot.get("viewport_meta"):
        out.append(issue("responsive", "medium", "Missing viewport meta tag",
                         "The page does not declare a viewport meta tag, so mobile rendering may be scaled incorrectly.", url,
                         recommendation="Add <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">."))

    h1s = snapshot.get("h1_texts") or []
    if len(h1s) == 0:
        out.append(issue("accessibility", "low", "No H1 heading",
                         "No top-level H1 heading was found.", url,
                         recommendation="Add one descriptive H1 for the primary page topic."))
    elif len(h1s) > 1:
        out.append(issue("structure", "low", "Multiple H1 headings",
                         f"Found {len(h1s)} H1 headings.", url, {"h1s": h1s[:6]},
                         "Use a clear heading hierarchy; prefer one primary H1."))

    missing_alt = snapshot.get("images_missing_alt") or []
    if missing_alt:
        out.append(issue("accessibility", "medium", "Images missing alt text",
                         f"Found {len(missing_alt)} image(s) without alt text.", url,
                         {"examples": missing_alt[:5]}, "Add meaningful alt text, or alt=\"\" for decorative images."))

    unlabeled = snapshot.get("unlabeled_controls") or []
    if unlabeled:
        out.append(issue("accessibility", "high", "Form controls missing labels",
                         f"Found {len(unlabeled)} input/select/textarea control(s) without an accessible label.", url,
                         {"examples": unlabeled[:8]}, "Associate <label> elements or aria-label/aria-labelledby with each control."))

    nameless = snapshot.get("nameless_buttons") or []
    if nameless:
        out.append(issue("accessibility", "high", "Buttons without accessible names",
                         f"Found {len(nameless)} button(s) with no readable accessible name.", url,
                         {"examples": nameless[:8]}, "Give every button visible text, aria-label, or aria-labelledby."))

    nameless_links = snapshot.get("nameless_links") or []
    if nameless_links:
        out.append(issue("accessibility", "high", "Links without accessible names",
                         f"Found {len(nameless_links)} link(s) with no readable accessible name.", url,
                         {"examples": nameless_links[:8]}, "Give links descriptive text or an accessible label."))

    duplicate_ids = snapshot.get("duplicate_ids") or []
    if duplicate_ids:
        out.append(issue("html", "medium", "Duplicate element IDs",
                         f"Found duplicate IDs: {', '.join(duplicate_ids[:8])}.", url,
                         {"ids": duplicate_ids[:20]}, "Ensure each id attribute is unique within the document."))

    broken_aria = snapshot.get("broken_aria_references") or []
    if broken_aria:
        out.append(issue("accessibility", "medium", "Broken ARIA references",
                         f"Found {len(broken_aria)} aria-labelledby/aria-describedby reference(s) pointing to missing IDs.", url,
                         {"examples": broken_aria[:8]}, "Fix ARIA ID references so assistive technology can resolve them."))

    unsafe_blank = snapshot.get("unsafe_blank_links") or []
    if unsafe_blank:
        out.append(issue("security", "low", "New-tab links missing rel protection",
                         f"Found {len(unsafe_blank)} target=_blank link(s) without rel=noopener.", url,
                         {"examples": unsafe_blank[:8]}, "Add rel=\"noopener noreferrer\" to untrusted external target=_blank links."))

    mixed = snapshot.get("mixed_content") or []
    if mixed:
        out.append(issue("security", "high", "Mixed-content resources detected",
                         f"Found {len(mixed)} HTTP resource(s) referenced by an HTTPS page.", url,
                         {"resources": mixed[:8]}, "Serve every subresource over HTTPS."))

    if ARABIC_RE.search(text):
        if not lang.startswith("ar"):
            out.append(issue("bilingual", "medium", "Arabic content with non-Arabic page language",
                             "Arabic text was detected but the document language is not set to Arabic.", url,
                             {"lang": lang or "missing"}, "Set lang=\"ar\" on Arabic pages."))
        if direction != "rtl":
            out.append(issue("bilingual", "high", "Arabic page is not RTL",
                             "Arabic text was detected but <html dir=\"rtl\"> is not set.", url,
                             {"dir": direction or "missing"}, "Set dir=\"rtl\" and verify component mirroring."))

    insecure_forms = snapshot.get("password_forms_insecure") or []
    if insecure_forms:
        out.append(issue("security", "critical", "Password form served insecurely",
                         "A password field is present on a non-HTTPS page.", url,
                         {"forms": insecure_forms}, "Serve authentication pages only over HTTPS."))

    dom_elements = int(snapshot.get("dom_elements") or 0)
    if dom_elements > 2500:
        out.append(issue("performance", "medium", "Very large DOM",
                         f"The page contains {dom_elements:,} DOM elements, which can slow style/layout work.", url,
                         {"dom_elements": dom_elements}, "Reduce deeply nested/repeated markup and virtualize very large lists."))

    resource_count = int(snapshot.get("resource_count") or 0)
    if resource_count > 180:
        out.append(issue("performance", "low", "High resource count",
                         f"The page loaded {resource_count} resource entries.", url,
                         {"resource_count": resource_count}, "Bundle, lazy-load, or remove nonessential resources."))

    transfer_kb = int(snapshot.get("transfer_kb") or 0)
    if transfer_kb > 5000:
        out.append(issue("performance", "low", "Large page transfer size",
                         f"Browser-reported transfer size is approximately {transfer_kb / 1024:.1f} MB.", url,
                         {"transfer_kb": transfer_kb}, "Compress images/assets and lazy-load content below the fold."))

    return out


def analyze_mobile(snapshot: dict[str, Any], url: str) -> list[Issue]:
    out: list[Issue] = []
    if snapshot.get("horizontal_overflow"):
        offenders = snapshot.get("overflowing_elements") or []
        out.append(issue("responsive", "high", "Horizontal overflow on mobile",
                         "Page content is wider than the mobile viewport and may require horizontal scrolling.", url,
                         {"elements": offenders[:8], "scroll_width": snapshot.get("scroll_width"),
                          "viewport_width": snapshot.get("viewport_width")},
                         "Use responsive widths, wrapping, and overflow handling for narrow screens.", "mobile"))
    tiny = snapshot.get("tiny_click_targets") or []
    if tiny:
        out.append(issue("responsive", "low", "Small mobile click targets",
                         f"Found {len(tiny)} interactive element(s) smaller than 36×36 CSS pixels.", url,
                         {"examples": tiny[:8]}, "Increase touch target size and spacing.", "mobile"))
    return out


def analyze_runtime(console_errors: list[str], request_failures: list[dict[str, str]], url: str) -> list[Issue]:
    out: list[Issue] = []
    if console_errors:
        unique = list(dict.fromkeys(console_errors))
        out.append(issue("javascript", "high", "JavaScript console errors",
                         f"Detected {len(console_errors)} console error event(s) while loading/interacting with the page.", url,
                         {"errors": unique[:8]}, "Fix uncaught exceptions and console errors, then retest."))
    if request_failures:
        unique = []
        seen = set()
        for item in request_failures:
            key = (item.get("url"), item.get("failure"))
            if key not in seen:
                seen.add(key)
                unique.append(item)
        out.append(issue("network", "high", "Failed network requests",
                         f"Detected {len(unique)} distinct failed request(s).", url,
                         {"requests": unique[:8]}, "Inspect failing resources/API calls and their status/CORS configuration."))
    return out


def analyze_status(status: int | None, url: str) -> list[Issue]:
    if status is None:
        return [issue("network", "critical", "Page did not return an HTTP response",
                      "Navigation completed without a usable HTTP response.", url,
                      recommendation="Verify the route, DNS, TLS certificate, and server availability.")]
    if status >= 500:
        return [issue("network", "critical", f"Server error HTTP {status}",
                      "The page returned a server-side error.", url, {"status": status}, "Fix the server error before release.")]
    if status >= 400:
        return [issue("navigation", "high", f"Broken page HTTP {status}",
                      "An internal page returned an error response.", url, {"status": status}, "Fix or remove links to this route.")]
    return []


def analyze_security_headers(headers: dict[str, str], url: str) -> list[Issue]:
    out: list[Issue] = []
    h = {k.lower(): v for k, v in headers.items()}
    scheme = urlsplit(url).scheme.lower()
    csp = h.get("content-security-policy", "")

    if scheme == "https" and "strict-transport-security" not in h:
        out.append(issue("security-headers", "low", "HSTS header missing",
                         "The HTTPS response does not advertise Strict-Transport-Security.", url,
                         recommendation="Consider enabling HSTS after confirming all subdomains/resources support HTTPS."))
    if not csp:
        out.append(issue("security-headers", "low", "Content-Security-Policy header missing",
                         "No Content-Security-Policy response header was detected.", url,
                         recommendation="Add a restrictive CSP and tighten it incrementally using report-only mode first."))
    if "x-frame-options" not in h and "frame-ancestors" not in csp.lower():
        out.append(issue("security-headers", "low", "Clickjacking protection not detected",
                         "Neither X-Frame-Options nor CSP frame-ancestors was detected.", url,
                         recommendation="Use CSP frame-ancestors (preferred) or X-Frame-Options where framing is not required."))
    if h.get("x-content-type-options", "").lower() != "nosniff":
        out.append(issue("security-headers", "info", "X-Content-Type-Options not set",
                         "The response does not set X-Content-Type-Options: nosniff.", url,
                         recommendation="Add X-Content-Type-Options: nosniff."))
    if "referrer-policy" not in h:
        out.append(issue("security-headers", "info", "Referrer-Policy not set",
                         "The response does not declare a Referrer-Policy.", url,
                         recommendation="Set a policy such as strict-origin-when-cross-origin based on application needs."))
    return out


def compare_parity(en: dict[str, Any], ar: dict[str, Any], en_url: str, ar_url: str) -> list[Issue]:
    out: list[Issue] = []
    pairs = [
        ("nav_count", "Navigation item count"),
        ("form_control_count", "Form field count"),
        ("button_count", "Button count"),
        ("image_count", "Image count"),
    ]
    for key, label in pairs:
        a, b = int(en.get(key) or 0), int(ar.get(key) or 0)
        if a != b:
            sev = "high" if key == "form_control_count" else "medium"
            out.append(issue("bilingual-parity", sev, f"{label} differs between EN and AR",
                             f"English has {a}; Arabic has {b}.", ar_url,
                             {"english_url": en_url, "arabic_url": ar_url, "english": a, "arabic": b},
                             "Check whether the Arabic page is missing functionality or content."))

    en_nums = Counter(en.get("important_numbers") or [])
    ar_nums = Counter(ar.get("important_numbers") or [])
    if (en_nums or ar_nums) and en_nums != ar_nums:
        out.append(issue("bilingual-parity", "high", "Important numeric content differs between EN and AR",
                         "Currency amounts or percentages differ between language versions.", ar_url,
                         {"english_url": en_url, "arabic_url": ar_url,
                          "english_numbers": list(en_nums.elements())[:20], "arabic_numbers": list(ar_nums.elements())[:20]},
                         "Verify that prices, percentages, and other important numeric facts are synchronized."))

    en_chars = int(en.get("text_chars") or 0)
    ar_chars = int(ar.get("text_chars") or 0)
    if en_chars > 100 and ar_chars > 0:
        ratio = ar_chars / en_chars
        if ratio < 0.35:
            out.append(issue("bilingual-parity", "medium", "Arabic page appears substantially shorter",
                             f"Arabic visible text is only {ratio:.0%} of the English page length.", ar_url,
                             {"english_chars": en_chars, "arabic_chars": ar_chars},
                             "Check for untranslated or missing sections."))
    return out


def analyze_site(pages: list[PageResult], target_url: str) -> list[Issue]:
    out: list[Issue] = []
    by_title: dict[str, list[str]] = defaultdict(list)
    for page in pages:
        title = page.title.strip()
        if title and page.status_code and page.status_code < 400:
            by_title[title.casefold()].append(page.url)
    duplicates = [(title, urls) for title, urls in by_title.items() if len(urls) > 1]
    for title, urls in duplicates[:10]:
        out.append(issue("site-structure", "medium", "Duplicate page title across routes",
                         f"The same page title is used by {len(urls)} crawled routes.", target_url,
                         {"title": title, "urls": urls[:10]}, "Give indexable pages unique, descriptive titles."))
    return out


def score_report(issues: list[Issue]) -> int:
    weights = {"critical": 18, "high": 8, "medium": 3, "low": 1, "info": 0}
    deduction = sum(weights[i.severity] for i in issues)
    return max(0, min(100, 100 - deduction))
