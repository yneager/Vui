from __future__ import annotations

import re
from collections import Counter
from typing import Any
from uuid import uuid4

from .models import Issue

ARABIC_RE = re.compile(r"[\u0600-\u06FF]")
RISKY_TEXT = re.compile(r"delete|remove|purchase|buy|pay|checkout|submit|send|logout|sign\s*out|unsubscribe|confirm", re.I)
SAFE_TEXT = re.compile(r"menu|open|close|expand|collapse|details|more|next|previous|search|filter|tab", re.I)


def issue(category: str, severity: str, title: str, description: str, page_url: str,
          evidence: dict[str, Any] | None = None, recommendation: str = "", viewport: str = "desktop") -> Issue:
    return Issue(
        id=uuid4().hex[:12], category=category, severity=severity, title=title,
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

    duplicate_ids = snapshot.get("duplicate_ids") or []
    if duplicate_ids:
        out.append(issue("html", "medium", "Duplicate element IDs",
                         f"Found duplicate IDs: {', '.join(duplicate_ids[:8])}.", url,
                         {"ids": duplicate_ids[:20]}, "Ensure each id attribute is unique within the document."))

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
        out.append(issue("network", "high", "Failed network requests",
                         f"Detected {len(request_failures)} failed request(s).", url,
                         {"requests": request_failures[:8]}, "Inspect failing resources/API calls and their status/CORS configuration."))
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
        if a != b and abs(a-b) >= 1:
            sev = "high" if key == "form_control_count" else "medium"
            out.append(issue("bilingual-parity", sev, f"{label} differs between EN and AR",
                             f"English has {a}; Arabic has {b}.", ar_url,
                             {"english_url": en_url, "arabic_url": ar_url, "english": a, "arabic": b},
                             "Check whether the Arabic page is missing functionality or content."))

    en_nums = Counter(en.get("important_numbers") or [])
    ar_nums = Counter(ar.get("important_numbers") or [])
    if en_nums and ar_nums and en_nums != ar_nums:
        out.append(issue("bilingual-parity", "high", "Numeric content differs between EN and AR",
                         "Prices, amounts, dates, or other prominent numeric tokens differ between language versions.", ar_url,
                         {"english_url": en_url, "arabic_url": ar_url,
                          "english_numbers": list(en_nums.elements())[:20], "arabic_numbers": list(ar_nums.elements())[:20]},
                         "Verify that prices, dates, quantities, and other numeric facts are synchronized."))

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


def score_report(issues: list[Issue]) -> int:
    weights = {"critical": 18, "high": 8, "medium": 3, "low": 1, "info": 0}
    deduction = sum(weights[i.severity] for i in issues)
    return max(0, min(100, 100 - deduction))
