from __future__ import annotations

import calendar
import logging
from dataclasses import dataclass, field
from datetime import date

log = logging.getLogger("tds.meta.ads")


def month_range(month: str) -> tuple[str, str]:
    """Inclusive [since, until] date bounds for a YYYY-MM month.

    Meta's Ads Insights time_range treats both `since` and `until` as inclusive
    dates. Using the first day of the NEXT month as `until` would leak one day
    of the following month into every report, so we use the last day of the
    reported month.
    """
    year, mon = (int(x) for x in month.split("-"))
    last = calendar.monthrange(year, mon)[1]
    since = date(year, mon, 1).isoformat()
    until = date(year, mon, last).isoformat()
    return since, until


def month_label(month: str) -> str:
    year, mon = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[mon]} {year}"


def prev_month_str(month: str) -> str:
    """Return the 'YYYY-MM' string for the month before `month`."""
    year, mon = (int(x) for x in month.split("-"))
    if mon == 1:
        return f"{year - 1}-12"
    return f"{year}-{mon - 1:02d}"


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
    status: str = ""
    effective_status: str = ""
    start_time: str = ""
    stop_time: str = ""
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
    lifecycle: str = ""
    results_label: str = ""

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


@dataclass
class MetaAdsDataset:
    """Rich per-client/month Meta dataset consumed by the insights engine + template.

    All breakdown fields are plain JSON-safe structures so the SQLite cache
    round-trips them without custom deserializers.
    """

    account_id: str
    month: str
    currency: str
    campaigns: list[CampaignRow] = field(default_factory=list)
    adsets: list[dict] = field(default_factory=list)
    conversions: dict[str, dict] = field(default_factory=dict)
    devices: list[dict] = field(default_factory=list)
    publishers: list[dict] = field(default_factory=list)
    countries: list[dict] = field(default_factory=list)
    demographics: list[dict] = field(default_factory=list)
    dow_pacing: dict[str, dict] = field(default_factory=dict)
    hour_pacing: dict[str, dict] = field(default_factory=dict)
    daily_spend: list[dict] = field(default_factory=list)
    totals: dict[str, float] = field(default_factory=dict)
    account_totals: dict[str, float] = field(default_factory=dict)
    platforms: dict[str, dict] = field(default_factory=dict)
    platform_conversions: dict[str, dict] = field(default_factory=dict)
    prev_month: dict = field(default_factory=dict)

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

ADSET_FIELDS = INSIGHTS_FIELDS + ["adset_id", "adset_name"]

CONVERSION_FIELDS = [
    "campaign_id",
    "campaign_name",
    "spend",
    "actions",
    "cost_per_action_type",
]

BREAKDOWN_FIELDS = [
    "spend",
    "impressions",
    "inline_link_clicks",
    "ctr",
    "results",
    "reach",
    "frequency",
    "cpc",
    "cpm",
]

DAILY_FIELDS = ["spend", "date_start"]

# Meta's hourly_stats_aggregated_by_audience_time_zone breakdown encodes the
# day-of-week as 0..6 where 0 = Sunday (same convention as JS Date.getDay()).
_DOW_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]


def _rows_from_response(response) -> list[dict]:
    """Normalize SDK insight objects (or plain dicts) into plain dicts."""
    rows: list[dict] = []
    for row in response:
        if hasattr(row, "export_all_data"):
            rows.append(row.export_all_data())
        elif isinstance(row, dict):
            rows.append(row)
        else:
            rows.append(dict(row) if row else {})
    return rows


def _get_insights(
    access_token: str,
    api_version: str,
    ad_account_id: str,
    fields: list[str],
    params: dict,
) -> list[dict]:
    """Initialize the SDK and return normalized insight rows as plain dicts."""
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.api import FacebookAdsApi

    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    FacebookAdsApi.init(access_token=access_token, api_version=api_version)
    account = AdAccount(ad_account_id)
    response = account.get_insights(fields=fields, params=params)
    return _rows_from_response(response)


