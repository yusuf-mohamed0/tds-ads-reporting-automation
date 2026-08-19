# TDS Ads Reporting Automation

Local Linux automation plan for monthly Meta Ads client PDF reporting.

## Purpose

This project defines the requirements, architecture, setup process, and implementation roadmap for a local reporting app that:

- Pulls Meta Ads performance through the official Meta Marketing API.
- Pulls Facebook/Instagram Page, content, messaging, and audience insights for Business Suite reports.
- Supports around 30 clients with mixed goals.
- Generates English monthly PDF reports matching the agency's "Lodge - March 2026" reference format.
- Emails reports automatically to `reports@trafficdigitalsolutions.com`.
- Avoids browser-login automation, screenshots, 2FA bypasses, Gmail-code handling, and dashboard scraping.

## Final Recommendation

Build a local Python app that uses official APIs and generates PDFs directly.

Do not automate Meta Business Suite UI screenshots. API-based reporting is more stable, safer, easier to audit, and scalable for 30 clients.

## Repository Contents

- `docs/01-requirements.md` - full business, technical, access, data, security, and operational requirements.
- `docs/02-architecture.md` - complete architecture, data flow, modules, database, scheduler, and failure handling.
- `docs/03-meta-api-setup.md` - Meta Business/Developer setup checklist.
- `docs/05-client-config-and-data-model.md` - client mapping, goal mapping, and local database schema.
- `docs/06-report-template-spec.md` - PDF sections, metrics, charts, and narrative structure.
- `docs/06-report-template-spec-lodge.md` - exact page-by-page analysis of the "Lodge - March 2026" reference report and API mapping.
- `docs/07-security-and-operations.md` - secrets, permissions, logs, backups, monitoring, and monthly runbook.
- `docs/08-implementation-roadmap.md` - phased build plan and acceptance criteria.
- `docs/09-qa-checklist.md` - verification checklist before monthly reports are trusted.
- `configs/clients.example.yaml` - example client configuration.
- `manual_inputs/lodge_2026-03.yaml` - example of budget/VAT/notes that are manually injected into the report.
- `.env.example` - local environment variable template.

## Required Inputs Before Build

- Sample report PDF/screenshots from the current manual process.
- Meta ad account IDs for every client.
- Client goal definitions and conversion event/action names.
- Sender email method for `reports@trafficdigitalsolutions.com`.
- Brand styling: logo, colors, fonts, footer/contact details.

## Target Monthly Workflow

1. Linux scheduler runs the app on the first day of each month.
2. App calculates previous month date range.
3. App pulls each client's Meta data.
4. App normalizes metrics into one local SQLite database.
5. App generates one PDF report per client.
6. App emails PDFs to `reports@trafficdigitalsolutions.com`.
7. App writes success/failure logs and a run summary.

## Current Status

Planning and architecture package complete, now aligned to the real "Lodge - March 2026" sample report. The sample confirms reports are full Meta Business Suite reports (Reach, Messaging, Content, Audience, Ads) requiring Page/Instagram insights permissions in addition to ads access, plus manual budget/VAT/insight narrative that must be injected locally.

Implementation can start after API credentials are created and per-client page/IG access is confirmed.
