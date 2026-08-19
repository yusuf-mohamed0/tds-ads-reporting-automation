# Implementation Roadmap

## Phase 0: Finalize Report Spec

Inputs needed:

- Current sample report PDF/screenshots.
- Agency logo and brand colors.
- List of all clients/accounts.
- Goal definitions and conversion mappings.

Deliverables:

- Final PDF layout.
- Exact metric list.
- Exact chart list.
- Manual notes strategy.

Acceptance criteria:

- Sample report sections are mapped to API fields or marked manual.
- Stakeholder approves report wireframe.

## Phase 1: Project Skeleton

Deliverables:

- Python package structure.
- Config loader.
- `.env` loader.
- Client YAML validation.
- Logging.
- CLI commands.

Acceptance criteria:

- `run-report --client client_a --month YYYY-MM` loads config and prints planned actions.

## Phase 2: Meta Extractor

Deliverables:

- Meta API client.
- Account, campaign, daily insights queries.
- Action/result mapper.
- Raw response persistence.

Acceptance criteria:

- One Meta client report data matches Meta UI within expected reporting settings.

## Phase 3: Normalization And Storage

Deliverables:

- SQLite schema.
- Raw pulls table.
- Normalized metrics table.
- Idempotent upserts.
- Month-over-month data loading.

Acceptance criteria:

- Rerunning same client/month does not duplicate rows.

## Phase 4: PDF Template

Deliverables:

- HTML/CSS report template.
- KPI cards.
- Tables.
- Charts.
- PDF rendering.

Acceptance criteria:

- One client PDF visually matches approved sample/report direction.

## Phase 5: Email Automation

Deliverables:

- Gmail API or SMTP sender.
- Attachment handling.
- Email status logging.
- Internal run summary email.

Acceptance criteria:

- Test PDF is emailed to `reports@trafficdigitalsolutions.com`.

## Phase 6: Batch Runner

Deliverables:

- Run all active clients.
- Continue on client failure.
- Retry failed email sends.
- Generate run summary.

Acceptance criteria:

- All configured clients process in one run.
- Failures are isolated and clear.

## Phase 7: Linux Scheduling

Deliverables:

- systemd service file.
- systemd timer file.
- Manual rerun commands.
- Logs directory.

Acceptance criteria:

- Timer runs monthly without manual intervention.

## Phase 8: QA And Production Hardening

Deliverables:

- Data comparison checklist.
- Error handling improvements.
- Token health check.
- Backup procedure.

Acceptance criteria:

- First full monthly run reviewed against manual reports.
- Numbers are approved.
- Automation can replace manual screenshot process.

## Build Priority

Recommended order:

1. Sample report mapping.
2. Config and Meta data extraction.
3. PDF generation.
4. Email sending.
5. Scheduler.
6. Polish and alerts.
