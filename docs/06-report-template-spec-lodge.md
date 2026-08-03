# Sample Report Analysis: "Lodge - March 2026 Report"

This document records the exact structure and data fields from the real manual report provided as the reference sample. The automation plan must reproduce this report.

## Source

- File: `Lodge - March26 Report.pdf`
- 16 pages
- Agency-branded, English, portrait
- Meta-only (Facebook + Instagram)

## Key Finding

This report is **not only Meta Ads**. It is a full **Meta Business Suite / Page / Instagram / Messaging** report. A large share of the data comes from **Page Insights / Instagram Insights / Messaging Insights**, not from the Ads Insights API alone.

Therefore automation requires a **superset of Meta permissions** compared with a pure ads report:

- `ads_read` (ads performance)
- `pages_read_engagement`
- `page_insights`
- `instagram_manage_insights` / `read_insights`
- `pages_read_user_content` (content/post-level data)
- `pages_messaging` or `pages_read_engagement` for messaging conversational data
- Page token with those permissions

## Report Structure (page by page)

### Page 1: Cover
- Traffic (agency) logo/branding
- Client name: Lodge
- Month/year

### Page 2: Table of Contents
Sections in order:
- Report Scope
- Reach
- Messaging
- Content
- Audience
- Ads
- Insights

### Page 3: Report Scope
- Narrative text describing monthly focus (e.g. engagement through messaging campaigns + profile visits).
- This text is largely **manual/summary prose** added by the account manager.

### Pages 4-5: Reach
**Facebook**
- Business Suite content overview
- Organic vs ads breakdown (trend + donut)
- KPIs: Total FB views, 3-sec views, 1-min views, interactions, watch time
- From organic vs from ads split

**Instagram**
- Total views, reach, interactions
- From organic vs from ads split

Data source: `page_insights` (`page_impressions`, `page_impressions_organic`, `page_impressions_paid`, `page_fan_adds`, `page_views_total`) and Instagram `instagram_reach`, `instagram_impressions`, `instagram_reach_organic`/`paid` via Graph API storytelling/insights.

### Pages 6-7: Messaging
**Facebook**
- Total contacts
- Conversations started
- Organic vs paid breakdown (e.g. organic 2, paid 4)

**Instagram**
- Total contacts
- Conversations started
- Organic vs paid (e.g. organic 159, paid 1,475)

Data source: Business Suite Messaging Insights — `page_messaging_*`, `messenger_*`, `whatsapp_*`-style metrics; Instagram `instagram_messaging_*`. Requires messaging insights access and per-client mapping.

### Pages 8-9: Content
**Facebook**
- Top content table: title, date published, views, reach, from ads

**Instagram**
- Top content table: title, date published, views, reach, from ads

Data source: Page `posts` edges + `insights` per post (`post_video_views`, `post_reach`, `post_impressions`), Instagram media insights. Requires `pages_read_engagement` and `pages_read_user_content`.

### Pages 10-11: Audience
**Facebook**
- Lifetime followers (e.g. 13,337)
- Age/gender distribution chart

**Instagram**
- Lifetime followers (e.g. 35,811)
- Age/gender distribution chart

Data source: `page_insights` demographic breakdowns (`page_fans_by_age_gender`), Instagram `ig_user_audience`/demographics insights.

### Pages 12-13: Ads
**Facebook** and **Instagram** campaign tables:
- Campaign name
- Platform
- Results
- Cost per result
- Amount spent
- Impressions
- Reach

Data source: Ads Insights API at `level=campaign` with `fields=results, cost_per_result, spend, impressions, reach` (fields differ by objective and mapped action types).

### Page 14: Budget / Spend
- Budget (e.g. EGP 63,600)
- Spent (e.g. EGP 42,834)
- VAT (e.g. EGP 48,830)
- Remaining (e.g. EGP 14,770)

Budget/VAT/Remaining are **manual inputs** (not from API). The app should accept these in client/month config and print them on the report.

### Page 15: Insights
- Hand-written bullet insights, e.g.:
  - Reach growth context
  - CPM / messages during vs after Ramadan comparison
  - Total messages (1.6K), 87% paid
  - Recommendation: continue messages campaign
  - Need profit impact
  - Pizza content recommendation

These insights are **manual narrative** reviewed by the account manager, optionally AI-drafted as a first pass that a human approves.

### Page 16: Thank-you / closing
- Brand closing page.

## Which Parts Are Automatable

### Fully automatable (API)
- Reach KPI cards and organic/paid breakdowns
- Messaging total/paid/organic counts
- Content top posts tables
- Audience follower counts + demographics
- Ads campaign tables (results, cost per result, spend, impressions, reach)
- Monthly month-over-month comparison charts

### Semi-automatic
- Report Scope summary prose (AI first draft, human approval)
- Insights commentary (AI first draft, human approval)

### Manual inputs (stored locally, injected into report)
- Budget
- VAT
- Remaining
- Currency assumption (EGP)
- Per-client manual narrative overrides

## Permissions To Request (Meta)

Document these because they exceed a standard ads-only app:
- `ads_read`
- `pages_read_engagement`
- `pages_read_user_content`
- `pages_show_list`
- `read_insights`
- `instagram_measure_insights` / `instagram_business_basic` / `instagram_manage_insights`
- `pages_read_engagement` replaced/paired with a Page token that has `read_insights`

A user/page token or system-user page token must cover every FB Page and IG professional account that the client report references.

## Data Field Mapping Summary

Placeholders to confirm against live API after access is granted:

- Page total views: `page_insights: {field: 'page_views_total'}`
- Page impressions organic: `page_impressions_organic`; paid: `page_impressions_paid`
- Page reach: `page_fan_reaches` (daily) / `page_reach`
- Page followers: `page_fans` or `page_fan_adds`
- Messenger conversations: Messenger/IG messaging insights (`messaging_*`)
- IG views: `instagram_impressions` / `instagram_reviews` (IG reel video views)
- IG followers: `instagram_followers`
- Content: `feeds` → `insights` per post/media

## Recommended Next Step

Confirm the exact metric names after a Meta app is provisioned by listing the insights metrics available on the client's Facebook Page and Instagram professional account for the coverage month. Then finalize mapping and the template.