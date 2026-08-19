from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date


def month_range(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    since = date(year, mon, 1).isoformat()
    until = date(year + (1 if mon == 12 else 0), 1 if mon == 12 else mon + 1, 1).isoformat()
    return since, until


def month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def _first_scalar(value: object) -> object:
    if isinstance(value, list):
        return _first_scalar(value[0]) if value else None
    if isinstance(value, dict):
        return _first_scalar(value.get("value") or value.get("values") or value.get("result"))
    return value


def parse_float(value: object, default: float = 0.0) -> float:
    value = _first_scalar(value)
    if value in (None, "", "None"):
        return default
    return float(value)


def parse_int(value: object, default: int = 0) -> int:
    value = _first_scalar(value)
    if value in (None, "", "None"):
        return default
    return int(float(value))


@dataclass
class CampaignRow:
    campaign_id: str
    campaign_name: str
    objective: str = ""
    results: int = 0
    cost_per_result: float = 0.0
    spend: float = 0.0
    impressions: int = 0
    reach: int = 0
    frequency: float = 0.0
    ctr: float = 0.0
    cpc: float = 0.0
    cpm: float = 0.0
    inline_link_clicks: int = 0
    currency: str = "EGP"
    actions: list[dict] = field(default_factory=list)

    @property
    def clicks(self) -> int:
        return self.inline_link_clicks or round(self.impressions * self.ctr / 100) if self.impressions else 0


@dataclass
class AdsSummary:
    account_id: str
    month: str
    currency: str
    campaigns: list[CampaignRow] = field(default_factory=list)

    @property
    def total_spend(self) -> float:
        return round(sum(c.spend for c in self.campaigns), 2)

    @property
    def total_impressions(self) -> int:
        return sum(c.impressions for c in self.campaigns)

    @property
    def total_reach(self) -> int:
        return sum(c.reach for c in self.campaigns)

    @property
    def total_results(self) -> int:
        return sum(c.results for c in self.campaigns)


INSIGHTS_FIELDS = [
    "campaign_id",
    "campaign_name",
    "objective",
    "results",
    "cost_per_result",
    "spend",
    "impressions",
    "reach",
    "frequency",
    "ctr",
    "cpc",
    "cpm",
    "inline_link_clicks",
    "account_currency",
    "date_start",
    "date_stop",
    "actions",
]


def fetch_campaign_insights(access_token: str, api_version: str, ad_account_id: str, month: str) -> AdsSummary:
    """Fetch per-campaign monthly insights for one Meta ad account.

    Uses the official facebook-business SDK. ad_account_id may be
    'act_123' or bare '123' (normalized to 'act_123').
    """
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.api import FacebookAdsApi

    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    FacebookAdsApi.init(access_token=access_token, api_version=api_version)
    since, until = month_range(month)

    account = AdAccount(ad_account_id)
    response = account.get_insights(
        fields=INSIGHTS_FIELDS,
        params={
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "use_unified_attribution_setting": True,
        },
    )

    campaigns: list[CampaignRow] = []
    currency = "EGP"
    for row in response:
        data = row.get("_data" if hasattr(row, "_data") else "")
        if hasattr(row, "export_all_data"):
            data = row.export_all_data()
        elif isinstance(row, dict):
            data = row
        else:
            data = dict(row) if row else {}

        currency = data.get("account_currency") or currency
        campaigns.append(
            CampaignRow(
                campaign_id=str(data.get("campaign_id", "")),
                campaign_name=str(data.get("campaign_name", "")),
                objective=str(data.get("objective", "")),
                results=parse_int(data.get("results")),
                cost_per_result=parse_float(data.get("cost_per_result")),
                spend=parse_float(data.get("spend")),
                impressions=parse_int(data.get("impressions")),
                reach=parse_int(data.get("reach")),
                frequency=parse_float(data.get("frequency")),
                ctr=parse_float(data.get("ctr")),
                cpc=parse_float(data.get("cpc")),
                cpm=parse_float(data.get("cpm")),
                inline_link_clicks=parse_int(data.get("inline_link_clicks")),
                actions=data.get("actions") or [],
            )
        )

    return AdsSummary(account_id=ad_account_id, month=month, currency=currency, campaigns=campaigns)
