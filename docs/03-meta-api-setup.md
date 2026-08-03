# Meta API Setup

## Objective

Use Meta Marketing API to pull reporting data without logging into Meta Business Suite in a browser.

## Required Meta Assets

- Meta Business Manager with admin access.
- Meta Developer account.
- Meta app owned by the Business Manager.
- Business System User.
- System User token with `ads_read`.
- Client ad accounts assigned to the System User.

## Setup Steps

1. Open Meta for Developers.
2. Create or select a Meta app for internal reporting.
3. Connect the app to the Business Manager.
4. Enable Marketing API access.
5. In Business Settings, create a System User.
6. Assign all client ad accounts to that System User.
7. Grant at least reporting/read access for ads.
8. Generate a System User access token with `ads_read`.
9. Store token in local `.env` as `META_SYSTEM_USER_ACCESS_TOKEN`.
10. Add each client ad account ID to `configs/clients.yaml`.

## Permissions

Minimum:

- `ads_read`

Possible later additions:

- `business_management` if business asset discovery must be automated.
- `ads_management` only if the app will later modify campaigns, which is not needed for reporting.

## API Endpoints

Account-level insights:

```text
GET https://graph.facebook.com/v25.0/act_<AD_ACCOUNT_ID>/insights
```

Campaign-level insights:

```text
GET https://graph.facebook.com/v25.0/act_<AD_ACCOUNT_ID>/insights?level=campaign
```

Daily trend:

```text
GET .../insights?level=account&time_increment=1
```

## Required Parameters

- `time_range[since]`
- `time_range[until]`
- `level`
- `fields`
- `access_token`

## Recommended Fields

```text
account_id,account_name,campaign_id,campaign_name,adset_id,adset_name,ad_id,ad_name,
impressions,reach,frequency,spend,clicks,inline_link_clicks,ctr,cpc,cpm,
actions,cost_per_action_type,purchase_roas,date_start,date_stop
```

## Conversion Mapping

Meta puts conversions inside arrays such as `actions` and `cost_per_action_type`.

The app must map client goals to action types. Examples:

- Leads: `lead`, `onsite_conversion.lead_grouped`
- Messages: `onsite_conversion.messaging_conversation_started_7d`
- Purchases: `purchase`, `omni_purchase`
- Calls: platform-specific action type if available in the account.

## Validation Checklist

- Confirm token can call `/me` or a basic Graph endpoint.
- Confirm each `act_<ID>/insights` returns data for last 7 days.
- Confirm previous-month date range returns data.
- Confirm conversion action names are present for each client goal.
- Confirm spend matches Meta Ads Manager within expected attribution/reporting differences.

## Risks

- Tokens can expire or be revoked.
- Client account permissions can be removed.
- Meta metrics can differ from UI if attribution windows/settings differ.
- Some action types differ by objective and account setup.

## Mitigation

- Preflight token/account access before monthly run.
- Log raw action arrays for debugging.
- Use account attribution settings consistently.
- Keep per-client conversion mapping explicit.
