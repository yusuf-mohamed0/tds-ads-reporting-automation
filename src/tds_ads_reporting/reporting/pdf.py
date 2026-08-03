from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from tds_ads_reporting.config import Client
from tds_ads_reporting.manual_inputs.loader import ManualInputs

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "reports"

MONTH_LABELS = {i: calendar.month_name[i] for i in range(1, 13)}


def _period(month: str) -> tuple[str, str]:
    y, m = (int(x) for x in month.split("-"))
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]}"


def _fmt(v: float | int | None, currency: str = "EGP") -> str:
    if v is None:
        return "-"
    return f"{v:,.0f} {currency}"


def render_pdf(cfg, client: Client, month: str, manual: ManualInputs) -> Path:
    date_start, date_stop = _period(month)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    template = env.get_template("report.html.j2")

    platforms = []
    if "meta" in client.platforms():
        platforms.append("Meta (Facebook & Instagram)")
    if "google" in client.platforms():
        platforms.append("Google Ads")

    ctx = {
        "client": {"name": client.name, "email": client.report_recipient},
        "month_label": f"{MONTH_LABELS[int(month.split('-')[1])]} {month.split('-')[0]}",
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
            "amount": _fmt(manual.budget.get("amount")),
            "spent": _fmt(manual.budget.get("spent")),
            "vat": _fmt(manual.budget.get("vat")),
            "remaining": _fmt(manual.budget.get("remaining")),
        },
        "reach": [],
        "messaging": [],
        "content": [],
        "audience": [],
        "ads": [],
    }

    html = template.render(**ctx)
    out = OUTPUT_DIR / f"{client.id}_{month}.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(out)
    return out