def _get_campaigns(access_token: str, api_version: str, ad_account_id: str) -> list[dict]:
    """Fetch campaign objects (id/name/status/dates) to enrich the campaign table."""
    from facebook_business.adobjects.adaccount import AdAccount
    from facebook_business.api import FacebookAdsApi

    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    FacebookAdsApi.init(access_token=access_token, api_version=api_version)
    account = AdAccount(ad_account_id)
    response = account.get_campaigns(
        fields=["id", "name", "status", "effective_status", "objective", "start_time", "stop_time"]
    )
    return _rows_from_response(response)


def _results_label(objective: str, actions: list[dict], results: int = 0) -> str:
    """Human label for what 'results' means for a campaign.

    Uses the dominant action type when available, falling back to the
    campaign objective so the reader always knows WHAT the result is
    (leads, messages, purchases, link clicks, engagement, video views...).
    """
    objective = (objective or "").upper()
    by_type: dict[str, float] = {}
    for item in actions or []:
        at = str(item.get("action_type") or "")
        value = parse_float(item.get("value"))
        if at:
            by_type[at] = by_type.get(at, 0.0) + value
    if by_type:
        matched = [action for action, value in by_type.items() if results and round(value) == results]
        action = matched[0] if len(matched) == 1 else max(by_type, key=by_type.get)
        low = action.lower()
        if "purchase" in low or low == "omni_purchase":
            return "Purchases"
        if "lead" in low or low == "on_view_portal" or "leadgen" in low:
            return "Leads"
        if "messaging" in low or low == "onsite_conversation_started" or "conversation" in low:
            return "Messages"
        if low == "link_click" or "link_click" in low:
            return "Link Clicks"
        if "video_view" in low or low == "video_views":
            return "Video Views"
        if "post_engagement" in low or low == "post_engagement":
            return "Post Engagements"
        if "post_reaction" in low:
            return "Post Reactions"
        if "comment" in low:
            return "Comments"
        if "app_install" in low or "mobile_app_install" in low:
            return "App Installs"
    objective_map = {
        "OUTCOME_LEADS": "Leads",
        "OUTCOME_CONVERSATIONS": "Messages",
        "OUTCOME_SALES": "Conversions (Purchases)",
        "OUTCOME_TRAFFIC": "Link Clicks",
        "OUTCOME_ENGAGEMENT": "Post Engagements",
        "OUTCOME_APP_PROMOTION": "App Installs",
        "OUTCOME_VIDEO_VIEWS": "Video Views",
        "OUTCOME_REACH": "Reach",
        "OUTCOME_AWARENESS": "Awareness (Reach)",
    }
    return objective_map.get(objective, "Results")


def _campaign_row(data: dict, currency: str) -> CampaignRow:
    return CampaignRow(
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
        currency=currency,
        actions=data.get("actions") or [],
        results_label=_results_label(
            data.get("objective", ""), data.get("actions") or [], parse_int(data.get("results"))
        ),
    )


def fetch_campaign_insights(access_token: str, api_version: str, ad_account_id: str, month: str) -> AdsSummary:
    """Fetch per-campaign monthly insights for one Meta ad account.

    Uses the official facebook-business SDK. ad_account_id may be
    'act_123' or bare '123' (normalized to 'act_123').
    """
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        INSIGHTS_FIELDS,
        {
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "use_unified_attribution_setting": True,
        },
    )

    campaigns: list[CampaignRow] = []
    currency = "EGP"
    for data in rows:
        currency = data.get("account_currency") or currency
        campaigns.append(_campaign_row(data, currency))

    return AdsSummary(account_id=ad_account_id, month=month, currency=currency, campaigns=campaigns)


# ---------------------------------------------------------------------------
# Rich dataset fetchers (each wrapped individually so a single failure never
# kills the whole report — the system degrades gracefully).
# ---------------------------------------------------------------------------


def _attach_statuses(access_token: str, api_version: str, ad_account_id: str, campaigns: list[CampaignRow]) -> None:
    by_id = {c.campaign_id: c for c in campaigns}
    for data in _get_campaigns(access_token, api_version, ad_account_id):
        cid = str(data.get("id", ""))
        if cid in by_id:
            by_id[cid].status = str(data.get("status", ""))
            by_id[cid].effective_status = str(data.get("effective_status", "") or data.get("status", ""))
            by_id[cid].start_time = str(data.get("start_time", "") or "")
            by_id[cid].stop_time = str(data.get("stop_time", "") or "")


