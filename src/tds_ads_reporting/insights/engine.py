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
    if value and abs(value) < 1:
        return f"{value:,.2f} {currency}"
    return f"{value:,.0f} {currency}"


def _fmt_num(value: float) -> str:
    return f"{int(value):,}"


def _campaign_metrics(c: CampaignRow) -> dict[str, Any]:
    return {
        "name": c.campaign_name,
        "campaign_id": c.campaign_id,
        "objective": c.objective,
        "status": c.status,
        "effective_status": c.effective_status,
        "start_time": c.start_time,
        "stop_time": c.stop_time,
        "lifecycle": c.lifecycle if getattr(c, "lifecycle", None) else "",
        "results_label": c.results_label if getattr(c, "results_label", None) else "Results",
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


def campaign_lifecycle(c: CampaignRow, month: str) -> str:
    """Classify how a campaign relates to the reported month.

    - 'new': started within the month
    - 'ended': stopped within the month
    - 'carried-over': started before the month and still running at month end
      (an old campaign that keeps running — its results are included)
    - 'active': ran during the month with no explicit start/stop dates
    - 'inactive': no spend recorded for the month
    """
    if not c.spend and not c.impressions:
        return "inactive"
    y, m = (int(x) for x in month.split("-"))
    month_start = date(y, m, 1)
    month_end = date(y, m, calendar.monthrange(y, m)[1])
    try:
        start = date.fromisoformat((c.start_time or "")[:10])
    except ValueError:
        start = None
    try:
        stop = date.fromisoformat((c.stop_time or "")[:10])
    except ValueError:
        stop = None
    if start is not None and month_start <= start <= month_end:
        return "new"
    if stop is not None and month_start <= stop <= month_end:
        return "ended"
    if start is not None and start < month_start:
        if stop is None or stop > month_end:
            return "carried-over"
        return "active"
    return "active"


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
    for c in campaigns:
        c.lifecycle = campaign_lifecycle(c, dataset.month)

    # ---- platform split (Facebook vs Instagram) ---------------------------
    platform_rows: list[dict[str, Any]] = []
    prev_platforms = (dataset.prev_month or {}).get("platforms") or {}
    fb_map = {"facebook": "Facebook", "instagram": "Instagram", "messenger": "Messenger", "audience_network": "Audience Network"}
    for platform_key, label in fb_map.items():
        data = (dataset.platforms or {}).get(platform_key)
        if not data:
            continue
        prev = prev_platforms.get(platform_key) or {}
        row: dict[str, Any] = {
            "platform": platform_key,
            "label": label,
            "spend": float(data.get("spend") or 0.0),
            "spend_fmt": _fmt_money(float(data.get("spend") or 0.0), currency),
            "results": int(data.get("results") or 0),
            "results_fmt": _fmt_num(int(data.get("results") or 0)),
            "impressions": int(data.get("impressions") or 0),
            "reach": int(data.get("reach") or 0),
            "clicks": int(data.get("clicks") or 0),
            "ctr": float(data.get("ctr") or 0.0),
            "cpc": float(data.get("cpc") or 0.0),
            "cpm": float(data.get("cpm") or 0.0),
            "cpr": float(data.get("cpr") or 0.0),
            "frequency": float(data.get("frequency") or 0.0),
            "share_pct": float(data.get("pct") or 0.0),
            "mom_spend_pct": _delta_pct(float(data.get("spend") or 0.0), float(prev.get("spend") or 0.0)),
            "mom_results_pct": _delta_pct(float(data.get("results") or 0.0), float(prev.get("results") or 0.0)),
            "mom_cpr_pct": _delta_pct(float(data.get("cpr") or 0.0), float(prev.get("cpr") or 0.0)),
            "mom_impressions_pct": _delta_pct(float(data.get("impressions") or 0.0), float(prev.get("impressions") or 0.0)),
            "prev_spend": float(prev.get("spend") or 0.0),
            "prev_results": int(prev.get("results") or 0),
        }
        platform_conv = (dataset.platform_conversions or {}).get(platform_key) or {}
        row["conversions_total"] = int(platform_conv.get("total") or 0)
        row["conversions"] = platform_conv.get("actions") or {}
        platform_rows.append(row)

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
    campaign_metrics = [_campaign_metrics(c) for c in ranked]
    top_campaigns = campaign_metrics[:5]
    for i, entry in enumerate(top_campaigns):
        entry["why"] = _why(entry, ranked)

    bottom_campaigns = campaign_metrics[-5:][::-1]
    for entry in bottom_campaigns:
        entry["flags"] = _weakness_flags(entry, cpr)

    # ---- MoM --------------------------------------------------------------
    prev_totals = (dataset.prev_month or {}).get("totals") or {}
    mom: dict[str, Any] = {}
    prev_label = month_label((dataset.prev_month or {}).get("month") or "") if dataset.prev_month else ""
    mom["prev_label"] = prev_label
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
            "name": c.campaign_name,
            "lifecycle": c.lifecycle,
            "spend_prev": float(prev_campaigns.get(c.campaign_id, {}).get("spend") or 0.0),
            "spend_delta_pct": _delta_pct(c.spend, float(prev_campaigns.get(c.campaign_id, {}).get("spend") or 0.0)),
            "results_prev": int(prev_campaigns.get(c.campaign_id, {}).get("results") or 0),
            "results_delta_pct": _delta_pct(c.results, float(prev_campaigns.get(c.campaign_id, {}).get("results") or 0)),
            "impressions_prev": int(prev_campaigns.get(c.campaign_id, {}).get("impressions") or 0),
            "impressions_delta_pct": _delta_pct(c.impressions, float(prev_campaigns.get(c.campaign_id, {}).get("impressions") or 0)),
            "cpr_prev": float(prev_campaigns.get(c.campaign_id, {}).get("cpr") or 0.0),
            "cpr_delta_pct": _delta_pct(c.cost_per_result or _safe_div(c.spend, c.results), float(prev_campaigns.get(c.campaign_id, {}).get("cpr") or 0.0)),
            "ctr_prev": float(prev_campaigns.get(c.campaign_id, {}).get("ctr") or 0.0),
            "ctr_delta_pct": _delta_pct(c.ctr, float(prev_campaigns.get(c.campaign_id, {}).get("ctr") or 0.0)),
        }
        for c in campaigns
    }

    # Campaign continuity: old campaigns still running + new/stopped ones.
    prev_ids = set(prev_campaigns)
    cur_ids = {c.campaign_id for c in campaigns}
    mom["new_campaigns"] = [
        {"campaign_id": c.campaign_id, "name": c.campaign_name, "spend": c.spend, "results": c.results}
        for c in campaigns if c.campaign_id not in prev_ids
    ]
    mom["stopped_campaigns"] = [
        {
            "campaign_id": pid,
            "name": pc.get("campaign_name") or pid,
            "spend": float(pc.get("spend") or 0.0),
            "results": int(pc.get("results") or 0),
        }
        for pid, pc in prev_campaigns.items() if pid not in cur_ids
    ]
    mom["carried_over"] = [
        {"campaign_id": c.campaign_id, "name": c.campaign_name, "spend": c.spend, "results": c.results}
        for c in campaigns if c.lifecycle == "carried-over"
    ]

    # ---- data quality: results vs primary conversion action --------------
    data_quality: list[str] = []
    for c in campaigns:
        if not c.results or c.spend <= 0:
            continue
        if c.objective and "lead" in c.objective.lower():
            lead_actions = [at for at in ("onsite_conversion.lead", "lead", "leadgen_grouped") if at in dataset.conversions]
            if lead_actions:
                lead_count = sum(int(dataset.conversions[at].get("count") or 0) for at in lead_actions)
                if lead_count and abs(lead_count - c.results) > max(1, c.results * 0.1):
                    data_quality.append(
                        f"'{c.campaign_name}': {c.results} results vs {lead_count} tracked lead actions "
                        "(difference is normal with cross-device/conversion attribution)"
                    )

    # ---- pacing -----------------------------------------------------------
    pacing = _build_pacing(dataset, manual, spend, budget_amount, budget_utilization, today)

    # ---- anomalies + recommendations -------------------------------------
    anomalies = _build_anomalies(dataset, totals, campaigns, mom, budget_amount, budget_utilization, currency)
    recommendations = _build_recommendations(
        dataset, campaigns, top_campaigns, bottom_campaigns, anomalies, budget_utilization, budget_amount, cpr, currency
    )

    # ---- executive summary ------------------------------------------------
    results_label = _dominant_results_label(campaign_metrics)
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
        results_label=results_label,
    )

    payload = {
        "executive_summary": executive_summary,
        "kpis": kpis,
        "top_campaigns": top_campaigns,
        "bottom_campaigns": bottom_campaigns,
        "anomalies": anomalies,
        "recommendations": recommendations,
        "pacing": pacing,
        "mom": mom,
        "platforms": platform_rows,
        "data_quality": data_quality,
        "results_label": results_label,
        "prev_month_label": month_label((dataset.prev_month or {}).get("month") or "") if dataset.prev_month else None,
    }
    from tds_ads_reporting.insights.ai_insights import generate_ai_insights

    ai = generate_ai_insights(client, dataset.month, payload)
    if ai:
        payload["ai"] = ai
        if ai.get("summary"):
            payload["executive_summary"] = ai["summary"]
    return payload


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
    results = int(totals.get("results", 0))
    clicks = int(totals.get("clicks", 0))

