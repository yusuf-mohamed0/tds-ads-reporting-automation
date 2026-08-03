# Phase 0 — API Knowledge & Requirements (researched Aug 2026)

Consolidated findings from official Meta + Google Ads documentation research.
This is the authoritative basis for the data-fetch modules. Anything in here that
differs from earlier docs supersedes them.

---

## 1. Meta Marketing API (ads insights) — v26.0

### Endpoint pattern
```
GET /v26.0/act_<AD_ACCOUNT_ID>/insights
  ?level=campaign
  &fields=campaign_name,campaign_id,date_start,date_stop,results,cost_per_result,
          spend,impressions,reach,frequency,ctr,cpc,cpm,inline_link_clicks
  &time_range={"since":"2026-01-01","until":"2026-02-01"}
  &access_token=<SYSTEM_USER_TOKEN>
```
- `time_range.until` is **exclusive** (beginning of next day). Full month:
  `since=2026-01-01, until=2026-02-01`. No timezone param exists; data is in the
  **ad account timezone** (get it via `GET /act_<ID>?fields=timezone_name`).
- `time_increment=monthly` returns one row per campaign per calendar month
  (needs a multi-month time_range). Simpler: use single-month time_range + level=campaign.
- `level=campaign` gives one row per campaign. `limit` + cursor `paging.cursors.after` for pagination.
- `use_unified_attribution_setting=true` to match Ads Manager numbers. Default attribution window = `["7d_click","1d_view"]`.

### Key fields (returned as strings, parse numerically)
- `spend` (estimated), `impressions`, `reach` (estimated, unique), `frequency` (avg, with reach), `ctr`, `cpc`, `cpm`
- `results` = count of the outcome the campaign optimizes for (leads, messages, purchases, calls...)
- `cost_per_result` = spend ÷ results
- `inline_link_clicks` = clicks to destination (fixed 1-day-click window)
- Also: `objective`, `actions` (event-by-event counts), `action_values`, `account_currency`, `date_start`, `date_stop`

### Auth
- **System User access token** (Business Manager), NOT a page token.
- Minimum permission: `ads_read`. `ads_management` only needed for creating/editing ads.
- Token generation: create System User → install app (`POST /<SUID>/applications`) → `POST /<SUID>/access_tokens` with `scope=ads_read` (+ appsecret_proof).
- Expiring tokens last 60 days and must be refreshed (`grant_type=fb_exchange_token`); non-expiring tokens exist but Meta pushes 60-day rotation. Must handle refresh in ops.
- Access tiers (2026): Limited (was "Standard", 1 system user) vs Full (was "Advanced", App Review, 10 users, needs 500 successful calls/15d <15% error).

### Rate limits (per ad account, rolling 1h)
- `ads_insights` bucket: 190,000 (Full) / 600 (Dev) + 400 × active ads − 0.001 × user errors.
- Errors: 80004/80000 (ad-account limit), 4 (app limit), 17 (user), 100/subcode 1487534 (too much data per call).
- Handling: exponential backoff (60s → 16 min), async report runs for heavy queries, monitor `x-fb-ads-insights-throttle`.
- Insights refresh every 15 min; finalize ~28 days after period.

### Python
- Official `facebook-business` SDK (maintained, latest 25.0.3; v26.x coming). Use it:
  `FacebookAdsApi.init(access_token=TOKEN, api_version='v26.0')`, then
  `AdAccount('act_...').get_insights(fields=[...], params={...})`. Cursor pagination built in.
- Raw `requests` to graph.facebook.com also fine. SDK recommended.

### 2025–2026 breaking changes that matter
- View-through windows removed Jan 12, 2026: `7d_view`/`28d_view` now return **empty silently**. Only `1d_view` remains.
- Attribution now mimics Ads Manager (mixed reporting); pass `use_unified_attribution_setting=true` for parity.
- v26 (Jul 29, 2026): `date_format` param now errors; insights `date_preset=maximum` cap 37 months.

---

## 2. Meta Graph API (Page + Instagram insights) — v26.0

### CRITICAL — metric retirements (June 2026)
- **`page reach`, `post reach`, `video impressions`, `story impressions` are GONE** (retired June 15, 2026).
  Replaced by **Media Views / Media Viewers** metrics:
  - Reach replacement: `page_total_media_view_unique` (period=day)
  - Paid vs organic split: `page_media_view` with `breakdown=is_from_ads`
  - Top posts: `post_total_media_view_unique` (period=lifetime, per post)
