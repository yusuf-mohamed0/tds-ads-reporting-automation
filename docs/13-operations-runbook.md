# Operations Runbook

How to run the monthly reporting cycle, refresh tokens, and handle failures.

## Monthly cycle

1. **Fill manual inputs** for each client/month:
   `manual_inputs/{client_id}_{YYYY-MM}.yaml`
   ```yaml
   budget:
     amount: 63600        # EGP
     spent: 42834
     vat: 48830
     remaining: 14770
   scope_prose: "Monthly focus: engagement through messaging + profile visits."
   scope_notes: ""
   insights:
     - "Reach up X% month over month."
     - "Total messages 1.6K, 87% paid."
   recommendations:
     - "Continue the messages campaign."
   ```
   Copy the sample in `manual_inputs/lodge_2026-03.yaml` (from earlier work).

2. **Dry-run one client** to verify config:
   ```bash
   cd /root/tds-ads-reporting-automation
   export GH_TOKEN="<REDACTED_GITHUB_TOKEN>"   # only for git push
   PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run \
     --client lodge --month 2026-03 --dry-run
   ```

3. **Generate one report (no email):**
   ```bash
   PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run \
     --client lodge --month 2026-03
   ```
   Output: `reports/lodge_2026-03.pdf`

4. **Generate + email one report:**
   ```bash
   PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run \
     --client lodge --month 2026-03 --email
   ```

5. **Generate reports for all active clients** (skips missing manual inputs gracefully):
   ```bash
   PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run-all --month 2026-03 --email
   ```
   Failures are logged per client (`fail <id>: <error>`) and do not stop others.

## Report render without API (offline / testing)

```bash
PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run \
  --client lodge --month 2026-03 --no-fetch
```
Renders with manual inputs only; API sections stay empty.

## Token refresh (Meta, 60-day tokens)

- System user token expires every 60 days. Refresh before expiry:
  ```
  GET /oauth/access_token
      ?grant_type=fb_exchange_token
      &client_id=<APP_ID>
      &client_secret=<APP_SECRET>
      &fb_exchange_token=<CURRENT_TOKEN>
      &set_token_expires_in_60_days=true
  ```
- Update `META_SYSTEM_USER_TOKEN` in `.env`.
- Page tokens: regenerate from Graph API Explorer if they stop working.

## Error handling

| Symptom | Cause | Fix |
|---|---|---|
| `MissingCredentialError` | env not set | Fill `.env` from `.env.example` |
| Meta `80004/80000` | ad-account rate limit | Wait, retry with backoff (module already retries) |
| Meta `4` / `17` | app/user limit | Spread queries over the day |
| Meta `#100 invalid metric` | metric name changed/retired | Check `docs/11-api-knowledge.md` metric table |
| Meta `#190` | token expired | Refresh token (above) |
| `TemplateNotFound` | wrong CWD | Always run from project root |
| PDF blank sections | no data for that platform | Expected when client doesn't use that platform |

## Testing

```bash
PYTHONPATH=src .venv/bin/python -m unittest discover tests
```

## Git / GitHub

```bash
export GH_TOKEN="<REDACTED_GITHUB_TOKEN>"
git add -A
git -c user.name="Traffic Digital Solutions" -c user.email="reports@trafficdigitalsolutions.com" \
  commit -m "message"
git push origin main
```
**Security:** rotate the GH token after finalizing (it sits in a plaintext git config).

## Logging / observability

- `logs/` reserved for future structured logging.
- `data/reporting.sqlite` reserved for caching historical months (planned).
- Caching recommendation: store per-month summaries in SQLite to avoid
  re-fetching and to stay under quota.
