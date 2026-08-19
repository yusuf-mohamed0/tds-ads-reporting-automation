# Security And Operations

## Security Principles

- Never store account passwords in this project.
- Never automate 2FA, Gmail verification codes, or browser sessions.
- Use official APIs and tokens.
- Keep all secrets out of Git.
- Restrict secrets to the local Linux user running reports.

## Secrets Storage

Development option:

- `.env` file with `chmod 600 .env`.

Better local option:

- Linux keyring or encrypted secrets file.

Never commit:

- Meta token.
- Meta app secret.
- Google refresh token.
- Google client secret.
- Gmail app password or Gmail refresh token.

## Local File Permissions

Recommended:

```bash
chmod 700 /path/to/project
chmod 600 /path/to/project/.env
chmod 700 /path/to/project/secrets
```

## Logs

Logs should include:

- Run ID.
- Client ID.
- Platform.
- Account ID.
- Date range.
- Status.
- Error message without secrets.

Logs should not include:

- Access tokens.
- Refresh tokens.
- Client secrets.
- Full raw payloads if they contain sensitive user-level data.

## Monthly Runbook

Before first monthly production run:

- Confirm Meta token works.
- Confirm email sender works.
- Confirm all client account IDs are mapped.
- Run one test client.
- Compare output numbers with Meta UI.
- Run all clients in dry-run mode.
- Approve template.

Monthly operation:

1. Scheduler runs on 1st day of month.
2. Review run summary.
3. Check failures.
4. Fix failed clients if any.
5. Rerun failed clients only.
6. Confirm email sent to `reports@trafficdigitalsolutions.com`.

## Backup

Back up monthly:

- `configs/clients.yaml`
- `data/reporting.sqlite`
- generated PDFs
- run summaries

Do not back up secrets to insecure cloud folders.

## Monitoring

Minimum:

- Final run summary email to internal address.
- Log file for each run.

Better:

- Slack/Telegram alert on failures.
- Daily API token health check during the last week of each month.

## Common Failure Cases

Meta:

- Token expired/revoked.
- System User lost account access.
- Action type changed or no longer appears.
- API rate limit.

Email:

- SMTP app password revoked.
- Gmail API token revoked.
- Attachment too large.

## Recovery Strategy

- Store generated PDF before email sending.
- Store raw API pull before normalization.
- Allow rerun by client/month/platform.
- Keep a manual send fallback for PDFs.