- `page_fans_gender_age` (FB age/gender demographics) **deprecated since 2024-03-14 — unavailable.**
  Surviving FB audience data: `page_follows_country` (geo, period=lifetime). No FB gender/age split anymore.
- IG: `impressions` deprecated Apr 2025 → use `views`. IG **does** still have demographics:
  `follower_demographics` with `breakdown=gender,age` (period=this_month only — NOT last_30_days/prev_month).

### Page metrics (per month = sum over period=day within since/until window; window ≤90 days)
| Metric | Endpoint | Notes |
|---|---|---|
| Media views (reach proxy) | `/insights?metric=page_total_media_view_unique&period=day&since=&until=` | sum days |
| Organic/paid split | `/insights?metric=page_media_view&period=day&breakdown=is_from_ads&since=&until=` | true/false buckets |
| Followers total | `/insights?metric=page_follows&period=lifetime` | current |
| Followers delta | `/insights?metric=page_follows&period=day&since=&until=` | sum = net change |
| New conversations | `/insights?metric=page_messages_new_conversations_unique&period=total_over_range&since=&until=` | correct messaging metric |
| Messages sent | `page_messages_sent` (period=day/total_over_range) | |
| Read ratio | `page_messages_read_ratio` | |
| Top posts | `/posts?fields=id,created_time,permalink_url` → per post `/insights?metric=post_total_media_view_unique&period=lifetime` | rank client-side |
| Geo | `/insights?metric=page_follows_country&period=lifetime` | only surviving FB demographic |

### Instagram metrics (IG Business Account ID = IG-scoped ID from `/{page-id}?fields=instagram_business_account`)
- Reach: `/insights?metric=reach&period=day` (UNIX timestamps for since/until; day buckets roll on Pacific time)
- Views: `metric=views&period=day` (impressions replacement)
- Engaged accounts: `metric=accounts_engaged&period=day`
- Follower count: `GET /{igsid}?fields=followers_count`
- Demographics: `metric=follower_demographics&period=this_month&metric_type=total_value&breakdown=gender,age`
- Top content: per media `/insights?metric=reach,saved,comments,likes,views,total_interactions`
  (media ids from `GET /{igsid}/media?fields=id,timestamp&limit=100`, paginate)

### Permissions & tokens
- **Page access token** (from `/me/accounts` → `access_token`) with `ANALYZE` + `CONTENT` tasks.
- Page permissions: `pages_read_engagement`, `pages_read_user_content`, `pages_show_list`;
  messaging needs `pages_messaging`; IG needs `instagram_basic` + `instagram_manage_insights`.
- Rate limits: Page BUC `4800 × engaged users / 24h` (error 80001), IG `4800 × impressions/24h` (80002).
  Sleep ~1s between per-post/per-media insight calls.
- Errors: #100 invalid metric, #10 permission, #190 token expired, #80001/#80004 rate limit.

### Methodology caveat
- Summing daily unique counts over a month **overcounts** true monthly unique (same as legacy Reach).
  Use `days_28` period for a cleaner rollup OR footnote methodology.
- Media Views ≠ legacy Reach. MoM comparisons across June 15, 2026 boundary need a footnote.

---

## 3. Google Ads API — v25 (client library 31.2.0)

### Auth & config
- OAuth2 installed-app (`client_id`, `client_secret`, `refresh_token`) or service account.
- `login_customer_id` (MCC, no dashes) required for MCC-level calls; each query targets one `customer_id`.
- `google-ads.yaml` structure: `developer_token`, `use_proto_plus: true`, `client_id`, `client_secret`,
  `refresh_token`, `login_customer_id`, optional `json_key_file_path`/`impersonated_email`, `logging`.
- `GoogleAdsClient.load_from_storage(path=..., version="v25")`. Default path `~/google-ads.yaml`.
- Access levels: Test (test accts only) → Explorer (2,880 prod ops/day) → Basic (15,000/day) →
  Standard (unlimited). New tokens start Test; Basic review ~5 days, Standard ~10 days.
  Sliding 24h window; violation → `RESOURCE_EXHAUSTED`.

