from __future__ import annotations

import calendar
from datetime import date
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML

from tds_ads_reporting.config import AppConfig, Client
from tds_ads_reporting.manual_inputs.loader import ManualInputs
from tds_ads_reporting.reporting.assembler import build_context

ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = ROOT / "templates"
OUTPUT_DIR = ROOT / "reports"


def _period(month: str) -> tuple[str, str]:
    y, m = (int(x) for x in month.split("-"))
    return f"{y}-{m:02d}-01", f"{y}-{m:02d}-{calendar.monthrange(y, m)[1]}"


def _month_label(month: str) -> str:
    y, m = (int(x) for x in month.split("-"))
    return f"{calendar.month_name[m]} {y}"


def render_pdf(cfg: AppConfig, client: Client, month: str, manual: ManualInputs, data) -> Path:
    date_start, date_stop = _period(month)
    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR), autoescape=select_autoescape(["html"]))
    template = env.get_template("report.html.j2")

    ctx = build_context(
        client=client,
        month=month,
        manual=manual,
        data=data,
        month_label=_month_label(month),
        date_start=date_start,
        date_stop=date_stop,
    )

    html = template.render(**ctx)
    out = OUTPUT_DIR / f"{client.id}_{month}.pdf"
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    HTML(string=html, base_url=str(TEMPLATE_DIR)).write_pdf(out)
    return out
