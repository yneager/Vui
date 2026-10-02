from autoqa.checks import (
    analyze_dom,
    analyze_mobile,
    analyze_security_headers,
    analyze_site,
    compare_parity,
    issue,
    score_report,
)
from autoqa.models import PageResult


def titles(issues):
    return {i.title for i in issues}


def test_dom_checks_find_accessibility_rtl_and_quality_bugs():
    snapshot = {
        "title": "",
        "lang": "",
        "dir": "ltr",
        "viewport_meta": False,
        "visible_text": "مرحبا بكم في الاختبار",
        "h1_texts": [],
        "images_missing_alt": ["hero.png"],
        "unlabeled_controls": [{"tag": "INPUT", "name": "email"}],
        "nameless_buttons": [{"tag": "BUTTON"}],
        "nameless_links": [{"href": "https://x/empty"}],
        "duplicate_ids": ["email"],
        "broken_aria_references": [{"attr": "aria-describedby", "missing_id": "hint"}],
        "unsafe_blank_links": [{"href": "https://external.test"}],
        "mixed_content": [],
        "password_forms_insecure": [],
        "dom_elements": 100,
        "resource_count": 4,
        "transfer_kb": 20,
    }
    found = titles(analyze_dom(snapshot, "https://example.com/ar"))
    assert "Missing page title" in found
    assert "Missing document language" in found
    assert "Missing viewport meta tag" in found
    assert "Images missing alt text" in found
    assert "Form controls missing labels" in found
    assert "Buttons without accessible names" in found
    assert "Links without accessible names" in found
    assert "Broken ARIA references" in found
    assert "New-tab links missing rel protection" in found
    assert "Arabic page is not RTL" in found


def test_mobile_overflow():
    found = titles(analyze_mobile({
        "horizontal_overflow": True,
        "overflowing_elements": [{"tag": "DIV"}],
        "scroll_width": 1000,
        "viewport_width": 390,
        "tiny_click_targets": [],
    }, "https://example.com"))
    assert "Horizontal overflow on mobile" in found


def test_bilingual_parity_finds_function_and_important_number_mismatch():
    en = {"nav_count": 4, "form_control_count": 3, "button_count": 2, "image_count": 1,
          "important_numbers": ["AED 199"], "text_chars": 500}
    ar = {"nav_count": 2, "form_control_count": 1, "button_count": 1, "image_count": 0,
          "important_numbers": ["AED 299"], "text_chars": 100}
    found = titles(compare_parity(en, ar, "https://x/en", "https://x/ar"))
    assert "Form field count differs between EN and AR" in found
    assert "Important numeric content differs between EN and AR" in found
    assert "Arabic page appears substantially shorter" in found


def test_security_header_checks():
    found = titles(analyze_security_headers({}, "https://example.com"))
    assert "HSTS header missing" in found
    assert "Content-Security-Policy header missing" in found
    assert "Clickjacking protection not detected" in found

    secure = {
        "strict-transport-security": "max-age=31536000",
        "content-security-policy": "default-src 'self'; frame-ancestors 'none'",
        "x-content-type-options": "nosniff",
        "referrer-policy": "strict-origin-when-cross-origin",
    }
    assert analyze_security_headers(secure, "https://example.com") == []


def test_duplicate_titles_are_site_level_issue():
    pages = [
        PageResult(url="https://x/a", status_code=200, title="Same"),
        PageResult(url="https://x/b", status_code=200, title="Same"),
    ]
    assert "Duplicate page title across routes" in titles(analyze_site(pages, "https://x"))


def test_issue_fingerprint_is_stable():
    a = issue("accessibility", "high", "Missing label", "x", "https://Example.com/a/")
    b = issue("accessibility", "high", "Missing label", "different evidence text", "https://example.com/a")
    assert a.id == b.id


def test_score_is_bounded():
    snapshot = {"title":"","lang":"","dir":"","viewport_meta":True,"visible_text":"","h1_texts":[],"images_missing_alt":[],"unlabeled_controls":[],"nameless_buttons":[],"nameless_links":[],"duplicate_ids":[],"broken_aria_references":[],"unsafe_blank_links":[],"mixed_content":[],"password_forms_insecure":[],"dom_elements":0,"resource_count":0,"transfer_kb":0}
    issues = analyze_dom(snapshot, "https://example.com") * 20
    assert 0 <= score_report(issues) <= 100
