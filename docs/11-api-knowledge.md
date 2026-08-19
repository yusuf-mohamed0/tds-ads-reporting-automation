# Phase 0 — API Knowledge & Requirements (researched Aug 2026)

Consolidated findings from official Meta documentation research.
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

## 3. Consolidated data model for the report

| Report section | Meta ads (Marketing API) | Meta Page/IG (Graph API) |
|---|---|---|
| Reach | campaign reach (sum) | page_total_media_view_unique (FB) + reach (IG); organic/paid via page_media_view is_from_ads |
| Messaging | results where objective=MESSAGES / onsite_conversion.messaging | page_messages_new_conversations_unique |
| Content (top posts) | — | post_total_media_view_unique (FB) + media insights (IG) |
| Audience | — | page_follows + page_follows_country (FB); follower_count + follower_demographics gender/age (IG only) |
| Ads campaigns | level=campaign insights | — |
| Budget/Spend | spend | — |

**Open design impact:** FB age/gender demographics are no longer available via API.
The reference report's "Audience demographics" section can only be filled from
Instagram (`follower_demographics`) or a manual upload from Facebook Page Insights
(the Page insights UI may still show them). Must confirm with client.

---

## 4. Prerequisites checklist (what the client must provide)

### Meta
- [ ] Business Manager admin access
- [ ] Meta Developer App (Marketing API product added)
- [ ] System User created; app installed on it; `ads_read` token generated
- [ ] Per-client ad account IDs (`act_<ID>`) — Business Manager admin can access all
- [ ] Page token with ANALYZE+CONTENT; Page ID + Instagram Business Account ID per client
- [ ] Permissions granted: pages_read_engagement, pages_read_user_content, instagram_basic, instagram_manage_insights, pages_messaging
- [ ] App Review / Full access tier for >1 system user (or use Limited with 1 system user)

### Ops
- [ ] Token refresh automation (60-day Meta tokens)
- [ ] `.env` storage, never committed; secrets rotated
