# PDF Report Template Specification

This document defines the target report structure. It must be finalized after reviewing the current manual report sample.

## Report Rules

- Language: English.
- Format: PDF.
- Orientation: portrait unless sample report requires landscape tables.
- Recipient: `reports@trafficdigitalsolutions.com`.
- Include only platforms available for the client.
- No screenshots required unless a final sample report explicitly requires visual proof images.

## Page 1: Cover

Required elements:

- Traffic Digital Solutions logo.
- Client name.
- Report month and year.
- Platforms included: Meta Ads only.
- Prepared by Traffic Digital Solutions.

## Page 2: Executive Summary

Required KPI cards:

- Total spend.
- Total impressions.
- Total clicks.
- Total conversions/results.
- Overall CPA or cost per result.
- ROAS if ecommerce/conversion value exists.

Narrative:

- 3-5 bullet summary.
- What improved.
- What declined.
- Main recommendation.

## Page 3: Overall Performance

Charts:

- Daily spend trend.
- Daily results/conversions trend.
- Platform spend split across Meta ad accounts.

Table:

- Platform.
- Spend.
- Impressions.
- Clicks.
- CTR.
- CPC.
- Conversions/results.
- CPA.
- ROAS where available.

## Meta Ads Section

Include when client has Meta enabled.

KPIs:

- Spend.
- Impressions.
- Reach.
- Frequency.
- Clicks.
- Link clicks.
- CTR.
- CPC.
- CPM.
- Results by primary goal.
- Cost per result.

Tables:

- Campaign performance.
- Optional ad set performance.
- Optional top ads.

Charts:

- Spend vs results by day.
- Campaign spend/result bar chart.

## Best And Weak Campaigns

Best campaign logic:

- Highest conversions with acceptable CPA.
- Highest ROAS for ecommerce.
- Highest click quality if traffic objective.

Weak campaign logic:

- High spend with low/no conversions.
- CPA above target.
- CTR below account average.
- Frequency too high for Meta.

## Recommendations

Automated recommendation rules can start simple:

- If spend increased and conversions increased: scale winning campaigns carefully.
- If spend increased and conversions decreased: review targeting, creative, and landing page.
- If CTR dropped: refresh ad creative/copy.
- If CPA increased: reallocate budget to lower CPA campaigns.
- If frequency is high on Meta: rotate creatives or expand audience.

Manual note override should be allowed in client config or monthly notes file.

## Appendix

Optional definitions:

- CTR = clicks / impressions.
- CPC = spend / clicks.
- CPM = spend / impressions * 1000.
- CPA = spend / conversions.
- ROAS = conversion value / spend.

## Metrics Mapping

### Meta

- Spend: `spend`
- Impressions: `impressions`
- Reach: `reach`
- Frequency: `frequency`
- Clicks: `clicks`
- Link clicks: `inline_link_clicks`
- CTR: `ctr`
- CPC: `cpc`
- CPM: `cpm`
- Results: mapped from `actions`
- Cost per result: mapped from `cost_per_action_type`
- ROAS: `purchase_roas`
