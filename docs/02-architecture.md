# Architecture

## High-Level Architecture

```text
Linux Scheduler
  -> Reporting Runner
     -> Client Config Loader
     -> Meta Ads Extractor
     -> Normalization Layer
     -> SQLite Storage
     -> KPI Calculator
     -> Chart Builder
     -> HTML Report Renderer
     -> PDF Generator
     -> Email Sender
     -> Logs + Run Summary
```

## Data Flow

1. Scheduler starts monthly job.
2. Runner calculates previous month date range.
3. Client config is loaded and validated.
4. For each client:
   - Pull Meta data if Meta is enabled.
   - Normalize metrics into common schema.
   - Store raw and normalized data locally.
   - Calculate KPIs and comparisons.
   - Render HTML.
   - Generate PDF.
   - Email PDF to report recipient.
   - Log result.
5. Runner writes a final JSON and text summary.

## Recommended Module Layout

```text
  src/tds_ads_reporting/
    app.py                    # CLI entry point
    config.py                 # env + client config loading
    scheduler.py              # optional scheduler helpers
    date_ranges.py            # previous month and custom ranges
    meta/
      client.py               # Graph API wrapper
      insights.py             # Meta insights queries (ads)
      metrics.py              # Meta action/result normalization
      page.py                 # Page/Instagram insights (reach, content, audience)
      messaging.py            # Messaging/conversations insights
      permissions.py          # scope checks
    storage/
      db.py                   # SQLite connection and migrations
      repositories.py         # save/load reports and metrics
    reporting/
      kpis.py                 # KPI calculations
      comparisons.py          # MoM calculations
      charts.py               # chart generation
      renderer.py             # Jinja HTML rendering
      pdf.py                  # HTML to PDF
    manual_inputs/
      loader.py               # budget/VAT/remaining/notes per client-month
    email/
      sender.py               # Gmail API or SMTP sending
    observability/
      logging.py              # structured logs
      health.py               # preflight checks
```

## Local Database

SQLite is enough for 30 clients and monthly reporting.

Recommended database file:

```text
data/reporting.sqlite
```

SQLite should store:

- Clients and account mappings.
- Raw API pulls per client/platform/month.
- Normalized campaign metrics.
- Monthly report summaries.
- Generated PDF paths.
- Email delivery status.
- API errors.

## API Strategy

### Meta

Use the Ads Insights API:

```text
GET /act_<AD_ACCOUNT_ID>/insights
```

Common levels:

- `level=account` for totals.
- `level=campaign` for campaign tables.
- `level=adset` when deeper diagnosis is needed.
- `level=ad` for top/worst ads if the sample report needs it.

Use fields such as:

- `account_id`
- `campaign_id`
- `campaign_name`
- `impressions`
- `reach`
- `frequency`
- `spend`
- `clicks`
- `inline_link_clicks`
- `ctr`
- `cpc`
- `cpm`
- `actions`
- `cost_per_action_type`
- `purchase_roas`

#### Page And Instagram Insights (required for the reference report)

The reference report includes Reach, Messaging, Content, and Audience data that come from Page/Instagram insights, not Ads Insights.

Collect via Graph API:

- Page total views/impressions: `page_impressions*`
- Page reach: `page_fans_reaches` / `page_reach`
- Page followers: `page_fans`
- Page demographic breakdown: `page_fans_by_age_gender`
- Content per post: `posts` edge + per-post `insights`
- Instagram reach/impressions: IG insights
- Instagram followers: `instagram_followers`
- Messaging conversations: messenger / IG messaging insights

These require `pages_read_engagement`, `pages_read_user_content`, `read_insights`, and IG insights scopes, plus access tokens covering every FB Page and IG account per client.

#### Manual Narrative And Budget

Budget, VAT, remaining, Report Scope prose, and Insights commentary are not in any API. Provide them through a per-client per-month manual-input file that is merged into the renderer.

## Report Rendering Strategy

Recommended approach:

- Use Jinja2 to render HTML templates.
- Use CSS for agency branding and print layout.
- Use WeasyPrint or Playwright/Chromium to produce PDFs.
- Save all PDFs locally before emailing.

## Email Strategy

Preferred:

- Gmail API OAuth.

Fallback:

- SMTP with Gmail App Password.

Email should include:

- Subject: `Monthly Ads Report - <Client Name> - <Month Year>`.
- Short body summary.
- PDF attachment.
- Optional run identifier.

## Failure Handling

- If one API account fails, mark that platform as failed for that client and continue.
- If one client fails, continue other clients.
- If PDF generation fails, keep data and log failure.
- If email fails, keep PDF and retry email only.
- Produce final `run_summary.json`.

## Local Scheduling

Preferred on Linux:

- `systemd timer` for production reliability.

Acceptable:

- `cron` monthly job.

Recommended schedule:

- Run on the 1st of each month at 09:00 Africa/Cairo for the previous calendar month.
- Optional retry run at 12:00 if first run fails.