def _fetch_adsets(access_token: str, api_version: str, ad_account_id: str, month: str) -> list[dict]:
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        ADSET_FIELDS,
        {
            "level": "adset",
            "time_range": {"since": since, "until": until},
            "use_unified_attribution_setting": True,
        },
    )
    adsets = []
    for data in rows:
        adsets.append(
            {
                "adset_id": str(data.get("adset_id", "")),
                "adset_name": str(data.get("adset_name", "")),
                "campaign_id": str(data.get("campaign_id", "")),
                "campaign_name": str(data.get("campaign_name", "")),
                "objective": str(data.get("objective", "")),
                "results": parse_int(data.get("results")),
                "cost_per_result": parse_float(data.get("cost_per_result")),
                "spend": parse_float(data.get("spend")),
                "impressions": parse_int(data.get("impressions")),
                "reach": parse_int(data.get("reach")),
                "frequency": parse_float(data.get("frequency")),
                "ctr": parse_float(data.get("ctr")),
                "cpc": parse_float(data.get("cpc")),
                "cpm": parse_float(data.get("cpm")),
                "inline_link_clicks": parse_int(data.get("inline_link_clicks")),
            }
        )
    adsets.sort(key=lambda a: a["spend"], reverse=True)
    return adsets[:50]  # bound cache size; assembler narrows to top ~15


def _fetch_conversions(access_token: str, api_version: str, ad_account_id: str, month: str) -> dict[str, dict]:
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        CONVERSION_FIELDS,
        {
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "use_unified_attribution_setting": True,
        },
    )
    totals: dict[str, dict] = {}
    for data in rows:
        spend = parse_float(data.get("spend"))
        cost_by_type: dict[str, float] = {}
        for item in data.get("cost_per_action_type") or []:
            at = str(item.get("action_type", ""))
            if at:
                cost_by_type[at] = parse_float(item.get("value"))
        for item in data.get("actions") or []:
            at = str(item.get("action_type", ""))
            count = parse_float(item.get("value"))
            if not at or count <= 0:
                continue
            entry = totals.setdefault(at, {"count": 0.0, "cost": 0.0, "cpa": 0.0})
            entry["count"] += count
            entry["cost"] += cost_by_type.get(at, 0.0)
    for at, entry in totals.items():
        if entry["cost"] <= 0 and entry["count"] > 0:
            entry["cost"] = 0.0  # cost-per-action not returned; leave 0
        entry["cpa"] = round(entry["cost"] / entry["count"], 2) if entry["count"] else 0.0
        entry["count"] = int(round(entry["count"]))
        entry["cost"] = round(entry["cost"], 2)
    return totals


def _fetch_breakdown(
    access_token: str, api_version: str, ad_account_id: str, month: str, breakdown: str
) -> list[dict]:
    """Fetch a single-dimension breakdown aggregated across campaigns."""
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        BREAKDOWN_FIELDS,
        {
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "breakdowns": [breakdown],
            "use_unified_attribution_setting": True,
        },
    )
    buckets: dict[str, dict] = {}
    for data in rows:
        label = str(data.get(breakdown, "") or "")
        if not label:
            continue
        bucket = buckets.setdefault(
            label,
            {"label": label, "spend": 0.0, "impressions": 0, "clicks": 0, "results": 0, "ctr": 0.0},
        )
        bucket["spend"] += parse_float(data.get("spend"))
        bucket["impressions"] += parse_int(data.get("impressions"))
        bucket["clicks"] += parse_int(data.get("inline_link_clicks"))
        bucket["results"] += parse_int(data.get("results"))
    total_spend = sum(b["spend"] for b in buckets.values()) or 0.0
    out = []
    for bucket in buckets.values():
        bucket["ctr"] = round(bucket["clicks"] / bucket["impressions"] * 100, 2) if bucket["impressions"] else 0.0
        bucket["pct"] = round(bucket["spend"] / total_spend * 100, 1) if total_spend else 0.0
        bucket["spend"] = round(bucket["spend"], 2)
        out.append(bucket)
    out.sort(key=lambda b: b["spend"], reverse=True)
    return out


def _fetch_countries(access_token: str, api_version: str, ad_account_id: str, month: str) -> list[dict]:
    return _fetch_breakdown(access_token, api_version, ad_account_id, month, "country")[:10]


