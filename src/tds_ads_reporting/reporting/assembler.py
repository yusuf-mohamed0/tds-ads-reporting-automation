from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

from tds_ads_reporting.config import Client
from tds_ads_reporting.insights.engine import generate_insights
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import (
    AdsSummary,
    MetaAdsDataset,
    fetch_campaign_insights,
    fetch_meta_dataset,
    prev_month_str,
)
from tds_ads_reporting.meta.page import (
    InstagramMetrics,
    PageMetrics,
    fetch_instagram_metrics,
    fetch_page_metrics,
    fetch_top_posts,
)

# Canonical template section ids (in report order).
ALL_SECTIONS = [
    "executive_summary",
    "campaign_performance",
    "conversions",
    "distribution",
    "audience",
    "page_instagram",
    "recommendations",
    "appendix",
]

# Map client.report.include_sections (old/new names) to canonical ids.
SECTION_ALIASES: dict[str, list[str]] = {
    "executive_summary": ["executive_summary", "summary", "overview", "kpis"],
    "campaign_performance": ["campaign_performance", "campaign_breakdown", "campaigns", "meta_ads", "ads", "overall_performance"],
    "conversions": ["conversions", "conversion_breakdown", "conversion", "meta_ads", "campaign_breakdown", "overall_performance"],
    "distribution": ["distribution", "breakdowns", "publishers", "devices", "countries", "meta_ads", "overall_performance"],
    "audience": ["audience", "demographics", "pacing", "audience_insights", "meta_ads", "overall_performance"],
    "page_instagram": ["page_instagram", "page", "instagram", "social", "organic", "content", "reach", "messaging", "meta_ads", "overall_performance"],
    "recommendations": ["recommendations", "insights", "next_steps", "insights_recommendations"],
    "appendix": ["appendix", "methodology", "notes", "manual_inputs"],
}


@dataclass
class FetchedData:
    meta_ads: AdsSummary | MetaAdsDataset | None = None
    page: PageMetrics | None = None
    top_posts: list | None = None
    instagram: InstagramMetrics | None = None


def fetch_all(
    meta_token: str,
    meta_version: str,
    client: Client,
    month: str,
    meta_page_token: str | None = None,
    fetch_meta: bool = True,
    cache=None,
) -> FetchedData:
    data = FetchedData()
    page_token = meta_page_token or meta_token
    if fetch_meta and client.meta.ad_accounts:
        data.meta_ads = _cached(cache, client.id, month, "meta_ads",
                                lambda: fetch_meta_dataset(
                                    meta_token, meta_version, client.meta.ad_accounts[0], month
                                ))
        if client.meta.page_id:
            data.page = _cached(cache, client.id, month, "page",
                                lambda: fetch_page_metrics(page_token, meta_version, client.meta.page_id, month))
            data.top_posts = _cached(cache, client.id, month, "top_posts",
                                     lambda: fetch_top_posts(page_token, meta_version, client.meta.page_id, month))
        if client.meta.instagram_id:
            data.instagram = _cached(cache, client.id, month, "instagram",
                                     lambda: fetch_instagram_metrics(
                                         page_token, meta_version, client.meta.instagram_id, month
                                     ))
    return data


def _cached(cache, client_id: str, month: str, platform: str, fetch):
    """Return cached payload if present, else fetch, serialize, and store."""
    if cache is not None:
        cached = cache.get(client_id, month, platform)
        if cached is not None:
            return _deserialize(cached, platform)
    value = fetch()
    if cache is not None:
        try:
            cache.set(client_id, month, platform, _serialize(value))
        except Exception:  # noqa: BLE001
            pass
    return value


def _serialize(value):
    from dataclasses import asdict

    return asdict(value)


def _deserialize(data: dict, platform: str):
    from tds_ads_reporting.meta.ads import AdsSummary, CampaignRow, MetaAdsDataset
    from tds_ads_reporting.meta.page import InstagramMetrics, PageMetrics, PostRow

    if platform == "meta_ads":
        campaigns = [CampaignRow(**d) for d in data.get("campaigns", [])]
        cls = MetaAdsDataset if "adsets" in data else AdsSummary
        return cls(**{**data, "campaigns": campaigns})
    if platform == "page":
        return PageMetrics(**data)
    if platform == "top_posts":
        return [PostRow(**d) for d in data]
    if platform == "instagram":
        return InstagramMetrics(**data)
    return data


def _fmt_money(value: float, currency: str) -> str:
    if value and abs(value) < 1:
        return f"{value:,.2f} {currency}"
    return f"{value:,.0f} {currency}"


