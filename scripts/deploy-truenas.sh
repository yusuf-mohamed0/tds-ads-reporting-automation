#!/usr/bin/env bash
# Deploy tds-ads-reporting-automation to TrueNAS
#
# Usage:
#   1. SSH into your TrueNAS Ubuntu VM
#   2. Run this script: bash deploy-truenas.sh
#
# Prerequisites:
#   - Ubuntu Server VM running on TrueNAS
#   - SSH access to the VM
#   - Internet access (for git clone, pip install)
set -euo pipefail

echo "=== TDS Ads Reporting Automation — TrueNAS Deploy ==="

# --- Config ---
REPO_URL="https://github.com/yusuf-mohamed0/tds-ads-reporting-automation.git"
INSTALL_DIR="/opt/tds-reporter"
PYTHON_MIN="3.10"

# --- Check Python ---
echo "[1/6] Checking Python..."
if ! command -v python3 &>/dev/null; then
    echo "Python3 not found. Installing..."
    sudo apt-get update -qq
    sudo apt-get install -y -qq python3 python3-pip python3-venv
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "  Python version: $PY_VER"

# --- Clone or pull repo ---
echo "[2/6] Setting up repository..."
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Repo exists at $INSTALL_DIR — pulling latest..."
    cd "$INSTALL_DIR"
    git pull origin main
else
    echo "  Cloning repo to $INSTALL_DIR..."
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$(whoami)" "$INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# --- Create venv and install deps ---
echo "[3/6] Setting up Python environment..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
echo "  Dependencies installed."

# --- Check for .env ---
echo "[4/6] Checking credentials..."
if [ ! -f ".env" ]; then
    echo "  Creating .env from example..."
    cp .env.example .env 2>/dev/null || cat > .env << 'ENVEOF'
# Meta API credentials
META_SYSTEM_USER_TOKEN=your_system_user_token_here
META_PAGE_ACCESS_TOKEN=your_page_access_token_here
META_API_VERSION=v26.0

# Email (SMTP) — optional
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASS=your_app_password
EMAIL_FROM=reports@trafficdigitalsolutions.com
ENVEOF
    echo "  ⚠️  Edit .env with your actual Meta API tokens!"
    echo "     nano $INSTALL_DIR/.env"
else
    echo "  .env already exists."
fi

# --- Check for clients.yaml ---
if [ ! -f "configs/clients.yaml" ]; then
    echo "  ⚠️  configs/clients.yaml not found!"
    echo "     Copy from configs/clients.example.yaml and configure your clients."
fi

# --- Install cron jobs ---
echo "[5/6] Installing cron jobs..."
mkdir -p logs

# Monthly cron: 1st of each month at 09:00 (Cairo time)
MONTHLY_CRON="0 9 1 * * cd $INSTALL_DIR && PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run-all --month \$(date -d 'yesterday' +\\%Y-\\%m) --email >> logs/cron.log 2>&1"

# Backup crontab
crontab -l > /tmp/tds-crontab-backup.txt 2>/dev/null || true

if crontab -l 2>/dev/null | grep -Fq "tds_ads_reporting"; then
    echo "  Cron already installed."
else
    (crontab -l 2>/dev/null || true; echo "$MONTHLY_CRON") | crontab -
    echo "  Installed monthly cron (1st at 09:00)."
fi

# --- Test run ---
echo "[6/6] Testing report generation..."
cd "$INSTALL_DIR"
PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run --client 3-towers --month 2026-08 --dry-run 2>&1 | tail -5 || echo "  ⚠️  Dry-run failed. Check .env and configs/clients.yaml."

echo ""
echo "=== Deploy Complete ==="
echo "Location: $INSTALL_DIR"
echo ""
echo "Next steps:"
echo "  1. Edit .env:  nano $INSTALL_DIR/.env"
echo "  2. Edit clients:  nano $INSTALL_DIR/configs/clients.yaml"
echo "  3. Test run:  cd $INSTALL_DIR && ./tds-report run-all --month 2026-08"
echo "  4. Check cron:  crontab -l"
echo ""
