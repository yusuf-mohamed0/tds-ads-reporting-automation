from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tds_ads_reporting.config import Client
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import AdsSummary, fetch_campaign_insights
from tds_ads_reporting.meta.page import (
    InstagramMetrics,
    PageMetrics,
    fetch_instagram_metrics,
    fetch_page_metrics,
    fetch_top_posts,
)
from tds_ads_reporting.google_ads.ads import GoogleAdsSummary, fetch_campaigns


@dataclass
class FetchedData:
    meta_ads: AdsSummary | None = None
    page: PageMetrics | None = None
    top_posts: list | None = None
    instagram: InstagramMetrics | None = None
    google_ads: GoogleAdsSummary | None = None


def fetch_all(
    meta_token: str,
    meta_version: str,
    google_yaml: str,
    client: Client,
    month: str,
    fetch_meta: bool = True,
    fetch_google: bool = True,
) -> FetchedData:
    data = FetchedData()
    if fetch_meta and client.meta.ad_accounts:
        data.meta_ads = fetch_campaign_insights(
            meta_token, meta_version, client.meta.ad_accounts[0], month
        )
        if client.meta.page_id:
            data.page = fetch_page_metrics(meta_token, meta_version, client.meta.page_id, month)
            data.top_posts = fetch_top_posts(meta_token, meta_version, client.meta.page_id, month)
        if client.meta.instagram_id:
            data.instagram = fetch_instagram_metrics(
                meta_token, meta_version, client.meta.instagram_id, month
            )
    if fetch_google and client.google_ads.customer_ids:
        data.google_ads = fetch_campaigns(google_yaml, client.google_ads.customer_ids[0], month)
    return data


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def _fmt_num(value: int) -> str:
    return f"{value:,}"


