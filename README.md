# TDS Ads Reporting Automation

Monthly Meta Ads client PDF reporting system for Traffic Digital Solutions.

## What It Does

Automatically generates professional 17-page PDF reports for each client:

1. **Pulls data** from Meta Marketing API (campaigns, ad sets, conversions, demographics, pacing)
2. **Pulls insights** from Facebook Page (media views, followers, messaging, top posts)
3. **Pulls insights** from Instagram (reach, views, demographics, top media)
4. **Generates** individual client PDFs + combined portfolio report
5. **Emails** reports to `reports@trafficdigitalsolutions.com`

## Report Structure (17 pages)

| Page | Section |
|------|---------|
| 1 | Cover (dark, branded) |
| 2 | Table of Contents |
| 3 | Executive Summary |
| 4 | KPI Dashboard |
| 5 | Campaign Performance |
| 6 | Top Ad Sets |
| 7 | Conversion Breakdown |
| 8 | Distribution (devices, publishers, countries) |
| 9 | Audience Insights |
| 10 | Pacing Analysis |
| 11 | Facebook Reach |
| 12 | Instagram Reach |
| 13 | Messaging |
| 14 | Content |
| 15 | Insights & Recommendations |
| 16 | Thank You |
| 17 | Tim Attribution |

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/yusuf-mohamed0/tds-ads-reporting-automation.git
cd tds-ads-reporting-automation

# 2. Set up environment
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 3. Configure credentials
cp .env.example .env
# Edit .env with your Meta API tokens

# 4. Configure clients
cp configs/clients.example.yaml configs/clients.yaml
# Edit configs/clients.yaml with your client ad accounts

# 5. Run reports
PYTHONPATH=src python -m tds_ads_reporting.app run-all --month 2026-08
```

## Monthly Automation

Reports auto-generate on the 1st of each month at 09:00 (Cairo time):

```bash
# Install cron jobs
./scripts/install-monthly-cron.sh

# Manual run for a specific month
./scripts/run-monthly.sh 2026-08

# Manual run with email
./scripts/run-monthly.sh 2026-08 --email
```

## Project Structure

```
tds-ads-reporting-automation/
├── src/tds_ads_reporting/     # Main application code
│   ├── app.py                 # CLI entry point
│   ├── config.py              # Client configuration loader
│   ├── meta/                  # Meta API integration
│   │   ├── ads.py             # Campaign/adset/conversion data
│   │   ├── page.py            # Facebook Page insights
│   │   └── credentials.py     # API token management
│   ├── reporting/             # Report generation
│   │   ├── assembler.py       # Data → template context
│   │   ├── pdf.py             # Jinja2 → WeasyPrint PDF
│   │   └── combined.py        # Portfolio combined report
│   ├── insights/              # AI insights engine
│   ├── mailer/                # Email sending
│   ├── storage/               # SQLite cache
│   ├── manual_inputs/         # YAML budget/VAT/recommendations
│   └── observability/         # Logging
├── templates/                 # Jinja2 HTML templates
│   ├── report.html.j2         # Individual client report
│   ├── combined_report.html.j2 # Portfolio report
│   └── _styles.html.j2        # Shared styles + Proxima Nova fonts
├── configs/
│   ├── clients.yaml           # Client configurations (gitignored)
│   └── clients.example.yaml   # Example config
├── scripts/                   # Automation scripts
│   ├── run-monthly.sh         # Monthly report runner
│   ├── install-monthly-cron.sh # Cron setup
│   └── watch-trigger.sh       # Backend trigger watcher
├── tests/                     # Unit tests
├── manual_inputs/             # Per-client budget/VAT YAML files
├── docs/                      # Architecture & setup documentation
└── assets/                    # Brand assets & fonts
```

## Client Configuration

Each client in `configs/clients.yaml` needs:

- `id`: Unique identifier (matches folder names)
- `name`: Display name
- `currency`: EGP, ILS, USD, or CAD
- `meta.ad_accounts`: List of Meta ad account IDs
- `meta.page_id`: Facebook Page ID (for Page insights)
- `meta.instagram_id`: Instagram Business Account ID
- `goals.primary`: Primary conversion goal
- `monthly_budget`: Budget for utilization tracking

## Manual Inputs

Per-client monthly YAML files in `manual_inputs/`:

```yaml
budget:
  amount: 50000
  vat: 14%
recommendations:
  - "Increase budget for top-performing campaign"
  - "Pause underperforming ad sets"
```

## Tests

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```

## Credentials

Required in `.env`:

- `META_SYSTEM_USER_TOKEN` — Meta System User token with ads_read permission
- `META_PAGE_ACCESS_TOKEN` — Page access token with ANALYZE+CONTENT tasks
- `META_API_VERSION` — API version (default: v26.0)

## Generated Output

Reports are saved to `reports/{client-id}/{YYYY-MM}/`:
- `{client-id}_{YYYY-MM}.pdf` — Individual client report
- `reports/combined/combined_{YYYY-MM}.pdf` — Portfolio summary

Reports are gitignored (regenerated monthly by automation).