def _fmt_num(value: int) -> str:
    return f"{value:,}"


def _resolve_sections(client: Client) -> list[str]:
    configured = client.report.get("include_sections") or []
    if not configured:
        return list(ALL_SECTIONS)
    out = []
    for section in ALL_SECTIONS:
        aliases = SECTION_ALIASES.get(section, [section])
        if any(a in configured for a in aliases):
            out.append(section)
    return out


def _campaign_table_rows(
    dataset: MetaAdsDataset, currency: str, prev_campaigns: dict[str, dict]
) -> list[dict[str, Any]]:
    total_spend = dataset.total_spend
    total_results = dataset.total_results or 1
    rows = []
    for c in dataset.campaigns:
        spend_share = round(c.spend / total_spend * 100, 1) if total_spend else 0.0
        cpr = c.cost_per_result or (round(c.spend / c.results, 2) if c.results else 0.0)
        prev_spend = float(prev_campaigns.get(c.campaign_id, {}).get("spend") or 0.0)
        mom_spend_delta_pct = round((c.spend - prev_spend) / prev_spend * 100, 1) if prev_spend else None
        rows.append(
            {
                "campaign_id": c.campaign_id,
                "name": c.campaign_name,
                "objective": c.objective,
                "status": c.status or "-",
                "effective_status": c.effective_status or c.status or "-",
                "lifecycle": c.lifecycle or "-",
                "start_time": c.start_time,
                "stop_time": c.stop_time,
                "spend": c.spend,
                "spend_fmt": f"{c.spend:,.0f}",
                "results": c.results,
                "cpr": cpr,
                "cpr_fmt": f"{cpr:,.0f}",
                "ctr": c.ctr,
                "cpc": c.cpc,
                "cpm": c.cpm,
                "frequency": c.frequency,
                "impressions": c.impressions,
                "reach": c.reach,
                "clicks": c.clicks,
                "share_pct": spend_share,
                "bar_width": max(spend_share, 2.0) if spend_share else 0.0,
                "results_pct": round(c.results / total_results * 100, 1),
                "mom_spend_delta_pct": mom_spend_delta_pct,
            }
        )
    rows.sort(key=lambda r: r["spend"], reverse=True)
    return rows


def _conversion_rows(conversions: dict[str, dict], currency: str) -> list[dict[str, Any]]:
    total = sum(v.get("count", 0) for v in conversions.values()) or 1
    rows = [
        {
            "action_type": at,
            "label": at.replace("_", " ").replace(".", " / ").title(),
            "count": int(v.get("count", 0)),
            "cost": float(v.get("cost", 0.0)),
            "cost_fmt": _fmt_money(v.get("cost", 0.0), currency),
            "cpa": float(v.get("cpa", 0.0)),
            "cpa_fmt": _fmt_money(v.get("cpa", 0.0), currency),
            "pct": round(v.get("count", 0) / total * 100, 1),
        }
        for at, v in conversions.items()
    ]
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def _bucket_rows(buckets: list[dict], currency: str) -> list[dict[str, Any]]:
    max_spend = max((b.get("spend", 0) for b in buckets), default=0) or 1
    rows = []
    for b in buckets:
        share = float(b.get("pct", 0) or 0.0)
        rows.append(
            {
                "label": b.get("label", ""),
                "spend": float(b.get("spend", 0.0)),
                "spend_fmt": _fmt_money(b.get("spend", 0.0), currency),
                "impressions": int(b.get("impressions", 0)),
                "clicks": int(b.get("clicks", 0)),
                "results": int(b.get("results", 0)),
                "ctr": float(b.get("ctr", 0.0)),
                "pct": share,
                "bar_width": max(share, 2.0) if share else 0.0,
                "bar_spend": round(float(b.get("spend", 0.0)) / max_spend * 100, 1),
            }
        )
    return rows


