"""Insights engine: turns a fetched Meta dataset + manual inputs + client config
into narrative, KPIs, rankings, anomalies, recommendations, pacing and MoM.

Pure deterministic code — no LLM. Every derived computation is guarded against
division by zero / missing keys so the engine never crashes on partial data.
"""

from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from tds_ads_reporting.config import Client
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.meta.ads import CampaignRow, MetaAdsDataset, month_label

# ---------------------------------------------------------------------------
# Safe math helpers
# ---------------------------------------------------------------------------


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _pct(part: float, whole: float) -> float:
    return round(part / whole * 100, 1) if whole else 0.0


def _delta_pct(current: float, previous: float) -> float | None:
    if previous is None or previous == 0:
        return None
    return round((current - previous) / previous * 100, 1)


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def _fmt_num(value: float) -> str:
    return f"{int(value):,}"


def _campaign_metrics(c: CampaignRow) -> dict[str, Any]:
    return {
        "name": c.campaign_name,
        "campaign_id": c.campaign_id,
        "objective": c.objective,
        "status": c.status,
        "spend": round(c.spend, 2),
        "results": c.results,
        "cpr": round(c.cost_per_result or _safe_div(c.spend, c.results), 2),
        "ctr": c.ctr,
        "cpc": c.cpc,
        "cpm": c.cpm,
        "frequency": c.frequency,
        "impressions": c.impressions,
        "reach": c.reach,
        "clicks": c.clicks,
    }


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_insights(
    dataset: MetaAdsDataset,
    manual: ManualInputs,
    client: Client,
    currency: str = "EGP",
    today: date | None = None,
) -> dict[str, Any]:
    """Produce the full insights payload for the report template."""
    totals = dataset.totals or {}
    spend = float(totals.get("spend", 0.0))
    results = int(totals.get("results", 0))
    impressions = int(totals.get("impressions", 0))
    reach = int(totals.get("reach", 0))
    clicks = int(totals.get("clicks", 0))
    ctr = float(totals.get("ctr", 0.0))
    cpc = float(totals.get("cpc", 0.0))
    cpm = float(totals.get("cpm", 0.0))
    cpr = float(totals.get("cpr", 0.0))
    frequency = float(totals.get("frequency", 0.0))

    campaigns = list(dataset.campaigns)

    # ---- budget / revenue -------------------------------------------------
    budget_amount = float(manual.budget.get("amount") or 0.0)
    budget_spent = float(manual.budget.get("spent") or spend)
    revenue = manual.budget.get("revenue") or manual.revenue
    revenue = float(revenue) if revenue else None
    budget_utilization = _pct(spend, budget_amount)
    roas = round(revenue / spend, 2) if revenue and spend else None

    # ---- primary action CPA ----------------------------------------------
    primary_goal = str(client.goals.get("primary") or "conversion")
    action_types = list((client.meta.conversion_actions or {}).get(primary_goal) or [])
    primary_action: str | None = None
    cpa_primary: float | None = None
    if action_types:
        best = None
        for at in action_types:
            conv = dataset.conversions.get(at)
            if conv and conv.get("count"):
                if best is None or conv["count"] > best["count"]:
                    best = conv
                    primary_action = at
        if best:
            cpa_primary = float(best.get("cpa") or 0.0) or None

    kpis: dict[str, Any] = {
        "spend": spend,
        "spend_fmt": _fmt_money(spend, currency),
        "results": results,
        "results_fmt": _fmt_num(results),
        "impressions": impressions,
        "impressions_fmt": _fmt_num(impressions),
        "reach": reach,
        "reach_fmt": _fmt_num(reach),
        "clicks": clicks,
        "clicks_fmt": _fmt_num(clicks),
        "ctr": ctr,
        "cpc": cpc,
        "cpm": cpm,
        "cpr": cpr,
        "cpr_fmt": _fmt_money(cpr, currency),
        "frequency": frequency,
        "cpa_primary": cpa_primary,
        "cpa_primary_fmt": _fmt_money(cpa_primary, currency) if cpa_primary is not None else None,
        "primary_action": primary_action,
        "primary_goal": primary_goal,
        "roas": roas,
        "roas_fmt": f"{roas:.2f}x" if roas is not None else None,
        "budget_amount": budget_amount,
        "budget_amount_fmt": _fmt_money(budget_amount, currency),
        "budget_spent": budget_spent,
        "budget_spent_fmt": _fmt_money(budget_spent, currency),
        "budget_utilization": budget_utilization,
        "budget_remaining": round(budget_amount - spend, 2),
        "budget_remaining_fmt": _fmt_money(budget_amount - spend, currency),
    }

    # ---- top / bottom campaigns ------------------------------------------
    ranked = sorted(campaigns, key=lambda c: (c.results, c.spend), reverse=True)
    top_campaigns = [_campaign_metrics(c) for c in ranked[:5]]
    for i, entry in enumerate(top_campaigns):
        entry["why"] = _why(entry, ranked)

    bottom_campaigns = [_campaign_metrics(c) for c in ranked[-5:][::-1]]
    for entry in bottom_campaigns:
        entry["flags"] = _weakness_flags(entry, cpr)

    # ---- MoM --------------------------------------------------------------
    prev_totals = (dataset.prev_month or {}).get("totals") or {}
    mom: dict[str, Any] = {}
    for key in ("spend", "results", "impressions", "reach", "ctr", "cpc", "cpm", "cpr"):
        cur = totals.get(key, 0.0)
        prev = prev_totals.get(key)
        mom[key] = {
            "current": cur,
            "previous": prev,
            "delta_pct": _delta_pct(float(cur), float(prev)) if prev is not None else None,
        }
    prev_campaigns = {(pc.get("campaign_id") or ""): pc for pc in (dataset.prev_month or {}).get("campaigns") or []}
    mom["campaigns"] = {
        c.campaign_id: {
            "spend_prev": float(prev_campaigns.get(c.campaign_id, {}).get("spend") or 0.0),
            "spend_delta_pct": _delta_pct(c.spend, float(prev_campaigns.get(c.campaign_id, {}).get("spend") or 0.0)),
        }
        for c in campaigns
        if c.campaign_id in prev_campaigns
    }

    # ---- pacing -----------------------------------------------------------
    pacing = _build_pacing(dataset, manual, spend, budget_amount, budget_utilization, today)

    # ---- anomalies + recommendations -------------------------------------
    anomalies = _build_anomalies(dataset, totals, campaigns, mom, budget_amount, budget_utilization, currency)
    recommendations = _build_recommendations(
        dataset, campaigns, top_campaigns, bottom_campaigns, anomalies, budget_utilization, cpr, currency
    )

    # ---- executive summary ------------------------------------------------
    executive_summary = _executive_summary(
        client=client,
        month=dataset.month,
        spend=spend,
        impressions=impressions,
        results=results,
        cpr=cpr,
        budget_amount=budget_amount,
        budget_utilization=budget_utilization,
        mom=mom,
        top=top_campaigns[0] if top_campaigns else None,
        recommendation=recommendations[0] if recommendations else None,
        currency=currency,
    )

    return {
        "executive_summary": executive_summary,
        "kpis": kpis,
        "top_campaigns": top_campaigns,
        "bottom_campaigns": bottom_campaigns,
        "anomalies": anomalies,
        "recommendations": recommendations,
        "pacing": pacing,
        "mom": mom,
        "prev_month_label": month_label((dataset.prev_month or {}).get("month") or "") if dataset.prev_month else None,
    }


