#!/usr/bin/env bash
# Install (idempotently) the monthly combined-report cron job and the
# trigger-watcher cron job. All paths are resolved from the script location,
# so this works regardless of where the runner lives on the host.
#
#   - Monthly: 1st of each month at 09:00, generate + email previous month.
#   - Watcher: every 2 minutes, serve backend-triggered generations.
#
# Usage:
#   ./scripts/install-monthly-cron.sh
set -euo pipefail
cd "$(dirname "$0")/.."
RUNNER_ROOT="$(pwd)"

MONTHLY_CRON="0 9 1 * * cd $RUNNER_ROOT && ./scripts/run-monthly.sh \"\$(date -d \"yesterday\" +%Y-%m)\" --email >> logs/cron.log 2>&1"
WATCH_CRON="*/2 * * * * cd $RUNNER_ROOT && ./scripts/watch-trigger.sh >> logs/watch.log 2>&1"

mkdir -p logs

# Backup the existing crontab (if any) before touching it.
if crontab -l > /tmp/tds-crontab-backup.txt 2>/dev/null; then
  echo "Backed up existing crontab to /tmp/tds-crontab-backup.txt"
else
  : > /tmp/tds-crontab-backup.txt
  echo "No existing crontab to back up (empty backup written to /tmp/tds-crontab-backup.txt)"
fi

for entry in "$MONTHLY_CRON" "$WATCH_CRON"; do
  if crontab -l 2>/dev/null | grep -Fq "$entry"; then
    echo "Cron already installed: $entry"
  else
    (crontab -l 2>/dev/null || true; echo "$entry") | crontab -
    echo "Installed cron line:"
    echo "  $entry"
  fi
done