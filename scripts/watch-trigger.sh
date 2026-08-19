#!/usr/bin/env bash
# Host-side watcher: executes report generation triggered by the backend
# (kivo-os) via a trigger file, then records the outcome for the backend to
# pick up. The backend's api container runs on Alpine without python, so
# generation must happen here as the host user.
#
#   data/trigger.json   {"id": "...", "month": "2026-07"}   (written by api)
#   data/last_run.json  {"id": ..., "ok": bool, ...}        (written by us)
#
# Safe to run repeatedly (flock-guarded); intended to be called from cron.
set -euo pipefail
cd "$(dirname "$0")/.."

TRIGGER="data/trigger.json"
LAST_RUN="data/last_run.json"
LOCK="data/watch.lock"

mkdir -p data logs

exec 9>"$LOCK"
flock -n 9 || { echo "watch: another run in progress"; exit 0; }

if [[ ! -f "$TRIGGER" ]]; then
  exit 0
fi

ID="$(python3 -c 'import json;print(json.load(open("data/trigger.json"))["id"])' 2>/dev/null || echo unknown)"
MONTH="$(python3 -c 'import json;print(json.load(open("data/trigger.json"))["month"])' 2>/dev/null || echo "")"

if [[ -z "$MONTH" ]]; then
  rm -f "$TRIGGER"
  exit 0
fi

echo "=== watch: generating reports for $MONTH (id=$ID) ===" >> logs/watch.log

OUT="$(mktemp)"
ERR="$(mktemp)"
set +e
PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run-all --month "$MONTH" --no-cache >"$OUT" 2>"$ERR"
RC=$?
set -e

python3 - "$ID" "$MONTH" "$RC" "$OUT" "$ERR" <<'PYEOF'
import json, sys, os
run_id, month, rc, out_path, err_path = sys.argv[1:6]
stdout = open(out_path, encoding="utf-8", errors="replace").read()[-4000:]
stderr = open(err_path, encoding="utf-8", errors="replace").read()[-2000:]
payload = {
    "id": run_id,
    "month": month,
    "ok": rc == 0,
    "exitCode": int(rc),
    "stdout": stdout,
    "stderr": stderr,
    "finishedAt": __import__("datetime").datetime.now(datetime.timezone.utc).isoformat(),
}
tmp = "data/last_run.json.tmp"
with open(tmp, "w") as f:
    json.dump(payload, f)
os.replace(tmp, "data/last_run.json")
PYEOF

rm -f "$TRIGGER" "$OUT" "$ERR"
echo "=== watch: finished id=$ID rc=$RC ===" >> logs/watch.log
exit 0