# ---------------------------------------------------------------------------
# Rankings
# ---------------------------------------------------------------------------


def _why(entry: dict[str, Any], ranked: list[CampaignRow]) -> str:
    if entry["results"] == 0:
        return "highest spend (no results)"
    with_results = [c for c in ranked if c.results > 0]
    if with_results:
        min_cpr = min(c.cost_per_result or _safe_div(c.spend, c.results) for c in with_results)
        if entry["cpr"] == round(min_cpr, 2):
            return "lowest cost-per-result"
    if entry["results"] == max((c.results for c in ranked), default=0):
        return "highest results"
    if entry["ctr"] and entry["ctr"] == max((c.ctr for c in ranked), default=0):
        return "best click-through rate"
    return "top performer"


def _weakness_flags(entry: dict[str, Any], overall_cpr: float) -> list[str]:
    flags: list[str] = []
    if entry["results"] == 0 and entry["spend"] > 0:
        flags.append("zero results")
    if entry["frequency"] and entry["frequency"] > 4.0:
        flags.append("high frequency")
    if entry["cpr"] and overall_cpr and entry["cpr"] > overall_cpr * 2:
        flags.append("above-average cost")
    return flags


# ---------------------------------------------------------------------------
# Pacing
# ---------------------------------------------------------------------------


