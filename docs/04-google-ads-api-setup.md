# Google Ads API Setup

## Objective

Use Google Ads API to pull campaign and conversion reporting data without logging into Google Ads UI.

## Required Google Assets

- Google Ads Manager Account / MCC.
- Access from MCC to every client Google Ads account.
- Google Cloud project.
- Google Ads API enabled in the Cloud project.
- OAuth client ID and client secret.
- Google Ads developer token.
- OAuth refresh token for the MCC/admin user.
- Client customer IDs.

## Setup Steps

1. Confirm all client Google Ads accounts are accessible from the MCC.
2. Open Google Cloud Console.
3. Create/select a project for reporting automation.
4. Enable Google Ads API.
5. Create OAuth client credentials.
6. In Google Ads MCC, open API Center.
7. Apply for or copy the Developer Token.
8. Generate OAuth refresh token using the MCC/admin Google account.
9. Store credentials in `.env`.
10. Add each client customer ID to `configs/clients.yaml`.

## Environment Variables

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_LOGIN_CUSTOMER_ID`

## GAQL Campaign Query Example

```sql
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  metrics.impressions,
  metrics.clicks,
  metrics.ctr,
  metrics.average_cpc,
  metrics.cost_micros,
  metrics.conversions,
  metrics.cost_per_conversion,
  metrics.conversions_value,
  segments.date
FROM campaign
WHERE segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
  AND campaign.status != 'REMOVED'
```

## Conversion Action Query Example

```sql
SELECT
  campaign.id,
  campaign.name,
  segments.conversion_action_name,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_micros
FROM campaign
WHERE segments.date BETWEEN 'YYYY-MM-DD' AND 'YYYY-MM-DD'
  AND campaign.status != 'REMOVED'
```

## Metric Conversion Rules

- `cost_micros / 1_000_000 = cost`.
- `average_cpc` may be micros depending on selected field/client library output.
- ROAS = `conversion_value / cost` when conversion value exists.
- CPA = `cost / conversions` when conversions > 0.

## Validation Checklist

- Confirm `listAccessibleCustomers` works.
- Confirm MCC `login-customer-id` is accepted.
- Confirm each client customer ID returns campaign rows.
- Confirm monthly spend matches Google Ads UI after excluding removed entities.
- Confirm conversion actions are mapped correctly per client.

## Risks

- Developer token may have limited access level at first.
- Refresh token can be revoked.
- MCC access to client accounts can change.
- UI reports and API reports can differ if filters/status/segments differ.

## Mitigation

- Add preflight checks.
- Store refresh token securely.
- Log customer ID and GAQL query for each failure.
- Match UI by filtering removed entities and using same date/timezone settings.
