# Monthly Automation (cron)

Run the reports automatically on the 1st of each month. Works on the local
Linux machine the project is installed on.

## Script

`scripts/run-monthly.sh` generates reports for all active clients for a given
month (default: current month) and optionally emails them.

```bash
./scripts/run-monthly.sh 2026-03 --email   # fixed month + email
./scripts/run-monthly.sh                    # current month, no email
```

## Install a cron job (emails on the 1st at 09:00)

```bash
crontab -e
```

Add:

```
0 9 1 * * /root/tds-ads-reporting-automation/scripts/run-monthly.sh "$(date -d 'yesterday' +\%Y-\%m)" --email >> /root/tds-ads-reporting-automation/logs/cron.log 2>&1
```

Notes:
- `$(date -d 'yesterday' ...)` reports the *previous* month on the 1st, because
  the 1st's data is not yet finalized (Meta insights finalize ~28 days after
  the period, but daily aggregates for the prior month are available on the 1st).
- Percent signs in crontab must be escaped as `\%`.
- `.env` and `configs/clients.yaml` must exist before cron runs.

## Verify the cron schedule

```bash
crontab -l
```

## Manual run on demand

```bash
./scripts/run-monthly.sh 2026-03 --email
```

## Logging

- App logs: `logs/tds-report.log` (file + console).
- Cron output: `logs/cron.log` (redirected above).
