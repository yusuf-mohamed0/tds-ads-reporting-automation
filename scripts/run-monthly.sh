#!/usr/bin/env bash
# Monthly reporting job: generate + email reports for all active clients,
# for the given month. Defaults to the previous calendar month.
#
# Usage:
#   ./scripts/run-monthly.sh [YYYY-MM] [--email]
#
# Examples:
#   ./scripts/run-monthly.sh 2026-03 --email
#   ./scripts/run-monthly.sh            # previous calendar month, no email
set -euo pipefail
cd "$(dirname "$0")/.."

MONTH="${1:-$(date -d "$(date +%Y-%m-01) -1 day" +%Y-%m)}"
EMAIL_FLAG=""
if [[ "${2:-}" == "--email" ]]; then
  EMAIL_FLAG="--email"
fi

if [[ ! -f .env ]]; then
  echo "ERROR: .env not found. Copy .env.example to .env and fill in credentials." >&2
  exit 1
fi

if [[ ! -f configs/clients.yaml ]]; then
  echo "ERROR: configs/clients.yaml not found. Copy clients.example.yaml." >&2
  exit 1
fi

echo "=== TDS monthly report: $MONTH $(if [ -n "$EMAIL_FLAG" ]; then echo "(with email)"; fi) ==="
PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run-all --month "$MONTH" $EMAIL_FLAG
echo "=== done ==="