def _build_pacing(
    dataset: MetaAdsDataset,
    manual: ManualInputs,
    spend: float,
    budget_amount: float,
    budget_utilization: float,
    today: date | None,
) -> dict[str, Any]:
    year, mon = (int(x) for x in dataset.month.split("-"))
    days_in_month = calendar.monthrange(year, mon)[1]
    today = today or date.today()
    if dataset.month == today.strftime("%Y-%m"):
        days_elapsed = today.day
    else:
        days_elapsed = days_in_month
    daily_avg = _safe_div(spend, days_elapsed)
    projected = round(daily_avg * days_in_month, 2)

    spike_days: list[dict[str, Any]] = []
    if daily_avg > 0:
        for day in dataset.daily_spend or []:
            if float(day.get("spend") or 0.0) > daily_avg * 1.5:
                spike_days.append({"date": day.get("date", ""), "spend": round(float(day.get("spend") or 0.0), 2)})
        spike_days.sort(key=lambda d: d["spend"], reverse=True)
        spike_days = spike_days[:5]

    return {
        "budget_amount": budget_amount,
        "spend": spend,
        "utilization": budget_utilization,
        "remaining": round(budget_amount - spend, 2),
        "days_elapsed": days_elapsed,
        "days_in_month": days_in_month,
        "daily_avg": round(daily_avg, 2),
        "projected": projected,
        "spike_days": spike_days,
    }


# ---------------------------------------------------------------------------
# Anomalies
# ---------------------------------------------------------------------------


def _build_anomalies(
    dataset: MetaAdsDataset,
    totals: dict[str, Any],
    campaigns: list[CampaignRow],
    mom: dict[str, Any],
    budget_amount: float,
    budget_utilization: float,
    currency: str,
) -> list[str]:
    out: list[str] = []
    spend = float(totals.get("spend", 0.0))
    impressions = int(totals.get("impressions", 0))
    clicks = int(totals.get("clicks", 0))

    # Publisher concentration
    for pub in dataset.publishers or []:
        share = _pct(float(pub.get("impressions") or 0), impressions)
        if share >= 50:
            out.append(f"{pub['label']} delivers {share:.0f}% of impressions")
            break

    # Device concentration (clicks)
    for dev in dataset.devices or []:
        share = _pct(float(dev.get("clicks") or 0), clicks)
        if share >= 70:
            out.append(f"{dev['label']} drives {share:.0f}% of clicks")
            break

    # Campaign spend vs results imbalance
    for c in campaigns:
        spend_share = _pct(c.spend, spend)
        results_share = _pct(c.results, int(totals.get("results", 0)))
        if spend_share >= 35 and results_share <= 12:
            out.append(f"{c.campaign_name} spent {spend_share:.0f}% of budget for {results_share:.0f}% of results")

    # MoM spend swing
    spend_mom = mom.get("spend", {}).get("delta_pct")
    if spend_mom is not None and abs(spend_mom) > 30:
        direction = "up" if spend_mom > 0 else "down"
        out.append(f"Spend moved {direction} {abs(spend_mom):.0f}% vs the previous month")

    # High frequency
    for c in campaigns:
        if c.frequency and c.frequency > 4.0:
            out.append(f"{c.campaign_name} ran at frequency {c.frequency:.1f} (above 4.0)")

    # Zero-results spend
    for c in campaigns:
        if c.results == 0 and c.spend > 0:
            out.append(f"{c.campaign_name} spent {_fmt_money(c.spend, currency)} with no results")

    # Budget over/under
    if budget_amount and budget_utilization > 100:
        out.append(f"Spend exceeded the monthly budget by {budget_utilization - 100:.0f}%")
    elif budget_amount and budget_utilization < 10:
        out.append(f"Only {budget_utilization:.0f}% of the monthly budget was used")

    # Hour concentration
    peak_hour = max((dataset.hour_pacing or {}).items(), key=lambda kv: kv[1].get("pct", 0), default=None)
    if peak_hour and peak_hour[1].get("pct", 0) >= 15:
        out.append(f"Spend concentrates at hour {peak_hour[0]} ({peak_hour[1]['pct']:.0f}% of spend)")

    # Country concentration
    if dataset.countries:
        top = dataset.countries[0]
        if top.get("pct", 0) >= 50:
            out.append(f"{top['label']} accounts for {top['pct']:.0f}% of spend")

    return out


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------


