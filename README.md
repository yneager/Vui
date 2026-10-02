# AutoQA UAE

**Autonomous bilingual web QA for Arabic/English websites.**

AutoQA UAE crawls a website in a real Chromium browser, checks common release-blocking problems, retests pages at a mobile viewport, and compares English/Arabic counterparts for functional parity. It is designed as a Computer Science capstone that is useful without a training dataset, government integration, or crowdsourcing.

## What it detects

- Broken/internal pages and HTTP 4xx/5xx responses
- JavaScript console errors and failed network requests
- Missing page titles and document language declarations
- Missing image alt text
- Unlabelled form controls and nameless buttons
- Duplicate DOM IDs and insecure password forms on HTTP
- Mobile horizontal overflow and undersized touch targets
- Arabic content served without `lang="ar"` / RTL direction
- EN↔AR mismatches in navigation, form fields, buttons, images, visible-content coverage and important numeric values
- Missing Arabic counterpart routes
- A small allow-list of safe non-destructive UI interactions

Every result contains severity, page URL, viewport, evidence and a recommended fix.

## Product architecture

```text
Browser UI
   │
   ▼
FastAPI API ───── JSON report storage
   │
   ▼
Scan orchestrator
   │
   ├── same-origin BFS crawler
   ├── Chromium / Playwright
   ├── desktop DOM checks
   ├── safe interaction smoke tests
   ├── mobile viewport checks
   └── EN ↔ AR parity engine
```

No LLM is required to produce findings. This keeps results deterministic and makes evaluation straightforward.

## Quick start

Requirements: Python 3.11+ and Chromium/Playwright.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn autoqa.app:app --host 0.0.0.0 --port 4173
```

Open `http://localhost:4173`.

If Chromium is installed somewhere other than Playwright's default, set:

```bash
export CHROMIUM_PATH=/path/to/chromium
```

### Docker

```bash
docker compose up --build
```

Then open `http://localhost:4173`.

## Seeded demo

The app includes a bilingual test site under `/demo/en` and `/demo/ar` with intentional bugs:

- missing image alt text
- empty button accessible name
- JavaScript console error
- mobile overflow
- missing Arabic `lang`/RTL configuration
- EN/AR form mismatch
- EN/AR price mismatch
- missing Arabic pricing route
- broken internal link

Start AutoQA and click **Scan seeded demo**. The API explicitly permits only this bundled localhost demo; arbitrary private-network targets remain blocked unless `ALLOW_PRIVATE_TARGETS=1` is set by the operator.

## CLI

```bash
python -m autoqa https://example.com --max-pages 8
```

For a private/staging site you own:

```bash
python -m autoqa http://127.0.0.1:3000 --allow-private
```

## Testing

```bash
python -m pytest -q
python scripts/browser_probe.py
python scripts/smoke.py
```

`browser_probe.py` is network-free and proves the real Chromium DOM/mobile analysis works. `smoke.py` starts the bundled demo server and runs the complete crawler against it.

GitHub Actions installs Chromium and runs all three levels automatically.

## API

Interactive OpenAPI docs are available at `/api/docs`.

### Start scan

`POST /api/scans`

```json
{
  "target_url": "https://example.com/en",
  "max_pages": 8,
  "mobile_check": true,
  "bilingual_parity": true,
  "safe_interactions": true
}
```

### Poll report

`GET /api/scans/{scan_id}`

### Recent reports

`GET /api/reports`

## Safety model

AutoQA is intentionally conservative:

- only HTTP/HTTPS targets
- private/reserved/loopback addresses blocked by default
- same-origin crawl only
- bounded page count
- no form submission
- no purchase/payment/delete/logout actions
- only a restricted class of button interactions

Use it only on websites you own or have permission to test. The scanner is a capstone/research tool, not a hardened multi-tenant commercial security scanner.

## Capstone evaluation design

A strong report can evaluate three questions:

1. **Detection effectiveness:** seed a benchmark site with known bugs and measure precision/recall by category.
2. **Bilingual parity:** create paired EN/AR pages with controlled functional/content differences and measure detection rate.
3. **Exploration efficiency:** compare bugs found per page/request against a simple static-link checker baseline.

Suggested metrics: precision, recall, F1, scan duration, pages visited, interactions attempted, and false-positive rate.

## Scope / limitations

- AutoQA does not bypass CAPTCHAs, bot protection or 2FA.
- It does not submit forms or test real payments.
- EN/AR semantic translation quality is not judged; parity is structural/content-based and deterministic.
- Heavily canvas/WebGL-native interfaces require specialized checks outside this MVP.
- Authenticated scanning can be added later using Playwright storage-state profiles.

## Suggested capstone title

**AutoQA UAE: Autonomous Functional and Bilingual Parity Testing for Arabic-English Web Applications**