# Platform efficiency: share of impressions vs share of results.
    platforms = dataset.platforms or {}
    platform_reported: set[str] = set()
    if len(platforms) > 1:
        for plat in platforms.values():
            imp_share = _pct(float(plat.get("impressions") or 0), impressions)
            plat_results = int(plat.get("results") or 0)
            res_share = _pct(plat_results, results)
            if imp_share >= 50 and res_share < 30 and results > 0:
                out.append(
                    f"{plat['platform'].capitalize()} delivered {imp_share:.0f}% of impressions but only "
                    f"{_fmt_num(plat_results)} of {_fmt_num(results)} results ({res_share:.0f}%)"
                )
                platform_reported.add(plat["platform"].lower())
                break

    # Publisher concentration (impressions) — skip platforms already reported above
    for pub in dataset.publishers or []:
        label = str(pub.get("label") or "").lower()
        share = _pct(float(pub.get("impressions") or 0), impressions)
        if share >= 60 and label not in platform_reported:
            out.append(f"{pub['label']} alone delivered {share:.0f}% of all impressions")
            break

    # Device concentration (clicks)
    for dev in dataset.devices or []:
        share = _pct(float(dev.get("clicks") or 0), clicks)
        if share >= 80:
            out.append(f"{dev['label']} devices drove {share:.0f}% of clicks")
            break

    # Campaign spend vs results imbalance (top offender only, specific)
    offenders = sorted(
        (c for c in campaigns if c.spend > 0),
        key=lambda c: _pct(c.spend, spend) - _pct(c.results, results),
        reverse=True,
    )
    if offenders:
        worst = offenders[0]
        spend_share = _pct(worst.spend, spend)
        res_share = _pct(worst.results, results)
        if spend_share >= 25 and res_share < 15 and results > 0:
            out.append(
                f"'{worst.campaign_name}' consumed {spend_share:.0f}% of the budget for only {res_share:.0f}% of results"
            )

    # MoM spend swing
    spend_mom = mom.get("spend", {}).get("delta_pct")
    if spend_mom is not None and abs(spend_mom) > 30:
        direction = "up" if spend_mom > 0 else "down"
        out.append(f"Ad spend moved {direction} {abs(spend_mom):.0f}% versus {mom.get('prev_label', 'the previous month')}")

    # Zero-result spenders: only the top 2 by spend, specific
    zero_spenders = sorted((c for c in campaigns if c.results == 0 and c.spend > 0), key=lambda c: c.spend, reverse=True)
    for c in zero_spenders[:2]:
        out.append(f"'{c.campaign_name}' spent {_fmt_money(c.spend, currency)} and produced no results")

    # Frequency flag: only the worst offender
    high_freq = [c for c in campaigns if c.frequency and c.frequency > 4.0]
    if high_freq:
        worst_freq = max(high_freq, key=lambda c: c.frequency)
        out.append(f"'{worst_freq.campaign_name}' reached a frequency of {worst_freq.frequency:.1f} (recommended ceiling 4.0)")

    # Budget pacing
    if budget_amount and budget_utilization > 100:
        out.append(f"Spend exceeded the monthly budget by {budget_utilization - 100:.0f}% ({_fmt_money(spend, currency)} vs {_fmt_money(budget_amount, currency)})")
    elif budget_amount and budget_utilization < 10:
        out.append(f"Only {budget_utilization:.0f}% of the monthly budget was used ({_fmt_money(spend, currency)} of {_fmt_money(budget_amount, currency)})")

    # Hour concentration
    peak_hour = max((dataset.hour_pacing or {}).items(), key=lambda kv: kv[1].get("pct", 0), default=None)
    if peak_hour and peak_hour[1].get("pct", 0) >= 20:
        out.append(f"Spend peaks at {peak_hour[0]}:00 ({peak_hour[1]['pct']:.0f}% of daily spend)")

    # Country concentration
    if dataset.countries:
        top = dataset.countries[0]
        if top.get("pct", 0) >= 60:
            out.append(f"{top['label']} accounts for {top['pct']:.0f}% of total spend")

    return out[:8]


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
    budget_amount: float,
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

    # Publisher shift (ignore unknown/other labels)
    if dataset.publishers and len(dataset.publishers) > 1:
        known = [p for p in dataset.publishers if str(p.get("label", "")).lower() not in ("unknown", "other", "")]
        if len(known) >= 2:
            top_pub = known[0]
            bottom_pub = known[-1]
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

    # Adset scaling
    if dataset.adsets:
        top_adset = dataset.adsets[0]
        if top_adset.get("results", 0) > 0:
            out.append(
                f"Duplicate or scale adset '{top_adset['adset_name']}' "
                f"({top_adset['results']} results at {_fmt_money(top_adset.get('cost_per_result') or 0, currency)} each)"
            )

    # Platform efficiency: reallocate between FB and IG based on cost per result
    if dataset.platforms and len(dataset.platforms) > 1:
        ranked = sorted(dataset.platforms.values(), key=lambda x: float(x.get("cpr") or 1e9))
        best = ranked[0]
        worst = ranked[-1]
        best_cpr = float(best.get("cpr") or 0.0)
        worst_cpr = float(worst.get("cpr") or 0.0)
        if best_cpr and worst_cpr and best_cpr > 0 and worst_cpr > best_cpr * 1.5:
            out.append(
                f"{best['platform'].capitalize()} is more efficient (CPR {best_cpr:.2f} vs "
                f"{worst_cpr:.2f} on {worst['platform'].capitalize()}) — shift a tested share of budget "
                f"toward {best['platform'].capitalize()} while watching delivery"
            )

    # Creative fatigue: high frequency with high CPM usually means fatigued creative
    if campaigns:
        fatigued = [c for c in campaigns if (c.frequency or 0) > 4.0]
        if fatigued:
            worst_f = max(fatigued, key=lambda c: c.frequency)
            out.append(
                f"Refresh creative in '{worst_f.campaign_name}' — frequency {worst_f.frequency:.1f} "
                f"with CPM {_fmt_money(worst_f.cpm, currency)} signals audience fatigue"
            )

    # Cost inflation: CPC/CPM rising means the auction got more expensive
    mom_cpm = (dataset.prev_month or {}).get("totals", {}).get("cpm")
    if mom_cpm and dataset.totals and float(mom_cpm) > 0:
        cur_cpm = float(dataset.totals.get("cpm") or 0.0)
        if cur_cpm > float(mom_cpm) * 1.2:
            out.append(
                f"CPM rose to {_fmt_money(cur_cpm, currency)} from {_fmt_money(float(mom_cpm), currency)} — "
                f"audience/creative refresh or broadened targeting will defend efficiency"
            )

    # Zero-results in a lead/message objective is a funnel or offer problem, not delivery
    for c in campaigns:
        if c.results == 0 and c.spend > 0 and c.objective and ("LEAD" in c.objective.upper() or "CONVERS" in c.objective.upper()):
            out.append(
                f"'{c.campaign_name}' is delivering impressions but zero results — before pausing, audit "
                f"the landing page/offer and tracking (pixel events), then relaunch a fresh ad"
            )
            break

    # Under-utilized budget: pacing problem (only when a budget is actually set)
    if budget_amount and budget_utilization < 50:
        out.append(
            f"Increase spend to reach the monthly budget — only {budget_utilization:.0f}% utilized; "
            f"raise bids or add placements/audiences to improve delivery"
        )
    elif budget_amount and budget_utilization > 100:
        out.append(f"Review the monthly budget — spend exceeded it by {budget_utilization - 100:.0f}%")

    return out[:8]


# ---------------------------------------------------------------------------
# Executive summary
# ---------------------------------------------------------------------------


def _dominant_results_label(campaign_metrics: list[dict[str, Any]]) -> str:
    """Weighted dominant 'what the results are' label across campaigns."""
    weights: dict[str, int] = {}
    for cm in campaign_metrics:
        label = cm.get("results_label") or "Results"
        weights[label] = weights.get(label, 0) + int(cm.get("results") or 0)
    if not weights:
        return "Results"
    return max(weights, key=weights.get)


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
    results_label: str = "Results",
) -> str:
    sentences: list[str] = []
    sentences.append(
        f"In {month_label(month)}, {client.name} invested {_fmt_money(spend, currency)} across Meta, "
        f"generating {_fmt_num(results)} {results_label.lower()} from {_fmt_num(impressions)} impressions."
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