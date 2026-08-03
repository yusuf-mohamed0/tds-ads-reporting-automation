# Requirements

## Business Requirements

- Generate monthly paid ads reports for around 30 clients.
- Run locally on a Linux device controlled by Traffic Digital Solutions.
- Produce English PDF reports only.
- Email generated reports automatically to `reports@trafficdigitalsolutions.com`.
- Support clients with Meta Ads only, Google Ads only, or both.
- Support mixed goals: leads, messages, purchases, calls, traffic, awareness, and custom conversions.
- Preserve a consistent agency-branded report structure.
- Reduce monthly manual screenshot/reporting work as close to zero as practical.

## Non-Goals

- Do not automate browser login to Meta Business Suite or Google Ads.
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

- `google-ads` for Google Ads API.
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

- Meta Business Manager admin access.
- Meta Developer account.
- Meta App owned by the Business Manager.
- Marketing API available for the app.
- `ads_read` permission minimum.
- Business System User created in Business Settings.
- Every client ad account assigned to the System User with reporting access.
- System User access token generated and stored securely.
- Ad account IDs for every client in `act_<ID>` format.

## Google Ads Access Requirements

- Google Ads Manager Account / MCC with access to all client accounts.
- Google Cloud project.
- Google Ads API enabled.
- OAuth Client ID and Client Secret.
- Google Ads Developer Token from API Center.
- OAuth refresh token for the MCC/admin account.
- MCC customer ID used as `login-customer-id`.
- Client Google Ads customer IDs.

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
- Google Ads customer IDs.
- Primary goal.
- Secondary goals.
- Meta conversion action mapping.
- Google Ads conversion action mapping.
- Optional campaign naming rules.
- Optional manual notes/recommendation overrides.

## Reporting Requirements

Each report should include only platforms enabled for that client.

Required sections:

- Cover page.
- Executive summary.
- Overall monthly KPI cards.
- Platform split: Meta vs Google Ads when both exist.
- Meta Ads section when enabled.
- Google Ads section when enabled.
- Campaign performance table.
- Best performers.
- Weak performers.
- Month-over-month comparison.
- Recommendations and next steps.
- Appendix or definitions if needed.

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
