# Requirements

## Business Requirements

- Generate monthly paid ads reports for around 30 clients.
- Run locally on a Linux device controlled by Traffic Digital Solutions.
- Produce English PDF reports only.
- Email generated reports automatically to `reports@trafficdigitalsolutions.com`.
- Support clients with Meta Ads (Facebook & Instagram).
- Support mixed goals: leads, messages, purchases, calls, traffic, awareness, and custom conversions.
- Preserve a consistent agency-branded report structure.
- Reduce monthly manual screenshot/reporting work as close to zero as practical.

## Non-Goals

- Do not automate browser login to Meta Business Suite.
- Do not automate Gmail verification codes, 2FA prompts, captchas, or device checks.
- Do not scrape screenshots as the primary reporting method.
- Do not store client passwords.
- Do not send reports directly to clients until the agency approves the workflow. Initial recipient is `reports@trafficdigitalsolutions.com`.

## Platform Requirements

### Linux Device

- Python 3.11 or newer.
- Git.
- Cron or systemd timer.
- Chromium/Chrome if HTML-to-PDF rendering uses browser rendering.
- Stable internet connection during scheduled runs.
- Disk space for logs, SQLite database, cached raw API results, and monthly PDFs.

### Python Packages

Recommended implementation packages:

- `requests` or Meta Business SDK for Meta API.
- `pandas` for data normalization.
- `pydantic` for config validation.
- `PyYAML` for client config.
- `Jinja2` for report HTML templates.
- `WeasyPrint` or Playwright/Chromium for PDF rendering.
- `matplotlib`, `plotly`, or `altair` for charts.
- `sqlite-utils` or SQLAlchemy for SQLite persistence.
- `python-dotenv` for local config loading.
- `keyring` optional for local secret storage.

## Meta Access Requirements

The reference report ("Lodge - March 2026") is a full **Meta Business Suite** report covering Reach, Messaging, Content, Audience, and Ads across Facebook and Instagram. This requires more than ads access.

- Meta Business Manager admin access.
- Meta Developer account.
- Meta App owned by the Business Manager.
- Marketing API available for the app.
- Permissions required (superset):
  - `ads_read`
  - `pages_read_engagement`
  - `pages_read_user_content`
  - `pages_show_list`
  - `read_insights`
  - `instagram_manage_insights` / IG insights scopes
  - `pages_messaging` / messaging insights scopes if conversational metrics are needed
- Business System User created in Business Settings, OR a user/page-access-token covering every FB Page and IG professional account referenced by client reports.
- Every client ad account assigned to the System User with reporting access; every FB Page and IG account assigned/linked for insights.
- Access token covering all pages/IG accounts, stored securely.
- Ad account IDs in `act_<ID>` format, plus Page IDs and Instagram IDs (or handles) for content/audience/messaging metrics.

## Email Requirements

Preferred email method:

- Gmail API OAuth for the mailbox that sends to `reports@trafficdigitalsolutions.com`.

Acceptable simpler method:

- SMTP with Gmail App Password if allowed for the sender mailbox.

Required email behavior:

- Attach one or more PDFs.
- Send run summary to `reports@trafficdigitalsolutions.com`.
- Log each email success/failure.
- Never automate Gmail browser login.

## Client Data Requirements

Each client needs:

- Internal client ID.
- Client display name.
- Report recipient, initially `reports@trafficdigitalsolutions.com`.
- Currency.
- Timezone.
- Monthly budget if available.
- Enabled platforms.
- Meta ad account IDs.
- Primary goal.
- Secondary goals.
- Meta conversion action mapping.
- Optional campaign naming rules.
- Optional manual notes/recommendation overrides.

## Reporting Requirements

Each report should include only platforms enabled for that client.

Required sections:

- Cover page.
- Executive summary.
- Overall monthly KPI cards.
- Reach (FB + IG, organic vs paid breakdown).
- Messaging / conversations (FB + IG, organic vs paid).
- Content performance (top posts/media).
- Audience demographics + followers.
- Meta Ads section when enabled (campaign tables).
- Campaign performance table.
- Best performers.
- Weak performers.
- Budget / Spend / VAT / Remaining.
- Manual narrative insights (account manager review, optionally AI-drafted).
- Recommendations and next steps.
- Appendix or definitions if needed.

## Manual Inputs Required Per Client Per Month

The reference report includes values that are not in any API:

- Monthly budget (e.g. EGP 63,600).
- Amount spent (API-provided) and VAT amount.
- Remaining budget.
- Currency.
- Report Scope prose.
- Insights commentary and recommendations.

These must be stored locally in client/month configuration or an editable notes file, then injected into the generated PDF.

## Reliability Requirements

- Every monthly run must produce a run summary.
- One client failure must not stop all other client reports.
- API errors must be logged with platform, client, account, date range, and error message.
- Generated reports must be saved locally even if email sending fails.
- The system must support rerunning one client/month safely without duplicating database rows.

## Compliance And Safety Requirements

- Use official APIs and approved permissions.
- Store tokens outside Git.
- Restrict Linux file permissions for `.env` and secrets.
- Do not include full secrets in logs.
- Do not share raw client data outside the local machine except report email output.
- Keep audit logs for generated reports and email delivery.
