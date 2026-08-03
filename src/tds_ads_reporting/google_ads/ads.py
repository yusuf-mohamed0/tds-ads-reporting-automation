from __future__ import annotations

import calendar
import os
import time
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from google.ads.googleads.client import GoogleAdsClient
from google.api_core.exceptions import ResourceExhausted, DeadlineExceeded

ROOT = Path(__file__).resolve().parents[3]


class GoogleAdsError(RuntimeError):
    pass


@dataclass
class GoogleCampaign:
    campaign_id: int
    name: str
    status: str = ""
    channel_type: str = ""
    results: float = 0.0
    cost_per_result: float = 0.0
    cost: float = 0.0
    impressions: int = 0
    clicks: int = 0
    ctr: float = 0.0
    average_cpc: float = 0.0
    conversions_value: float = 0.0

    @property
    def spend(self) -> float:
        return self.cost


@dataclass
class GoogleAdsSummary:
    customer_id: str
    month: str
    currency: str = ""
    timezone: str = ""
    campaigns: list[GoogleCampaign] = field(default_factory=list)

    @property
    def total_cost(self) -> float:
        return round(sum(c.cost for c in self.campaigns), 2)

    @property
    def total_impressions(self) -> int:
        return sum(c.impressions for c in self.campaigns)

    @property
    def total_clicks(self) -> int:
        return sum(c.clicks for c in self.campaigns)

    @property
    def total_results(self) -> float:
        return sum(c.results for c in self.campaigns)


def _micros(value: Any) -> float:
    return float(value or 0) / 1_000_000


def _rate(value: Any) -> float:
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0.0


GAQL_CAMPAIGN_QUERY = """
SELECT
  campaign.id,
  campaign.name,
  campaign.status,
  campaign.advertising_channel_type,
  metrics.clicks,
  metrics.impressions,
  metrics.ctr,
  metrics.average_cpc,
  metrics.cost_micros,
  metrics.conversions,
  metrics.conversions_value,
  metrics.cost_per_conversion
FROM campaign
WHERE segments.date >= '{since}' AND segments.date <= '{until}'
  AND campaign.status != 'REMOVED'
"""


def _get_client(yaml_path: str) -> GoogleAdsClient:
    return GoogleAdsClient.load_from_storage(path=yaml_path, version="v25")


def _month_dates(month: str) -> tuple[str, str]:
    year, mon = (int(x) for x in month.split("-"))
    since = date(year, mon, 1)
    until = date(year, mon, calendar.monthrange(year, mon)[1])
    return since.isoformat(), until.isoformat()


def fetch_campaigns(yaml_path: str, customer_id: str, month: str) -> GoogleAdsSummary:
    """Fetch monthly per-campaign stats for one Google Ads customer id."""
    since, until = _month_dates(month)
    query = GAQL_CAMPAIGN_QUERY.format(since=since, until=until)

    client = _get_client(yaml_path)
    ga_service = client.get_service("GoogleAdsService")
    request = client.get_type("SearchGoogleAdsStreamRequest")
    request.customer_id = customer_id
    request.query = query

    campaigns: list[GoogleCampaign] = []
    currency = ""
    timezone_name = ""

    for attempt in range(4):
        try:
            stream = ga_service.search_stream(request=request)
            for batch in stream:
                for row in batch.results:
                    campaign = row.campaign
                    metrics = row.metrics
                    campaigns.append(
                        GoogleCampaign(
                            campaign_id=campaign.id,
                            name=campaign.name,
                            status=campaign.status_.name,
                            channel_type=campaign.advertising_channel_type_.name,
                            results=float(metrics.conversions or 0),
                            cost_per_result=_micros(metrics.cost_per_conversion),
                            cost=_micros(metrics.cost_micros),
                            impressions=int(metrics.impressions or 0),
                            clicks=int(metrics.clicks or 0),
                            ctr=_rate(metrics.ctr),
                            average_cpc=_micros(metrics.average_cpc),
                            conversions_value=float(metrics.conversions_value or 0),
                        )
                    )
            break
        except (ResourceExhausted, DeadlineExceeded) as exc:
            if attempt == 3:
                raise GoogleAdsError(f"Google Ads quota exhausted after retries: {exc}") from exc
            time.sleep(5 * (attempt + 1))

    # currency/timezone from customer resource (cheap, separate query)
    try:
        cur_req = client.get_type("SearchGoogleAdsStreamRequest")
        cur_req.customer_id = customer_id
        cur_req.query = "SELECT customer.currency_code, customer.time_zone FROM customer"
        for batch in ga_service.search_stream(request=cur_req):
            for row in batch.results:
                currency = row.customer.currency_code or ""
                timezone_name = row.customer.time_zone or ""
    except Exception:  # noqa: BLE001
        pass

    return GoogleAdsSummary(
        customer_id=customer_id,
        month=month,
        currency=currency,
        timezone=timezone_name,
        campaigns=sorted(campaigns, key=lambda c: c.cost, reverse=True),
    )