def _demographic_rows(demographics: list[dict], currency: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    max_spend = max((d.get("spend", 0) for d in demographics), default=0) or 1
    rows = []
    pivot: dict[str, dict[str, Any]] = {}
    for d in demographics:
        age = d.get("age", "")
        gender = d.get("gender", "")
        spend = float(d.get("spend", 0.0))
        rows.append(
            {
                "age": age,
                "gender": gender,
                "spend": spend,
                "spend_fmt": _fmt_money(spend, currency),
                "impressions": int(d.get("impressions", 0)),
                "results": int(d.get("results", 0)),
                "pct": float(d.get("pct", 0.0)),
                "bar_width": max(float(d.get("pct", 0.0)), 2.0) if d.get("pct", 0) else 0.0,
                "bar_spend": round(spend / max_spend * 100, 1),
            }
        )
        cell = pivot.setdefault(age, {"M": 0.0, "F": 0.0, "total": 0.0})
        if gender in ("M", "male"):
            cell["M"] += spend
        elif gender in ("F", "female"):
            cell["F"] += spend
        cell["total"] += spend
    for cell in pivot.values():
        for key in ("M", "F", "total"):
            cell[key] = f"{cell[key]:,.0f}"
    return rows, pivot


def _flag_table_rows(campaign_rows: list[dict[str, Any]], insights_payload: dict[str, Any]) -> None:
    """Mark TOP (best by results) and WEAK (flagged) rows so the template can
    highlight them without double-flagging every campaign."""
    top_camps = insights_payload.get("top_campaigns") or []
    bottom_camps = insights_payload.get("bottom_campaigns") or []
    top_ids = {c.get("campaign_id") for c in top_camps if c.get("results", 0) > 0}
    bottom_ids = {c.get("campaign_id") for c in bottom_camps if c.get("flags")}
    for row in campaign_rows:
        row["is_top"] = row["campaign_id"] in top_ids and row["campaign_id"] not in bottom_ids
        row["is_bottom"] = row["campaign_id"] in bottom_ids


def _pacing_series(pacing: dict[str, dict]) -> list[dict[str, Any]]:
    max_spend = max((v.get("spend", 0) for v in pacing.values()), default=0) or 1
    out = []
    for label, v in pacing.items():
        spend = float(v.get("spend", 0.0))
        pct = float(v.get("pct", 0.0))
        out.append(
            {
                "label": label,
                "spend": spend,
                "spend_fmt": _fmt_money(spend, ""),
                "pct": pct,
                "bar_width": max(pct, 2.0) if pct else 0.0,
                "bar_spend": round(spend / max_spend * 100, 1),
            }
        )
    return out


def build_context(
    client: Client,
    month: str,
    manual: ManualInputs,
    data: FetchedData | None,
    month_label: str,
    date_start: str,
    date_stop: str,
) -> dict[str, Any]:
    currency = client.currency
    if data is None:
        data = FetchedData()

    platforms = []
    if client.meta.ad_accounts:
        platforms.append("Meta (Facebook & Instagram)")

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
                "followers": _fmt_num(data.page.followers_total),
                "followers_delta": _fmt_num(data.page.followers_delta),
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
                "followers_delta": _fmt_num(data.page.followers_delta),
                "demographics": [{"age": "Total", "female": "-", "male": "-"}],
                "geo": _geo_rows(data.page.geo),
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
                "followers": _fmt_num(ig.followers_count),
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

    # ---- Manually supplied organic numbers (Business Suite screenshots) ----
    # Mirrors the historical March workflow: the account manager types the
    # monthly organic values into manual_inputs/<client>_<month>.yaml and the
    # report renders them on the reference pages. API data always wins when
    # present; manual values only fill platforms Meta could not serve.
    for platform_name in ("Facebook", "Instagram"):
        entry = (manual.organic or {}).get(platform_name.lower()) or {}
        if not entry:
            continue
        if entry.get("reach_cards") and not any(row.get("name") == platform_name for row in reach):
            reach.append(
                {
                    "name": platform_name,
                    "cards": [
                        {"label": str(c.get("label", "")), "value": str(c.get("value", ""))}
                        for c in entry["reach_cards"]
                    ],
                    "organic_pct": int(entry.get("organic_pct") or 0),
                    "paid_pct": 100 - int(entry.get("organic_pct") or 0),
                    "followers": _fmt_num(entry.get("followers") or 0) if entry.get("followers") is not None else "",
                }
            )
        if entry.get("messaging_contacts") is not None and not any(row.get("name") == platform_name for row in messaging):
            messaging.append(
                {
                    "name": platform_name,
                    "total_contacts": _fmt_num(entry["messaging_contacts"]),
                    "conversations": _fmt_num(entry.get("conversations_started") or entry["messaging_contacts"]),
                    "organic_pct": int(entry.get("organic_pct") or 0),
                    "paid_pct": 100 - int(entry.get("organic_pct") or 0),
                }
            )
        if entry.get("content_rows") and not any(row.get("name") == platform_name for row in content):
            content.append(
                {
                    "name": platform_name,
                    "top": [
                        {
                            "title": str(r.get("title", "")),
                            "date": str(r.get("date", "")),
                            "views": _fmt_num(r.get("views") or 0),
                            "reach": _fmt_num(r.get("reach") or 0),
                        }
                        for r in entry["content_rows"][:10]
                    ],
                }
            )
        if entry.get("followers") is not None and not any(row.get("name") == platform_name for row in audience):
            audience.append(
                {
                    "name": platform_name,
                    "followers": _fmt_num(entry["followers"]),
                    "geo": [
                        {"country": str(g.get("country", "")), "value": _fmt_num(g.get("value") or 0)}
                        for g in entry.get("geo") or []
                    ],
                }
            )

    # ---- Meta ads dataset + insights engine --------------------------------
    dataset: MetaAdsDataset | None = None
    insights_payload: dict[str, Any] = {}
    campaign_rows: list[dict[str, Any]] = []
    conversion_rows: list[dict[str, Any]] = []
    device_rows: list[dict[str, Any]] = []
    publisher_rows: list[dict[str, Any]] = []
    country_rows: list[dict[str, Any]] = []
    demographic_rows: list[dict[str, Any]] = []
    age_gender: dict[str, Any] = {}
    dow_series: list[dict[str, Any]] = []
    hour_series: list[dict[str, Any]] = []
    top_adsets: list[dict[str, Any]] = []

    if data.meta_ads:
        raw = data.meta_ads
        if isinstance(raw, MetaAdsDataset):
            dataset = raw
        else:  # legacy AdsSummary — promote to a minimal dataset
            dataset = MetaAdsDataset(
                account_id=raw.account_id,
                month=raw.month,
                currency=raw.currency,
                campaigns=raw.campaigns,
            )
            dataset.totals = {
                "spend": dataset.total_spend,
                "impressions": dataset.total_impressions,
                "reach": dataset.total_reach,
                "results": dataset.total_results,
                "clicks": sum(c.clicks for c in dataset.campaigns),
            }
        ads_summary = dataset

        try:
            insights_payload = generate_insights(dataset, manual, client, currency)
        except Exception as exc:  # noqa: BLE001
            insights_payload = {"anomalies": [], "recommendations": [], "kpis": {}}
            insights_payload["engine_error"] = str(exc)

        prev_campaigns = {
            (pc.get("campaign_id") or ""): pc for pc in (dataset.prev_month or {}).get("campaigns") or []
        }
        campaign_rows = _campaign_table_rows(dataset, currency, prev_campaigns)
        _flag_table_rows(campaign_rows, insights_payload)
        conversion_rows = _conversion_rows(dataset.conversions, currency)
        device_rows = _bucket_rows(dataset.devices, currency)
        publisher_rows = _bucket_rows(dataset.publishers, currency)
        country_rows = _bucket_rows(dataset.countries, currency)
        demographic_rows, age_gender = _demographic_rows(dataset.demographics, currency)
        dow_series = _pacing_series(dataset.dow_pacing)
        hour_series = _pacing_series(dataset.hour_pacing)
        top_adsets = sorted(dataset.adsets, key=lambda a: a.get("spend", 0), reverse=True)[:15]
        for a in top_adsets:
            a["spend_fmt"] = f"{float(a.get('spend', 0.0)):,.0f}"
            a["cpr_fmt"] = f"{float(a.get('cost_per_result') or 0.0):,.0f}"
            a["impressions_fmt"] = f"{int(a.get('impressions', 0)):,}"

        ads.append(
            {
                "name": "Meta",
                "spend": _fmt_money(ads_summary.total_spend, currency),
                "impressions": _fmt_num(ads_summary.total_impressions),
                "reach": _fmt_num(ads_summary.total_reach),
                "results": _fmt_num(ads_summary.total_results),
                "campaigns": [
                    {
                        "name": c.campaign_name,
                        "results": _fmt_num(c.results),
                        "cost_per_result": _fmt_money(c.cost_per_result or (round(c.spend / c.results, 2) if c.results else 0.0), currency),
                        "spend": _fmt_money(c.spend, currency),
                        "impressions": _fmt_num(c.impressions),
                        "reach": _fmt_num(c.reach),
                    }
                    for c in ads_summary.campaigns
                ],
            }
        )

    kpis = insights_payload.get("kpis") or {}
    mom = insights_payload.get("mom") or {}
    pacing = insights_payload.get("pacing") or {}
    recommendations = insights_payload.get("recommendations") or manual.recommendations
    platform_rows = insights_payload.get("platforms") or []
    data_quality = insights_payload.get("data_quality") or []

    # Ads Insights is still available when the token lacks Page/Instagram
    # permissions. Use those exact paid metrics rather than emitting empty
    # Reach or Messaging pages.
    results_label = insights_payload.get("results_label") or "Results"
    for platform in platform_rows:
        name = platform.get("label")
        if name not in {"Facebook", "Instagram"}:
            continue
        if not any(row.get("name") == name for row in reach):
            reach.append(
                {
                    "name": name,
                    "cards": [
                        {"label": "Paid Impressions", "value": _fmt_num(platform.get("impressions", 0))},
                        {"label": "Paid Reach", "value": _fmt_num(platform.get("reach", 0))},
                        {"label": results_label, "value": _fmt_num(platform.get("results", 0))},
                    ],
                    "organic_pct": 0,
                    "paid_pct": 100,
                }
            )
        if results_label == "Messages" and not any(row.get("name") == name for row in messaging):
            messages = int(platform.get("results") or 0)
            messaging.append(
                {
                    "name": name,
                    "total_contacts": _fmt_num(messages),
                    "conversations": _fmt_num(messages),
                    "organic": "0",
                    "paid": _fmt_num(messages),
                    "organic_pct": 0,
                    "paid_pct": 100,
                }
            )

    budget_amount = float(manual.budget.get("amount") or 0)
    budget_spent = float(manual.budget.get("spent") or kpis.get("spend") or 0)
    budget_vat = float(manual.budget.get("vat") or 0)
    budget_remaining = float(manual.budget.get("remaining") or 0)
    budget = {
        "amount": _fmt_money(budget_amount, currency) if budget_amount else "Not provided",
        "spent": _fmt_money(budget_spent, currency),
        "vat": _fmt_money(budget_vat, currency) if budget_vat else "Not provided",
        "remaining": _fmt_money(budget_remaining, currency) if budget_amount else "Not provided",
    }

    prev_month_label = insights_payload.get("prev_month_label")
    if not prev_month_label and dataset and dataset.prev_month:
        from tds_ads_reporting.meta.ads import month_label as _ml

        prev_month_label = _ml((dataset.prev_month or {}).get("month") or prev_month_str(month))

    revenue = manual.revenue if manual.revenue is not None else manual.budget.get("revenue")

    return {
        "client": {"name": client.name, "email": client.report_recipient},
        "month_label": month_label,
        "date_start": date_start,
        "date_stop": date_stop,
        "report_date": date.today().isoformat(),
        "platforms_label": " & ".join(platforms) or "-",
        "include_sections": _resolve_sections(client),
        "report_notes": client.report.get("notes") or {},
        "toc": [
            "Executive Summary",
            "Campaign Performance",
            "Conversion Breakdown",
            "Distribution",
            "Audience Insights",
            "Page & Instagram",
            "Recommendations",
            "Appendix",
        ],
        "scope_prose": manual.scope_prose,
        "scope_notes": manual.scope_notes,
        "insights": manual.insights,
        "recommendations": recommendations,
        "manual_recommendations": manual.recommendations,
        "budget": budget,
        "reach": reach,
        "messaging": messaging,
        "content": content,
        "audience": audience,
        "ads": ads,
        # ---- new (rich) keys ----
        "executive_summary": insights_payload.get("executive_summary", ""),
        "kpis": kpis,
        "top_campaigns": insights_payload.get("top_campaigns") or [],
        "bottom_campaigns": insights_payload.get("bottom_campaigns") or [],
        "anomalies": insights_payload.get("anomalies") or [],
        "campaigns": campaign_rows,
        "conversions": conversion_rows,
        "devices": device_rows,
        "publishers": publisher_rows,
        "countries": country_rows,
        "demographics": demographic_rows,
        "age_gender": age_gender,
        "dow_pacing": dow_series,
        "hour_pacing": hour_series,
        "top_adsets": top_adsets,
        "pacing": pacing,
        "mom": mom,
        "platforms": platform_rows,
        "data_quality": data_quality,
        "results_label": results_label,
        "ai": insights_payload.get("ai"),
        "prev_month_label": prev_month_label,
        "has_meta": dataset is not None,
        "has_page": data.page is not None,
        "has_instagram": data.instagram is not None,
        "revenue": revenue,
        "revenue_fmt": _fmt_money(revenue, currency) if revenue else None,
        "currency": currency,
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


def _geo_rows(geo: list[dict]) -> list[dict]:
    rows: list[dict] = []
    for block in geo or []:
        for v in block.get("values", []):
            val = v.get("value")
            if isinstance(val, list):
                for item in val:
                    if isinstance(item, dict) and item.get("name"):
                        rows.append(
                            {"country": str(item["name"]), "value": f"{item.get('value', 0):,}"}
                        )
    return sorted(rows, key=lambda r: r["value"], reverse=True)[:15]