def _fetch_demographics(access_token: str, api_version: str, ad_account_id: str, month: str) -> list[dict]:
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        BREAKDOWN_FIELDS,
        {
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "breakdowns": ["age", "gender"],
            "use_unified_attribution_setting": True,
        },
    )
    buckets: dict[tuple[str, str], dict] = {}
    for data in rows:
        age = str(data.get("age", "") or "")
        gender = str(data.get("gender", "") or "")
        if not age or not gender:
            continue
        key = (age, gender)
        bucket = buckets.setdefault(
            key,
            {"age": age, "gender": gender, "spend": 0.0, "impressions": 0, "results": 0, "pct": 0.0},
        )
        bucket["spend"] += parse_float(data.get("spend"))
        bucket["impressions"] += parse_int(data.get("impressions"))
        bucket["results"] += parse_int(data.get("results"))
    total_spend = sum(b["spend"] for b in buckets.values()) or 0.0
    out = []
    for bucket in buckets.values():
        bucket["spend"] = round(bucket["spend"], 2)
        bucket["pct"] = round(bucket["spend"] / total_spend * 100, 1) if total_spend else 0.0
        out.append(bucket)
    out.sort(key=lambda b: b["spend"], reverse=True)
    return out[:10]


def _fetch_hourly_pacing(
    access_token: str, api_version: str, ad_account_id: str, month: str
) -> tuple[dict[str, dict], dict[str, dict]]:
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        ["spend"],
        {
            "level": "campaign",
            "time_range": {"since": since, "until": until},
            "breakdowns": ["hourly_stats_aggregated_by_audience_time_zone"],
            "use_unified_attribution_setting": True,
        },
    )
    dow: dict[int, float] = {}
    hour: dict[int, float] = {}
    for data in rows:
        raw = str(data.get("hourly_stats_aggregated_by_audience_time_zone", "") or "")
        try:
            dow_idx, hour_idx = (int(x) for x in raw.split(":"))
        except (ValueError, TypeError):
            continue
        spend = parse_float(data.get("spend"))
        dow[dow_idx] = dow.get(dow_idx, 0.0) + spend
        hour[hour_idx] = hour.get(hour_idx, 0.0) + spend

    total = sum(dow.values()) or 0.0
    dow_pacing = {
        _DOW_NAMES[i]: {"spend": round(dow.get(i, 0.0), 2), "pct": round(dow.get(i, 0.0) / total * 100, 1) if total else 0.0}
        for i in range(7)
    }
    hour_pacing = {
        f"{h:02d}": {"spend": round(hour.get(h, 0.0), 2), "pct": round(hour.get(h, 0.0) / total * 100, 1) if total else 0.0}
        for h in range(24)
    }
    return dow_pacing, hour_pacing


def _fetch_daily_spend(access_token: str, api_version: str, ad_account_id: str, month: str) -> list[dict]:
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        DAILY_FIELDS,
        {
            "level": "account",
            "time_range": {"since": since, "until": until},
            "time_increment": "1",
        },
    )
    out = []
    for data in rows:
        day = str(data.get("date_start", ""))
        if not day:
            continue
        out.append({"date": day, "spend": round(parse_float(data.get("spend")), 2)})
    out.sort(key=lambda d: d["date"])
    return out


def _fetch_account_totals(access_token: str, api_version: str, ad_account_id: str, month: str) -> dict[str, float]:
    """Account-level insights for the month (unique reach/frequency, not summed)."""
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        [
            "spend",
            "results",
            "impressions",
            "reach",
            "frequency",
            "ctr",
            "cpc",
            "cpm",
            "inline_link_clicks",
        ],
        {
            "level": "account",
            "time_range": {"since": since, "until": until},
            "use_unified_attribution_setting": True,
        },
    )
    if not rows:
        return {}
    data = rows[0]
    clicks = parse_int(data.get("inline_link_clicks")) or round(parse_float(data.get("impressions")) * parse_float(data.get("ctr")) / 100)
    return {
        "spend": round(parse_float(data.get("spend")), 2),
        "results": parse_int(data.get("results")),
        "impressions": parse_int(data.get("impressions")),
        "reach": parse_int(data.get("reach")),
        "clicks": clicks,
        "ctr": parse_float(data.get("ctr")),
        "cpc": parse_float(data.get("cpc")),
        "cpm": parse_float(data.get("cpm")),
        "frequency": parse_float(data.get("frequency")),
        "cpr": round(parse_float(data.get("spend")) / parse_int(data.get("results")), 2) if parse_int(data.get("results")) else 0.0,
    }


