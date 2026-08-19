#!/usr/bin/env bash
# Install (idempotently) the monthly combined-report cron job.
# Runs on the 1st of each month at 09:00, generating + emailing the report
# for the previous calendar month.
#
# Usage:
#   ./scripts/install-monthly-cron.sh
set -euo pipefail
cd "$(dirname "$0")/.."

CRON_LINE='0 9 1 * * cd /root/tds-ads-reporting-automation && ./scripts/run-monthly.sh "$(date -d "yesterday" +%Y-%m)" --email >> logs/cron.log 2>&1'

mkdir -p logs

# Backup the existing crontab (if any) before touching it.
if crontab -l > /tmp/tds-crontab-backup.txt 2>/dev/null; then
  echo "Backed up existing crontab to /tmp/tds-crontab-backup.txt"
else
  : > /tmp/tds-crontab-backup.txt
  echo "No existing crontab to back up (empty backup written to /tmp/tds-crontab-backup.txt)"
fi

# Append the line only if it is not already present (idempotent).
if crontab -l 2>/dev/null | grep -Fq "$CRON_LINE"; then
  echo "Cron job already installed; nothing to do."
else
  (crontab -l 2>/dev/null || true; echo "$CRON_LINE") | crontab -
  echo "Installed cron line:"
  echo "  $CRON_LINE"
fi