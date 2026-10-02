# AutoQA UAE — Capstone handoff

This branch is a non-destructive handoff because the connected GitHub integration cannot create a new repository. The default `main` branch of Vui was not modified.

The complete standalone project is attached here as `autoqa-uae.zip`.

## Included
- FastAPI dashboard/API
- Playwright same-origin crawler
- accessibility/DOM checks
- mobile responsive checks
- JavaScript/network failure capture
- safe interaction smoke tests
- Arabic/English functional parity checks
- seeded bilingual demo site
- tests, Docker, and GitHub Actions CI
- full README and capstone evaluation plan

Local validation performed before upload:
- Python/API tests: 10/10 passed
- Browser DOM/mobile probe: 7/7 seeded checks detected
- JavaScript syntax check: passed
- Full network crawl cannot execute inside the ChatGPT host because Chromium network navigation is administratively blocked; GitHub CI is configured to run it in a normal runner.

Unzip the archive and follow its README.md for setup.
