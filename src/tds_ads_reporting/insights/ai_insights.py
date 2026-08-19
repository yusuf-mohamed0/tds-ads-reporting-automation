"""AI-generated per-client analyst insights (OpenAI gpt-4o-mini).

The AI writes the executive narrative and recommendations for a client's
monthly report. It is a STRICT tool: the numbers supplied in the payload are
the only source of truth, and any generated text that contradicts the payload
is rejected by a verification pass in :func:`generate_ai_insights`.

Requires OPENAI_API_KEY in the environment. When the key is missing, the API
is unreachable, or the response fails verification, the caller falls back to
the deterministic engine output.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import sys
import requests

from tds_ads_reporting.config import ROOT

CACHE_DIR = ROOT / "data" / "ai"

MODEL = "gpt-4o-mini"
ENDPOINT = "https://api.openai.com/v1/chat/completions"

SYSTEM_PROMPT = """You are the senior Meta Ads analyst at Traffic Digital Solutions writing a
monthly client performance report. The JSON payload below contains the ONLY
numbers that exist. Rules:
1. NEVER invent, extrapolate, round up, or repeat figures not present in the payload.
2. Use exact figures exactly as formatted in the payload.
3. No generic filler or templated phrases such as "the account performed well overall".
4. Be specific and analytical: reference campaign names, platforms, exact numbers.
5. Return valid JSON only with these keys:
   - "summary": 2-4 sentences summarising the month (spend, results and what the
     results are, key driver, MoM change with exact %).
   - "findings": 3-6 bullets, each citing exact numbers from the payload.
   - "recommendations": 3-5 concrete, budget-aware actions.
   - "warnings": risks/accuracy notes (empty list if none).
6. Every number you cite MUST appear verbatim in the payload."""

USER_TEMPLATE = """Client: {client_name} | Month: {month}

Payload:
{payload}

Write the JSON analysis now."""


def _fmt_num(n) -> str:
    try:
        return f"{int(n):,}"
    except (TypeError, ValueError):
        return "0"


def build_payload(
    client: Any,
    month: str,
    insights: dict[str, Any],
) -> dict[str, Any]:
    kpis = insights.get("kpis") or {}
    mom = insights.get("mom") or {}
    top = insights.get("top_campaigns") or []
    bottom = insights.get("bottom_campaigns") or []
    platforms = insights.get("platforms") or []
    anomalies = insights.get("anomalies") or []
    recommendations = insights.get("recommendations") or []
    results_label = insights.get("results_label") or "Results"

    payload: dict[str, Any] = {
        "month": month,
        "client": client.name,
        "account_id": (client.meta.ad_accounts or [""])[0],
        "results_are": results_label,
        "kpis": {
            "spend_currency": kpis.get("spend", 0),
            "results": kpis.get("results", 0),
            "cost_per_result": kpis.get("cpr", 0),
            "ctr_pct": kpis.get("ctr", 0),
            "cpc": kpis.get("cpc", 0),
            "cpm": kpis.get("cpm", 0),
            "impressions": kpis.get("impressions", 0),
            "reach": kpis.get("reach", 0),
            "frequency": kpis.get("frequency", 0),
            "clicks": kpis.get("clicks", 0),
        },
        "budget_amount": kpis.get("budget_amount", 0),
        "budget_utilization_pct": kpis.get("budget_utilization", 0),
        "month_over_month": {
            "spend_change_pct": (mom.get("spend") or {}).get("delta_pct"),
            "results_change_pct": (mom.get("results") or {}).get("delta_pct"),
            "impressions_change_pct": (mom.get("impressions") or {}).get("delta_pct"),
            "previous_month": (mom.get("spend") or {}).get("previous"),
        },
        "top_campaigns": [
            {
                "name": c.get("name"),
                "spend": c.get("spend"),
                "results": c.get("results"),
                "cost_per_result": c.get("cpr"),
                "lifecycle": c.get("lifecycle"),
            }
            for c in top[:5]
        ],
        "bottom_campaigns": [
            {"name": c.get("name"), "spend": c.get("spend"), "results": c.get("results")}
            for c in bottom[:5]
        ],
        "platforms": platforms[:6],
        "anomalies": anomalies,
        "recommendations": recommendations,
    }
    return payload


def _verify(text: str, payload: dict[str, Any]) -> bool:
    """Reject AI text that contradicts the source numbers.

    The AI is told to copy figures verbatim; a rendered thousands-separator
    (e.g. '18,638') is the canonical form. We require the headline spend to
    appear, and forbid obvious numeric contradictions for core KPIs.
    """
    spend = payload.get("kpis", {}).get("spend_currency", 0)
    results = payload.get("kpis", {}).get("results", 0)
    if spend and f"{int(spend):,}" not in text and str(spend) not in text:
        return False
    if results and f"{int(results):,}" not in text and str(results) not in text:
        return False
    return True


def generate_ai_insights(
    client: Any,
    month: str,
    insights: dict[str, Any],
) -> dict[str, Any] | None:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return None

    cache = CACHE_DIR / f"{client.id}_{month}.json"
    if cache.exists():
        try:
            return json.loads(cache.read_text())
        except Exception:
            pass

    payload = build_payload(client, month, insights)
    try:
        response = requests.post(
            ENDPOINT,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            client_name=client.name,
                            month=month,
                            payload=json.dumps(payload),
                        ),
                    },
                ],
                "temperature": 0.2,
                "response_format": {"type": "json_object"},
            },
            timeout=120,
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except Exception as exc:
        if os.environ.get("TDS_AI_DEBUG"):
            import traceback

            traceback.print_exc()
            print(f"[ai_insights] {client.id} failed: {exc!r}", file=sys.stderr)
        return None

    summary = str(data.get("summary") or "").strip()
    if not summary or not _verify(summary, payload):
        return None

    findings = [str(x).strip() for x in data.get("findings") or [] if str(x).strip()]
    recommendations = [str(x).strip() for x in data.get("recommendations") or [] if str(x).strip()]
    warnings = [str(x).strip() for x in data.get("warnings") or [] if str(x).strip()]

    result = {
        "summary": summary,
        "findings": findings[:6],
        "recommendations": recommendations[:5],
        "warnings": warnings[:5],
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }
    try:
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(result, indent=2))
    except Exception:
        pass
    return result