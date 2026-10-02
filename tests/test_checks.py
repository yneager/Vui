from autoqa.checks import analyze_dom, analyze_mobile, compare_parity, score_report


def titles(issues):
    return {i.title for i in issues}


def test_dom_checks_find_accessibility_and_rtl_bugs():
    snapshot = {
        "title": "",
        "lang": "",
        "dir": "ltr",
        "visible_text": "مرحبا بكم في الاختبار",
        "h1_texts": [],
        "images_missing_alt": ["hero.png"],
        "unlabeled_controls": [{"tag": "INPUT", "name": "email"}],
        "nameless_buttons": [{"tag": "BUTTON"}],
        "duplicate_ids": ["email"],
        "password_forms_insecure": [],
    }
    found = titles(analyze_dom(snapshot, "https://example.com/ar"))
    assert "Missing page title" in found
    assert "Missing document language" in found
    assert "Images missing alt text" in found
    assert "Form controls missing labels" in found
    assert "Buttons without accessible names" in found
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


def test_bilingual_parity_finds_function_and_number_mismatch():
    en = {"nav_count": 4, "form_control_count": 3, "button_count": 2, "image_count": 1,
          "important_numbers": ["AED 199"], "text_chars": 500}
    ar = {"nav_count": 2, "form_control_count": 1, "button_count": 1, "image_count": 0,
          "important_numbers": ["AED 299"], "text_chars": 100}
    found = titles(compare_parity(en, ar, "https://x/en", "https://x/ar"))
    assert "Form field count differs between EN and AR" in found
    assert "Numeric content differs between EN and AR" in found
    assert "Arabic page appears substantially shorter" in found


def test_score_is_bounded():
    snapshot = {"title":"","lang":"","dir":"","visible_text":"","h1_texts":[],"images_missing_alt":[],"unlabeled_controls":[],"nameless_buttons":[],"duplicate_ids":[],"password_forms_insecure":[]}
    issues = analyze_dom(snapshot, "https://example.com") * 20
    assert 0 <= score_report(issues) <= 100