def _fetch_platform_metrics(access_token: str, api_version: str, ad_account_id: str, month: str) -> dict[str, dict]:
    """Per-publisher-platform metrics at ACCOUNT level (deduped reach/frequency)."""
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        BREAKDOWN_FIELDS,
        {
            "level": "account",
            "time_range": {"since": since, "until": until},
            "breakdowns": ["publisher_platform"],
            "use_unified_attribution_setting": True,
        },
    )
    out: dict[str, dict] = {}
    total_spend = 0.0
    for data in rows:
        label = str(data.get("publisher_platform", "") or "").lower()
        if not label:
            continue
        entry = {
            "platform": label,
            "spend": round(parse_float(data.get("spend")), 2),
            "results": parse_int(data.get("results")),
            "impressions": parse_int(data.get("impressions")),
            "reach": parse_int(data.get("reach")),
            "clicks": parse_int(data.get("inline_link_clicks")),
            "ctr": parse_float(data.get("ctr")),
            "cpc": parse_float(data.get("cpc")),
            "cpm": parse_float(data.get("cpm")),
            "frequency": parse_float(data.get("frequency")),
        }
        entry["cpr"] = round(entry["spend"] / entry["results"], 2) if entry["results"] else 0.0
        out[label] = entry
        total_spend += entry["spend"]
    for entry in out.values():
        entry["pct"] = round(entry["spend"] / total_spend * 100, 1) if total_spend else 0.0
    return out


def _fetch_platform_conversions(
    access_token: str, api_version: str, ad_account_id: str, month: str
) -> dict[str, dict]:
    """Per-publisher-platform conversions (actions + cost per action type)."""
    since, until = month_range(month)
    rows = _get_insights(
        access_token,
        api_version,
        ad_account_id,
        ["actions", "cost_per_action_type"],
        {
            "level": "account",
            "time_range": {"since": since, "until": until},
            "breakdowns": ["publisher_platform"],
            "use_unified_attribution_setting": True,
        },
    )
    platforms: dict[str, dict] = {}
    for data in rows:
        platform = str(data.get("publisher_platform", "") or "").lower()
        if not platform:
            continue
        cost_by_type: dict[str, float] = {}
        for item in data.get("cost_per_action_type") or []:
            at = str(item.get("action_type", ""))
            if at:
                cost_by_type[at] = parse_float(item.get("value"))
        actions: dict[str, dict] = {}
        for item in data.get("actions") or []:
            at = str(item.get("action_type", ""))
            count = parse_float(item.get("value"))
            if not at or count <= 0:
                continue
            entry = actions.setdefault(at, {"count": 0.0, "cost": 0.0, "cpa": 0.0})
            entry["count"] += count
            entry["cost"] += cost_by_type.get(at, 0.0)
        for at, entry in actions.items():
            entry["cpa"] = round(entry["cost"] / entry["count"], 2) if entry["count"] else 0.0
            entry["count"] = int(round(entry["count"]))
            entry["cost"] = round(entry["cost"], 2)
        platforms[platform] = {"actions": actions, "total": sum(v["count"] for v in actions.values())}
    return platforms


def _fetch_prev_month(access_token: str, api_version: str, ad_account_id: str, month: str) -> dict:
    prev = prev_month_str(month)
    summary = fetch_campaign_insights(access_token, api_version, ad_account_id, prev)
    totals = _compute_totals_from_campaigns(summary.campaigns)
    platforms: dict[str, dict] = {}
    try:
        platforms = _fetch_platform_metrics(access_token, api_version, ad_account_id, prev)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta previous-month platform metrics failed for %s %s: %s", ad_account_id, prev, exc)
    return {
        "month": prev,
        "totals": totals,
        "platforms": platforms,
        "campaigns": [
            {
                "campaign_id": c.campaign_id,
                "campaign_name": c.campaign_name,
                "spend": c.spend,
                "results": c.results,
                "impressions": c.impressions,
                "reach": c.reach,
                "ctr": c.ctr,
                "cpr": c.cost_per_result or (round(c.spend / c.results, 2) if c.results else 0.0),
            }
            for c in summary.campaigns
        ],
    }