def _build_recommendations(
    dataset: MetaAdsDataset,
    campaigns: list[CampaignRow],
    top_campaigns: list[dict[str, Any]],
    bottom_campaigns: list[dict[str, Any]],
    anomalies: list[str],
    budget_utilization: float,
    overall_cpr: float,
    currency: str,
) -> list[str]:
    out: list[str] = []
    spend = float((dataset.totals or {}).get("spend", 0.0))

    # Scale the best campaign
    if top_campaigns:
        top = top_campaigns[0]
        if top["results"] > 0 and overall_cpr and top["cpr"] and top["cpr"] < overall_cpr:
            out.append(
                f"Scale budget for '{top['name']}' — it converts at {_fmt_money(top['cpr'], currency)} per result "
                f"vs the account average of {_fmt_money(overall_cpr, currency)}"
            )

    # Pause zero-result spenders
    for c in campaigns:
        if c.results == 0 and c.spend > 0:
            out.append(f"Pause '{c.campaign_name}' — it spent {_fmt_money(c.spend, currency)} with no results")

    # Lower frequency
    for c in campaigns:
        if c.frequency and c.frequency > 4.0:
            out.append(f"Refresh creative in '{c.campaign_name}' to reduce frequency ({c.frequency:.1f})")

    # Publisher shift
    if dataset.publishers and len(dataset.publishers) > 1:
        top_pub = dataset.publishers[0]
        bottom_pub = dataset.publishers[-1]
        if top_pub.get("pct", 0) > bottom_pub.get("pct", 0) + 20:
            out.append(
                f"Shift budget toward {top_pub['label']} ({top_pub['pct']:.0f}% of spend) and away from "
                f"{bottom_pub['label']} ({bottom_pub['pct']:.0f}%)"
            )

    # Demographic winner
    if dataset.demographics:
        top_demo = dataset.demographics[0]
        out.append(
            f"Test audience segment {top_demo['age']} / {top_demo['gender']} "
            f"({top_demo['pct']:.0f}% of spend)"
        )

    # Country opportunity
    if dataset.countries:
        top_country = dataset.countries[0]
        out.append(
            f"Expand geo targeting toward {top_country['label']} ({top_country['pct']:.0f}% of spend)"
        )

    # Budget pacing
    if budget_utilization < 50:
        out.append(f"Increase spend to reach the monthly budget — only {budget_utilization:.0f}% utilized")
    elif budget_utilization > 100:
        out.append(f"Review the monthly budget — spend exceeded it by {budget_utilization - 100:.0f}%")

    # Adset scaling
    if dataset.adsets:
        top_adset = dataset.adsets[0]
        if top_adset.get("results", 0) > 0:
            out.append(
                f"Duplicate or scale adset '{top_adset['adset_name']}' "
                f"({top_adset['results']} results at {_fmt_money(top_adset.get('cost_per_result') or 0, currency)} each)"
            )

    return out[:8]


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------


def _executive_summary(
    client: Client,
    month: str,
    spend: float,
    impressions: int,
    results: int,
    cpr: float,
    budget_amount: float,
    budget_utilization: float,
    mom: dict[str, Any],
    top: dict[str, Any] | None,
    recommendation: str | None,
    currency: str,
) -> str:
    sentences: list[str] = []
    sentences.append(
        f"In {month_label(month)}, {client.name} invested {_fmt_money(spend, currency)} across Meta, "
        f"generating {_fmt_num(results)} results from {_fmt_num(impressions)} impressions."
    )
    if top:
        sentences.append(
            f"'{top['name']}' led performance with {_fmt_num(top['results'])} results "
            f"at {_fmt_money(top['cpr'], currency)} per result."
        )
    if budget_amount:
        sentences.append(
            f"Spend reached {budget_utilization:.0f}% of the {_fmt_money(budget_amount, currency)} monthly budget."
        )
    spend_mom = mom.get("spend", {}).get("delta_pct")
    results_mom = mom.get("results", {}).get("delta_pct")
    if spend_mom is not None or results_mom is not None:
        bits = []
        if spend_mom is not None:
            bits.append(f"spend {'rose' if spend_mom >= 0 else 'fell'} {abs(spend_mom):.0f}%")
        if results_mom is not None:
            bits.append(f"results {'rose' if results_mom >= 0 else 'fell'} {abs(results_mom):.0f}%")
        sentences.append(f"Compared with the previous month, {' and '.join(bits)}.")
    else:
        sentences.append("No previous-month data was available for comparison.")
    if recommendation:
        sentences.append(f"Priority action: {recommendation}.")
    return " ".join(sentences)