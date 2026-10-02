# AutoQA UAE v1.1

**Autonomous functional, accessibility, responsive, security and Arabic/English parity testing for websites.**

AutoQA UAE opens a target in a real Chromium browser, crawls same-origin routes, runs deterministic QA checks, exercises a small allow-list of non-destructive UI controls, retests pages at a mobile viewport, and compares `/en` and `/ar` counterparts. It is designed as a Computer Science capstone that does **not** require a training dataset, government integration, crowdsourcing, or an LLM.

## What v1.1 detects

- Broken/internal pages and HTTP 4xx/5xx responses
- JavaScript console errors and failed browser requests
- Missing page titles, H1s, document language and viewport metadata
- Missing image alt text, labels and accessible names
- Broken `aria-labelledby` / `aria-describedby` references
- Duplicate DOM IDs
- Mobile horizontal overflow and undersized click targets
- Arabic content with incorrect `lang` or RTL configuration
- EN↔AR mismatches in navigation, forms, buttons, images, content coverage and important numeric values such as AED prices/percentages
- Missing Arabic counterpart routes
- Mixed-content resources
- HSTS, CSP, clickjacking, `nosniff` and Referrer-Policy signals
- Oversized DOM/resource-count/transfer-size heuristics
- Duplicate page titles across crawled routes

Every finding has a stable fingerprint, severity, URL, evidence and recommended fix.

## Major v1.1 upgrades

- **Regression tracking:** repeated scans automatically show new, resolved and unchanged findings.
- **Stable issue fingerprints:** deterministic IDs make before/after comparisons measurable.
- **Safer interactions:** unlabeled controls are never clicked; interactions run on an isolated browser page and must match a strict safe-text allow-list.
- **DNS-aware SSRF protection:** public scans validate browser subrequests and redirects, not just the initial URL.
- **Redirect-aware crawling:** an initial `domain.com → www.domain.com` redirect no longer stops site discovery.
- **Concurrency control + cancellation:** browser scans are bounded and can be canceled from the dashboard/API.
- **Performance telemetry:** DOMContentLoaded, DOM size, resource count and browser-reported transfer size are recorded per page.
- **Exports:** download a report as JSON or standalone HTML.
- **CI threshold:** the CLI can fail a pipeline when issues reach a chosen severity.
- **Atomic report storage:** interrupted writes cannot leave half-written scan JSON files.

## Architecture

```text
Dashboard / CLI
      │
      ▼
 FastAPI API ───── atomic JSON history / regression baseline
      │
      ▼
 bounded scan queue
      │
      ▼
 Playwright + Chromium
      │
      ├── DNS-aware request guard
      ├── same-origin BFS crawler
      ├── DOM/accessibility checks
      ├── response security-header checks
      ├── isolated safe interactions
      ├── mobile viewport checks
      ├── performance telemetry
      └── EN ↔ AR parity engine
```

## Quick start

Requirements: Python 3.11+ and Chromium/Playwright.

```bash
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m playwright install chromium
uvicorn autoqa.app:app --host 0.0.0.0 --port 4173
```

Open `http://localhost:4173` and click **Scan seeded demo** first.

If Chromium is installed somewhere other than Playwright's default:

```bash
export CHROMIUM_PATH=/path/to/chromium
```

### Docker

```bash
docker compose up --build
```

## Seeded capstone demo

The bundled `/demo/en` and `/demo/ar` site intentionally contains controlled bugs including missing alt/accessibility names, duplicate IDs, a broken ARIA reference, a JS error, mobile overflow, broken links, unsafe new-tab markup, incomplete Arabic forms, price mismatches, incorrect RTL metadata and a missing Arabic pricing route.

This gives you a deterministic ground-truth benchmark for precision/recall experiments instead of relying only on arbitrary live websites.

## CLI

```bash
python -m autoqa https://example.com/en --max-pages 8
```

Use it as a CI quality gate:

```bash
python -m autoqa https://staging.example.com/en --max-pages 12 --fail-on high
```

Exit codes:

- `0`: scan completed and threshold not exceeded
- `1`: issue at/above the selected `--fail-on` threshold
- `2`: scan itself failed/could not complete

For localhost/private staging systems you control:

```bash
python -m autoqa http://127.0.0.1:3000 --allow-private
```

## API

Interactive OpenAPI docs: `/api/docs`.

- `POST /api/scans` — start a scan
- `GET /api/scans/{id}` — poll/read report
- `DELETE /api/scans/{id}` — cancel queued/running scan
- `GET /api/scans/{id}/export.json` — download JSON report
- `GET /api/scans/{id}/export.html` — download standalone HTML report
- `GET /api/reports` — recent scans

Example request:

```json
{
  "target_url": "https://example.com/en",
  "max_pages": 8,
  "mobile_check": true,
  "bilingual_parity": true,
  "safe_interactions": true
}
```

## Safety model

AutoQA is intentionally conservative:

- only HTTP/HTTPS targets
- private/reserved/loopback targets blocked by default
- DNS-aware guards for browser subrequests and redirects
- same-origin crawl after the initial canonical redirect
- bounded page count and concurrent browsers
- no form submission
- no purchase/payment/delete/book/save/logout actions
- unlabeled buttons are never clicked
- allowed interactions execute on an isolated page so they do not mutate the crawler state

Set `ALLOW_PRIVATE_TARGETS=1` only in a trusted local/staging environment that you control.

Use AutoQA only on sites you own or have permission to test. It is a capstone/research QA tool, not a hardened multi-tenant commercial security scanner.

## Testing

```bash
python -m compileall -q autoqa tests scripts
node --check autoqa/static/app.js
python -m pytest -q
python scripts/browser_probe.py
python scripts/smoke.py
```

GitHub Actions installs Chromium and runs syntax checks, the unit/API suite, a real browser DOM probe, the full seeded-site crawler, and a second scan to verify regression fingerprints.

## Capstone evaluation plan

A strong final report can answer four measurable questions:

1. **Detection effectiveness** — seed known bugs and measure precision, recall and F1 by category.
2. **Bilingual parity effectiveness** — control EN/AR differences and measure detection rate/false positives.
3. **Exploration efficiency** — compare findings per page/time against a static-link checker baseline.
4. **Regression stability** — rerun unchanged/fixed seeded sites and measure correct classification of new/resolved/unchanged issues.

Also report scan duration, pages visited, interactions attempted, DOM/resource telemetry and false-positive rate.

## Scope / limitations

- No CAPTCHA, bot-protection or 2FA bypass.
- No real form submission or payment testing.
- Arabic translation *quality* is not judged; parity is deterministic/structural plus selected content tokens.
- Security-header checks are best-practice signals, not a penetration test.
- Browser-reported transfer sizes can be incomplete for some cross-origin resources.
- Canvas/WebGL-heavy applications need specialized visual/state instrumentation.
- Authenticated scanning can be added later using Playwright storage-state profiles.

## Suggested capstone title

**AutoQA UAE: Autonomous Functional and Bilingual Parity Testing for Arabic-English Web Applications**
