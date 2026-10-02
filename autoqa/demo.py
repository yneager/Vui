from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter()

BASE_STYLE = """
<style>
body{font-family:Arial,sans-serif;margin:0;background:#f7f8fb;color:#1d2433}header{background:#152238;color:white;padding:18px 6vw}nav{display:flex;gap:18px;align-items:center}nav a{color:white}.wrap{padding:36px 6vw;max-width:900px}.card{background:white;padding:24px;border-radius:14px;margin:20px 0;box-shadow:0 8px 30px #0001}button{padding:8px 12px}.wide-bug{width:1200px;height:20px;background:#e7eefc}input{padding:8px;margin:8px 0}.muted{color:#667}
</style>
"""


def page(lang: str, body: str, *, title: str = "AutoQA Demo", rtl: bool = False, broken_lang: bool = False) -> str:
    lang_attr = "" if broken_lang else f' lang="{lang}"'
    dir_attr = ' dir="rtl"' if rtl else ""
    return f"<!doctype html><html{lang_attr}{dir_attr}><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title>{BASE_STYLE}</head><body>{body}</body></html>"


@router.get("/demo/en", response_class=HTMLResponse)
@router.get("/demo/en/", response_class=HTMLResponse)
async def demo_en_home():
    body = """
<header><nav><a href='/demo/en/'>Home</a><a href='/demo/en/contact'>Contact</a><a href='/demo/en/pricing'>Pricing</a><a href='/demo/en/missing'>Broken link</a><a href='https://example.com' target='_blank'>Partner</a><a href='/demo/ar/'>العربية</a></nav></header>
<main class='wrap'><h1>AutoQA Seeded Demo</h1><div class='card'><h2>Starter plan</h2><p>Only AED 199 per month.</p><img src='data:image/svg+xml,%3Csvg xmlns="http://www.w3.org/2000/svg" width="80" height="40"%3E%3Crect width="80" height="40" fill="gray"/%3E%3C/svg%3E'><p id='dup'>This page intentionally contains known bugs for capstone evaluation.</p><span id='dup'>Duplicate ID seed</span><button type='button' aria-label='' aria-describedby='missing-description'></button></div><div class='wide-bug'>Intentional mobile overflow</div></main>
<script>console.error('AUTOQA_SEEDED_JS_ERROR');</script>
"""
    return page("en", body)


@router.get("/demo/ar", response_class=HTMLResponse)
@router.get("/demo/ar/", response_class=HTMLResponse)
async def demo_ar_home():
    body = """
<header><nav><a href='/demo/ar/'>الرئيسية</a><a href='/demo/ar/contact'>تواصل</a><a href='/demo/en/'>English</a></nav></header>
<main class='wrap'><h1>نسخة الاختبار</h1><div class='card'><h2>الخطة الأساسية</h2><p>فقط AED 299 شهرياً.</p><p>هذه الصفحة تحتوي على أخطاء مقصودة للاختبار.</p></div></main>
"""
    # Intentionally missing lang and dir to seed bilingual bugs.
    return page("ar", body, broken_lang=True, rtl=False)


@router.get("/demo/en/contact", response_class=HTMLResponse)
async def demo_en_contact():
    body = """
<header><nav><a href='/demo/en/'>Home</a><a href='/demo/en/contact'>Contact</a><a href='/demo/en/pricing'>Pricing</a></nav></header>
<main class='wrap'><h1>Contact us</h1><form class='card'><label for='name'>Name</label><input id='name' name='name'><input name='email' type='email' placeholder='Email without label'><textarea name='message' aria-label='Message'></textarea><button type='button'>Open details</button></form></main>
"""
    return page("en", body, title="Contact - AutoQA Demo")


@router.get("/demo/ar/contact", response_class=HTMLResponse)
async def demo_ar_contact():
    body = """
<header><nav><a href='/demo/ar/'>الرئيسية</a><a href='/demo/ar/contact'>تواصل</a></nav></header>
<main class='wrap'><h1>تواصل معنا</h1><form class='card'><label for='name'>الاسم</label><input id='name' name='name'><button type='button'>المزيد</button></form></main>
"""
    return page("ar", body, title="تواصل - نسخة الاختبار", rtl=True)


@router.get("/demo/en/pricing", response_class=HTMLResponse)
async def demo_en_pricing():
    body = """
<header><nav><a href='/demo/en/'>Home</a><a href='/demo/en/contact'>Contact</a><a href='/demo/en/pricing'>Pricing</a></nav></header>
<main class='wrap'><h1>Pricing</h1><div class='card'><p>Standard: AED 199</p><p>Premium: AED 399</p></div></main>
"""
    return page("en", body, title="Pricing - AutoQA Demo")


@router.get("/demo/ar/pricing", response_class=HTMLResponse, status_code=404)
async def demo_ar_pricing():
    return page("ar", "<main class='wrap'><h1>404</h1><p>الصفحة غير موجودة</p></main>", title="404", rtl=True)
