# Client Config And Data Model

## Client Config

The local app should use `configs/clients.yaml` as the source of truth for client/account mappings.

Required fields:

- `id`
- `name`
- `report_recipient`
- `language`
- `currency`
- `timezone`
- `goals.primary`
- `meta.enabled`
- `google_ads.enabled`

Conditional fields:

- `meta.ad_accounts` when Meta is enabled.
- `google_ads.customer_ids` when Google Ads is enabled.
- `conversion_actions` for each platform and goal.

## Goal Types

Supported goal types:

- `leads`
- `messages`
- `purchases`
- `calls`
- `traffic`
- `awareness`
- `custom`

Each goal requires explicit conversion/action mapping when it affects results or CPA.

## Normalized Metric Schema

All platforms should be normalized into common fields:

- `client_id`
- `platform`
- `account_id`
- `campaign_id`
- `campaign_name`
- `date_start`
- `date_stop`
- `spend`
- `impressions`
- `reach`
- `clicks`
- `link_clicks`
- `conversions`
- `conversion_value`
- `ctr`
- `cpc`
- `cpm`
- `cpa`
- `roas`
- `primary_goal`
- `raw_payload_id`

## SQLite Tables

### clients

```sql
CREATE TABLE clients (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  report_recipient TEXT NOT NULL,
  currency TEXT NOT NULL,
  timezone TEXT NOT NULL,
  primary_goal TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1
);
```

### accounts

```sql
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  external_account_id TEXT NOT NULL,
  label TEXT,
  active INTEGER NOT NULL DEFAULT 1,
  UNIQUE(platform, external_account_id),
  FOREIGN KEY(client_id) REFERENCES clients(id)
);
```

### raw_api_pulls

```sql
CREATE TABLE raw_api_pulls (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  date_start TEXT NOT NULL,
  date_stop TEXT NOT NULL,
  endpoint_or_query TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL
);
```

### campaign_metrics

```sql
CREATE TABLE campaign_metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  platform TEXT NOT NULL,
  account_id TEXT NOT NULL,
  campaign_id TEXT,
  campaign_name TEXT,
  date_start TEXT NOT NULL,
  date_stop TEXT NOT NULL,
  spend REAL DEFAULT 0,
  impressions INTEGER DEFAULT 0,
  reach INTEGER,
  clicks INTEGER DEFAULT 0,
  link_clicks INTEGER,
  conversions REAL DEFAULT 0,
  conversion_value REAL DEFAULT 0,
  ctr REAL,
  cpc REAL,
  cpm REAL,
  cpa REAL,
  roas REAL,
  UNIQUE(client_id, platform, account_id, campaign_id, date_start, date_stop)
);
```

### report_runs

```sql
CREATE TABLE report_runs (
  run_id TEXT PRIMARY KEY,
  date_start TEXT NOT NULL,
  date_stop TEXT NOT NULL,
  status TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  summary_json TEXT
);
```

### generated_reports

```sql
CREATE TABLE generated_reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL,
  client_id TEXT NOT NULL,
  pdf_path TEXT NOT NULL,
  email_status TEXT NOT NULL DEFAULT 'not_sent',
  email_error TEXT,
  created_at TEXT NOT NULL
);
```

## Month-Over-Month Storage

The database must keep historical rows so the report can compare:

- Current month vs previous month.
- Current month vs monthly budget.
- Current CPA vs target CPA if provided.
- Current ROAS vs target ROAS if provided.