def _compute_totals_from_campaigns(campaigns: list[CampaignRow]) -> dict[str, float]:
    spend = sum(c.spend for c in campaigns)
    impressions = sum(c.impressions for c in campaigns)
    reach = sum(c.reach for c in campaigns)
    results = sum(c.results for c in campaigns)
    clicks = sum(c.clicks for c in campaigns)
    return {
        "spend": round(spend, 2),
        "impressions": impressions,
        "reach": reach,
        "results": results,
        "clicks": clicks,
        "ctr": round(clicks / impressions * 100, 2) if impressions else 0.0,
        "cpc": round(spend / clicks, 2) if clicks else 0.0,
        "cpm": round(spend / impressions * 1000, 2) if impressions else 0.0,
        "cpr": round(spend / results, 2) if results else 0.0,
        "frequency": round(impressions / reach, 2) if reach else 0.0,
    }


def _compute_totals(dataset: MetaAdsDataset) -> dict[str, float]:
    return _compute_totals_from_campaigns(dataset.campaigns)


def fetch_meta_dataset(access_token: str, api_version: str, ad_account_id: str, month: str) -> MetaAdsDataset:
    """Fetch the full monthly Meta dataset with graceful degradation.

    Every optional fetch is wrapped so a single unsupported breakdown (or any
    transient API error) is logged and skipped without failing the report.
    """
    dataset = MetaAdsDataset(account_id=ad_account_id, month=month, currency="EGP")

    try:
        summary = fetch_campaign_insights(access_token, api_version, ad_account_id, month)
        dataset.campaigns = summary.campaigns
        dataset.currency = summary.currency
    except Exception as exc:  # noqa: BLE001
        log.warning("meta campaign insights failed for %s %s: %s", ad_account_id, month, exc)
        return dataset

    if not dataset.campaigns:
        return dataset

    try:
        _attach_statuses(access_token, api_version, ad_account_id, dataset.campaigns)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta campaign statuses failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.adsets = _fetch_adsets(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta adset insights failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.conversions = _fetch_conversions(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta conversion breakdown failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.devices = _fetch_breakdown(access_token, api_version, ad_account_id, month, "device_platform")
    except Exception as exc:  # noqa: BLE001
        log.warning("meta device breakdown failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.publishers = _fetch_breakdown(access_token, api_version, ad_account_id, month, "publisher_platform")
    except Exception as exc:  # noqa: BLE001
        log.warning("meta publisher breakdown failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.countries = _fetch_countries(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta country breakdown failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.demographics = _fetch_demographics(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta demographics breakdown failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.dow_pacing, dataset.hour_pacing = _fetch_hourly_pacing(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta hourly pacing failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.daily_spend = _fetch_daily_spend(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta daily spend failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.account_totals = _fetch_account_totals(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta account totals failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.platforms = _fetch_platform_metrics(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta platform metrics failed for %s %s: %s", ad_account_id, month, exc)

    try:
        dataset.platform_conversions = _fetch_platform_conversions(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta platform conversions failed for %s %s: %s", ad_account_id, month, exc)

    # Additive metrics (spend, results, impressions, clicks) come from campaign
    # sums — they are reliable across mixed-objective accounts. Reach and
    # frequency are NOT additive (people can see multiple campaigns), so we
    # take the deduplicated account-level values when available.
    dataset.totals = _compute_totals(dataset)
    if dataset.account_totals:
        at = dataset.account_totals
        dataset.totals["reach"] = int(at.get("reach") or 0)
        dataset.totals["frequency"] = round(dataset.totals["impressions"] / dataset.totals["reach"], 2) if dataset.totals["reach"] else 0.0

    try:
        dataset.prev_month = _fetch_prev_month(access_token, api_version, ad_account_id, month)
    except Exception as exc:  # noqa: BLE001
        log.warning("meta previous-month fetch failed for %s %s: %s", ad_account_id, month, exc)

    return dataset
