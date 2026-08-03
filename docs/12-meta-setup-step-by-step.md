# Step-by-Step: Meta App + System User Token Setup

Complete these once as the Business Manager admin. Result: values for
`META_SYSTEM_USER_TOKEN` and `META_PAGE_ACCESS_TOKEN` in `.env`, plus
per-client IDs in `configs/clients.yaml`.

---

## 1. Create the Meta Developer App

1. Go to https://developers.facebook.com/apps → **Create App**.
2. Use-case: **Other** → type: **Business**. Name it e.g. "TDS Reports".
3. Add the **Marketing API** product (Business → Marketing API).
4. Go to **App Settings → Basic**: copy **App ID** and **App Secret**.

> The app must be owned by / have access to the Business Manager that manages
> all ~30 client ad accounts.

## 2. Create a System User (in Business Manager)

1. Business Suite → **Business Settings** (https://business.facebook.com/settings).
2. Users → **System Users** → **Add**.
3. Name: "TDS Reports Bot"; Role: **Admin**.
4. Copy the system user **ID**.

## 3. Add a Marketing API access token to the System User

In Business Settings → System Users → your bot → **Add Assets**:

- **Ad Accounts**: add every client ad account the reports cover
  (Assign → Manage campaigns / View performance).
- **Apps**: add your Developer App.

Then, still on the system user card → **Generate New Token**:
- App: your Developer App
- Token type: **System User token**
- **Scopes**: tick `ads_read` (minimum; add `ads_management` only if you also
  create/edit ads).
- **Token expiry**: choose 60 days (recommended) and set a rotation reminder,
  or non-expiring (legacy). Copy the token → put in `.env` as `META_SYSTEM_USER_TOKEN`.

> If you prefer the API route:
> `POST /v26.0/<SYSTEM-USER-ID>/applications` (body `business_app=<APP_ID>`),
> then `POST /v26.0/<SYSTEM-USER-ID>/access_tokens`
> (body `business_app`, `scope=ads_read`, `appsecret_proof`).

## 4. App Review / access tier

- **Limited access** (default) allows **1 system user** and works for internal
  reporting on assets you already own. Enough to start.
- For **>1 system user** you need **Full access** (App Review):
  qualify with ≥500 successful Marketing API calls in the last 15 days and
  <15% error rate, then request the `ads_read` permission for Marketing API.

## 5. Page access token (for Page + Instagram insights)

The system user token above does NOT cover Page insights. Generate a
**Page access token**:

1. Go to the **Graph API Explorer** → your app → **Get Token → Page Access Token**.
2. Choose the client's Page; the token appears in `/me/accounts`.
3. The Page token needs tasks **ANALYZE** + **CONTENT**.
4. Put it in `.env` as `META_PAGE_ACCESS_TOKEN`.

> Note: Page tokens are per-Page. If you manage all Pages under one Business
> Manager, a single **system user token** can also be exchanged for page access
> tokens for each page. The simplest robust option is to store each client's
> Page token in their `clients.yaml` entry if tokens differ per client.

## 6. Gather per-client IDs

For each of the ~30 clients, collect:

| Key | Where to find |
|---|---|
| `meta.ad_accounts[].id` | Business Settings → Ad Accounts → `act_<NUMBER>` |
| `meta.page_id` | Page → About → Page ID (or `/me/accounts` → `id`) |
| `meta.instagram_id` | Page settings → Linked accounts, or `GET /{page_id}?fields=instagram_business_account` |
| `goals` | Primary business goal (leads/messages/purchases/calls) |
| `currency` | EGP default; override per client |
| `report_recipient` | email for the monthly PDF |

Write these into `configs/clients.yaml` (copy of `clients.example.yaml`).

---

## Verification

After setup, test connectivity:

```bash
cd /root/tds-ads-reporting-automation
.venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from tds_ads_reporting.meta.credentials import init_credentials
c=init_credentials()
print('META_SYSTEM_USER_TOKEN set:', bool(c.meta_access_token))
print('API version:', c.meta_api_version)
print('GOOGLE_ADS_YAML:', c.google_ads_yaml)
"
```

Then a dry run to confirm config parses:

```bash
PYTHONPATH=src .venv/bin/python -m tds_ads_reporting.app run --client client_a --month 2026-03 --dry-run
```
