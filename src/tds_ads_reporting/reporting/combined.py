from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from tds_ads_reporting.config import Client

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "reports"

DEFAULT_RECIPIENT = "reports@trafficdigitalsolutions.com"


def _safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.0f} {currency}"


def _fmt_num(value: int) -> str:
    return f"{value:,}"


def _month_from_context(ctx: dict[str, Any]) -> str:
    """Derive YYYY-MM from a per-client context (date_start or month_label)."""
    date_start = ctx.get("date_start") or ""
    if len(date_start) >= 7 and date_start[4] == "-":
        return date_start[:7]
    month_label = ctx.get("month_label") or ""
    for i, ch in enumerate(month_label):
        if ch.isdigit():
            return month_label[i : i + 7]
    return ""


def build_combined_context(clients_data: list[tuple[Client, dict[str, Any]]]) -> dict[str, Any]:
    """Roll up per-client report contexts into one combined report context.

    clients_data: list of (client, build_context(...) result) for clients that
    rendered successfully. Failed clients are simply omitted by the caller.
    """
    month = ""
    clients: list[dict[str, Any]] = []
    total_spend = 0.0
    total_results = 0
    total_impressions = 0
    total_clicks = 0
    total_budget_amount = 0.0

    for client, ctx in clients_data:
        if not month:
            month = _month_from_context(ctx)
        kpis = ctx.get("kpis") or {}
        spend = float(kpis.get("spend") or 0.0)
        results = int(kpis.get("results") or 0)
        impressions = int(kpis.get("impressions") or 0)
        clicks = int(kpis.get("clicks") or 0)
        budget_amount = float(kpis.get("budget_amount") or 0.0)

        total_spend += spend
        total_results += results
        total_impressions += impressions
        total_clicks += clicks
        total_budget_amount += budget_amount

        clients.append(
            {
                "client_id": client.id,
                "name": client.name,
                "currency": ctx.get("currency") or client.currency,
                "kpis": kpis,
                "executive_summary": ctx.get("executive_summary") or "",
                "top_campaigns": ctx.get("top_campaigns") or [],
                "recommendations": ctx.get("recommendations") or [],
                "mom": ctx.get("mom") or {},
            }
        )

    currency = clients[0]["currency"] if clients else "EGP"
    ctr = _safe_div(total_clicks * 100.0, total_impressions)
    cpr = _safe_div(total_spend, total_results)
    budget_utilization = _safe_div(total_spend * 100.0, total_budget_amount)

    totals = {
        "spend": round(total_spend, 2),
        "results": total_results,
        "impressions": total_impressions,
        "ctr": round(ctr, 2),
        "cpr": round(cpr, 2),
        "budget_utilization": round(budget_utilization, 1),
        # formatted convenience keys for the template
        "spend_fmt": _fmt_money(total_spend, currency),
        "results_fmt": _fmt_num(total_results),
        "impressions_fmt": _fmt_num(total_impressions),
        "cpr_fmt": _fmt_money(cpr, currency),
    }

    return {
        "month": month,
        "month_label": _month_label(month),
        "generated_at": date.today().isoformat(),
        "client_count": len(clients),
        "clients": clients,
        "totals": totals,
    }


def _month_label(month: str) -> str:
    import calendar

    if not month or "-" not in month:
        return month
    y, m = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[m]} {y}"


def render_combined_pdf(
    clients_data: list[tuple[Client, dict[str, Any]]], month: str | None = None
) -> Path:
    """Render the combined report PDF for all provided clients.

    Keeps per-client PDFs untouched; this is an additional portfolio-level PDF
    written to reports/combined_{YYYY-MM}.pdf.
    """
    context = build_combined_context(clients_data)
    month = month or context["month"]
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    template = env.get_template("combined_report.html.j2")
    html = template.render(**context)
    out = OUTPUT_DIR / f"combined_{month}.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(out)
    return out