### GAQL monthly per-campaign query
```sql
SELECT campaign.name, campaign.status, campaign.advertising_channel_type,
       metrics.clicks, metrics.impressions, metrics.ctr, metrics.average_cpc,
       metrics.cost_micros, metrics.conversions, metrics.conversions_value,
       metrics.cost_per_conversion
FROM campaign
WHERE segments.date >= '2026-07-01' AND segments.date <= '2026-07-31'
  AND campaign.status != 'REMOVED'
```
- Custom date ranges: `YYYY-MM-DD` or `YYYYMMDD`; `BETWEEN` / `>=,<=` / `DURING LAST_30_DAYS` etc.
- `segments.date` is in the customer's timezone. If segments.date in SELECT → finite date range in WHERE required.
- **37-month lookback limit on `segments.date`** since June 1, 2026 (use segments.month for older data).
- `customer.currency_code`, `customer.time_zone` available via `SELECT customer.currency_code ... FROM customer`.
- **Cost micros** → divide by 1,000,000. **Conversions not additive** across dates (conversion lag):
  sum `conversions_by_conversion_date` for monthly totals, or footnote that recent months keep rising.
  `cost_micros`, `clicks`, `impressions`, `ctr` ARE additive.
- Conversion breakdown by action: `segments.conversion_action` + `conversion_action` resource
  (`conversion_action.type` = e.g. `PHONE_CALL` for calls).
- v25 `SearchGoogleAdsRequest` has NO `date_range` field — filter via GAQL only. `page_size` deprecated.

### Python usage
- `search_stream` → iterator of `GoogleAdsRow`. **Keep the iterator in the same scope as the
  GoogleAdsService client** (gRPC channel GC → broken stream). Don't create service in a helper
  and return only the iterator.
- One SearchStream call = 1 API operation regardless of batch size. Stream for big reports (64MB gRPC limit).
- `Client.load_from_storage`; `client.get_service("GoogleAdsService")`; build GAQLQueryRequest with
  `customer_id`, `query`, `search_settings`.

### Quotas & errors
- QPS metered per customer ID AND per developer token (token bucket). Violation → `RESOURCE_TEMPORARILY_EXHAUSTED`.
- Resource consumption throttling: `EXCESSIVE_SHORT_TERM_QUERY_RESOURCE_CONSUMPTION` (retry 5 min),
  `EXCESSIVE_LONG_TERM` (30 min). Avoid per-campaign loops — one query per account per month.
- Best practice: cache historical months; sequential queries with client-side QPS cap.

### Version timeline (2026)
- v25 released Jul 22, 2026 (sunset Aug 2027). Client 31.2.0 supports v21–v25, defaults v25.
- ~5 majors kept; upgrade ≤2/yr.

---

## 4. Consolidated data model for the report

| Report section | Meta ads (Marketing API) | Meta Page/IG (Graph API) | Google Ads (GAQL) |
|---|---|---|---|
| Reach | campaign reach (sum) | page_total_media_view_unique (FB) + reach (IG); organic/paid via page_media_view is_from_ads | N/A (impressions only) |
| Messaging | results where objective=MESSAGES / onsite_conversion.messaging | page_messages_new_conversations_unique | conversions where conversion_action.type=PHONE_CALL / Lead |
| Content (top posts) | — | post_total_media_view_unique (FB) + media insights (IG) | — |
| Audience | — | page_follows + page_follows_country (FB); follower_count + follower_demographics gender/age (IG only) | — |
| Ads campaigns | level=campaign insights | — | campaign GAQL rows |
| Budget/Spend | spend | — | cost_micros ÷ 1e6 |

**Open design impact:** FB age/gender demographics are no longer available via API.
The reference report's "Audience demographics" section can only be filled from
Instagram (`follower_demographics`) or a manual upload from Facebook Page Insights
(the Page insights UI may still show them). Must confirm with client.

---

## 5. Prerequisites checklist (what the client must provide)

### Meta
- [ ] Business Manager admin access
- [ ] Meta Developer App (Marketing API product added)
- [ ] System User created; app installed on it; `ads_read` token generated
- [ ] Per-client ad account IDs (`act_<ID>`) — Business Manager admin can access all
- [ ] Page token with ANALYZE+CONTENT; Page ID + Instagram Business Account ID per client
- [ ] Permissions granted: pages_read_engagement, pages_read_user_content, instagram_basic, instagram_manage_insights, pages_messaging
- [ ] App Review / Full access tier for >1 system user (or use Limited with 1 system user)

### Google
- [ ] MCC (Manager) account; login_customer_id
- [ ] Google Cloud project + Google Ads API enabled
- [ ] OAuth client (installed app) ID/secret
- [ ] Developer token (production — Basic/Standard level for real accounts)
- [ ] Refresh token (must generate once via OAuth consent)
- [ ] Per-client customer IDs

### Ops
- [ ] Token refresh automation (60-day Meta tokens; Google refresh tokens don't expire unless revoked)
- [ ] `.env` storage, never committed; secrets rotated