def build_context(
    client: Client,
    month: str,
    manual: ManualInputs,
    data: FetchedData,
    month_label: str,
    date_start: str,
    date_stop: str,
) -> dict[str, Any]:
    currency = client.currency

    platforms = []
    if client.meta.ad_accounts:
        platforms.append("Meta (Facebook & Instagram)")
    if client.google_ads.customer_ids:
        platforms.append("Google Ads")

    reach: list[dict] = []
    messaging: list[dict] = []
    content: list[dict] = []
    audience: list[dict] = []
    ads: list[dict] = []

    if data.page:
        total_views = data.page.media_views
        reach.append(
            {
                "name": "Facebook",
                "cards": [
                    {"label": "Media Views", "value": _fmt_num(total_views)},
                    {"label": "From Organic", "value": _fmt_num(data.page.organic_views)},
                    {"label": "From Ads", "value": _fmt_num(data.page.paid_views)},
                ],
                "organic_pct": data.page.organic_pct,
                "paid_pct": 100 - data.page.organic_pct,
                "total": _fmt_num(total_views),
                "organic": _fmt_num(data.page.organic_views),
                "paid": _fmt_num(data.page.paid_views),
            }
        )
        messaging.append(
            {
                "name": "Facebook",
                "total_contacts": _fmt_num(data.page.new_conversations),
                "conversations": _fmt_num(data.page.new_conversations),
                "organic": _fmt_num(data.page.new_conversations),
                "paid": "0",
                "organic_pct": 100,
                "paid_pct": 0,
            }
        )
        audience.append(
            {
                "name": "Facebook",
                "followers": _fmt_num(data.page.followers_total),
                "demographics": [{"age": "Total", "female": "-", "male": "-"}],
            }
        )
        if data.top_posts:
            content.append(
                {
                    "name": "Facebook",
                    "top": [
                        {
                            "title": p.message or p.post_id,
                            "date": p.created_time[:10],
                            "views": _fmt_num(p.views),
                            "reach": _fmt_num(p.views),
                            "from_ads": "-",
                        }
                        for p in data.top_posts
                    ],
                }
            )

    if data.instagram:
        ig = data.instagram
        reach.append(
            {
                "name": "Instagram",
                "cards": [
                    {"label": "Reach", "value": _fmt_num(ig.reach)},
                    {"label": "Views", "value": _fmt_num(ig.views)},
                    {"label": "Accounts Engaged", "value": _fmt_num(ig.accounts_engaged)},
                ],
                "organic_pct": 100,
                "paid_pct": 0,
                "total": _fmt_num(ig.reach),
                "organic": _fmt_num(ig.reach),
                "paid": "0",
            }
        )
        audience.append(
            {
                "name": "Instagram",
                "followers": _fmt_num(ig.followers_count),
                "demographics": _demographics_rows(ig.demographics),
            }
        )
        if ig.top_media:
            content.append(
                {
                    "name": "Instagram",
                    "top": [
                        {
                            "title": f"Media {t['id']}",
                            "date": (t.get("timestamp") or "")[:10],
                            "views": _fmt_num(int(t.get("views", 0))),
                            "reach": _fmt_num(int(t.get("reach", 0))),
                            "from_ads": "-",
                        }
                        for t in ig.top_media
                    ],
                }
            )

    if data.meta_ads:
        ads_summary = data.meta_ads
        ads.append(
            {
                "name": "Meta",
                "spend": _fmt_money(ads_summary.total_spend, currency),
                "impressions": _fmt_num(ads_summary.total_impressions),
                "reach": _fmt_num(ads_summary.total_reach),
                "campaigns": [
                    {
                        "name": c.campaign_name,
                        "results": _fmt_num(c.results),
                        "cost_per_result": _fmt_money(c.cost_per_result, currency),
                        "spend": _fmt_money(c.spend, currency),
                        "impressions": _fmt_num(c.impressions),
                        "reach": _fmt_num(c.reach),
                    }
                    for c in ads_summary.campaigns
                ],
            }
        )

    if data.google_ads:
        g = data.google_ads
        ads.append(
            {
                "name": "Google Ads",
                "spend": _fmt_money(g.total_cost, g.currency or currency),
                "impressions": _fmt_num(g.total_impressions),
                "reach": "-",
                "campaigns": [
                    {
                        "name": c.name,
                        "results": _fmt_num(int(c.results)),
                        "cost_per_result": _fmt_money(c.cost_per_result, g.currency or currency),
                        "spend": _fmt_money(c.cost, g.currency or currency),
                        "impressions": _fmt_num(c.impressions),
                        "reach": "-",
                    }
                    for c in g.campaigns
                ],
            }
        )

    return {
        "client": {"name": client.name, "email": client.report_recipient},
        "month_label": month_label,
        "date_start": date_start,
        "date_stop": date_stop,
        "platforms_label": " & ".join(platforms) or "-",
        "toc": [
            "Report Scope",
            "Reach (Facebook)",
            "Reach (Instagram)",
            "Messaging",
            "Top Content",
            "Audience",
            "Ads",
            "Budget & Spend",
            "Insights & Recommendations",
        ],
        "scope_prose": manual.scope_prose,
        "scope_notes": manual.scope_notes,
        "insights": manual.insights,
        "recommendations": manual.recommendations,
        "budget": {
            "amount": _fmt_money(manual.budget.get("amount", 0), currency),
            "spent": _fmt_money(manual.budget.get("spent", 0), currency),
            "vat": _fmt_money(manual.budget.get("vat", 0), currency),
            "remaining": _fmt_money(manual.budget.get("remaining", 0), currency),
        },
        "reach": reach,
        "messaging": messaging,
        "content": content,
        "audience": audience,
        "ads": ads,
    }


def _demographics_rows(demographics: list[dict]) -> list[dict]:
    rows: list[dict] = []
    seen: set[str] = set()
    for block in demographics or []:
        for v in block.get("values", []):
            val = v.get("value")
            if not isinstance(val, dict):
                continue
            for age, breakdown in val.items():
                if age in seen:
                    continue
                seen.add(age)
                if isinstance(breakdown, dict):
                    rows.append(
                        {
                            "age": age,
                            "female": str(breakdown.get("F", 0)),
                            "male": str(breakdown.get("M", 0)),
                        }
                    )
                else:
                    rows.append({"age": age, "female": str(breakdown), "male": "-"})
    return rows or [{"age": "-", "female": "-", "male": "-"}]
