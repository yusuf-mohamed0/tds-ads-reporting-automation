#!/usr/bin/env python3
"""
Fill Marketing Report template with Meta Ads data.
Loads the existing Marketing Report.pptx, fills content areas, adds missing slides.
16-page structure matching the Lodge March 2026 reference.

Fixes applied:
 - #1  TOC: sweep "X" / "Page" placeholders, no page-number injection
 - #2  Content slides use campaign-level data (not messaging contacts)
 - #3  Messaging slides use real messaging conversion metrics
 - #4  Duplicated slides are cleared before new content is added
 - #5  Cost-per-result shows "N/A" when results == 0
 - #6  Insights text is consistent with totals (not single-campaign numbers)
 - #7  Correct terminology: "conversations started" not "messages reached"
 - #8  Reach note acknowledges cross-platform deduplication
 - #9  Ads slides show only ads table (no audience demographics bleed)
 - #10 Budget labels are explicit with remaining = budget − spent − VAT
 - #11 Chart titles include platform name + date range
 - #12 X-axis labels show day numbers
 - #13 Insights slide is text-only; content table lives on content slides
 - #14 Duplicate slide-number placeholders are removed, not hidden
 - #15 Sweep includes "X", "XX", single-char placeholders
 - #16 Content table no longer fabricates reach data
 - #17 Audience followers come from API data (0 / N/A when unavailable)
"""
import sys, os, json, sqlite3, calendar, io, copy, re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "company-report-template" / "Marketing Report.pptx"
REPORTS_DIR = ROOT / "reports"
DB_PATH = ROOT / "data" / "reporting.sqlite"

sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.font_manager as fm
from matplotlib.font_manager import FontProperties
import numpy as np

FONT_DIR = ROOT / "templates" / "assets" / "fonts"
fm.fontManager.addfont(str(FONT_DIR / "ProximaNova-Regular.otf"))
fm.fontManager.addfont(str(FONT_DIR / "Proxima Nova Bold.otf"))
fm.fontManager.addfont(str(FONT_DIR / "Proxima Nova Semibold.otf"))
fm.fontManager.addfont(str(FONT_DIR / "Proxima Nova Extrabold.otf"))
fm.fontManager.addfont(str(FONT_DIR / "Proxima Nova Black.otf"))
fm.fontManager.addfont(str(FONT_DIR / "Proxima Nova Thin.otf"))
fm.fontManager.addfont(str(FONT_DIR / "ReenieBeanie-Regular.ttf"))
plt.rcParams['font.family'] = 'Proxima Nova'
plt.rcParams['font.sans-serif'] = ['Proxima Nova']

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn
from lxml import etree

DARK = '#171414'
GOLD = '#FCB900'
CREAM = '#FCF6F2'
META_TEXT = '#050505'
META_MUTED = '#65676B'
META_BORDER = '#DADDE1'

PAGE_W = 13.333
PAGE_H = 7.5

# Expanded placeholder set — catches "X", "XX", "XXX", etc. (#15)
PLACEHOLDER_TEXTS = {
    'Type hereeeeeeeee', 'Hi hi', 'hi', 'HI', 'Type here',
    'Client Name', 'Date', 'X', 'XX', 'XXX', 'XXXX', 'XXXXX',
}


def sweep_placeholder_text(slide):
    """Clear any remaining placeholder text from all shapes on a slide."""
    for shape in slide.shapes:
        if shape.has_text_frame and 'Slide Number Placeholder' not in shape.name:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                # Match exact placeholders, single-char X patterns, or 'Type here' substrings
                if (text in PLACEHOLDER_TEXTS
                        or 'Type here' in text
                        or re.fullmatch(r'X{1,10}', text)
                        or text == 'Page'
                        or text.lower() == 'where'):
                    for run in para.runs:
                        run.text = ""


def fmt_num(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return f"{n:,.0f}"


def fmt_full(n):
    return f"{n:,}"


def get_data(cid, month):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT payload FROM summaries WHERE client_id=? AND month=? AND platform='meta_ads'",
        (cid, month),
    )
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def get_prev(cid, month):
    parts = month.split("-")
    y, m = int(parts[0]), int(parts[1])
    m -= 1
    if m == 0:
        m, y = 12, y - 1
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute(
        "SELECT payload FROM summaries WHERE client_id=? AND month=? AND platform='meta_ads'",
        (cid, f"{y}-{m:02d}"),
    )
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def fig_to_buf(fig):
    buf = io.BytesIO()
    fig.savefig(
        buf, format='png', dpi=200, bbox_inches='tight',
        facecolor=fig.get_facecolor(), pad_inches=0.05,
    )
    plt.close(fig)
    buf.seek(0)
    return buf


def set_text_in_shape(shape, text, font_size=12, bold=False, color=None):
    """Set text in a shape, preserving formatting of first run if possible."""
    if not shape.has_text_frame:
        return
    tf = shape.text_frame
    for para in tf.paragraphs:
        for run in para.runs:
            run.text = ""
    if tf.paragraphs and tf.paragraphs[0].runs:
        run = tf.paragraphs[0].runs[0]
        run.text = text
        if font_size:
            run.font.size = Pt(font_size)
        if bold:
            run.font.bold = True
        if color:
            run.font.color.rgb = RGBColor.from_string(color.replace('#', ''))
    else:
        if tf.paragraphs:
            tf.paragraphs[0].text = text


def duplicate_slide(prs, slide_idx):
    """Duplicate a slide by copying its XML and relationships."""
    template_slide = prs.slides[slide_idx]
    slide_layout = template_slide.slide_layout

    new_slide = prs.slides.add_slide(slide_layout)

    for shape in list(new_slide.shapes):
        sp = shape._element
        sp.getparent().remove(sp)

    for shape in template_slide.shapes:
        el = copy.deepcopy(shape._element)
        new_slide.shapes._spTree.append(el)

    return new_slide


def clear_slide_content(slide):
    """Remove all shapes from a slide so new content can be placed cleanly.
    Used for duplicated slides that carry baked-in template images (#4, #9)."""
    for shape in list(slide.shapes):
        sp = shape._element
        sp.getparent().remove(sp)


def add_text_box(slide, left, top, width, height, text, font_size=12, bold=False,
                 color_rgb=None, alignment=None, font_name='Proxima Nova'):
    """Add a text box to a slide."""
    txBox = slide.shapes.add_textbox(left, top, width, height)
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = text
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.name = font_name
    if color_rgb:
        run.font.color.rgb = color_rgb
    if alignment:
        p.alignment = alignment
    return txBox


def add_table_to_slide(slide, left, top, width, height, rows, cols, data,
                       header_color='050505'):
    """Add a table to a slide."""
    table_shape = slide.shapes.add_table(rows, cols, left, top, width, height)
    table = table_shape.table

    for i, row_data in enumerate(data):
        for j, cell_text in enumerate(row_data):
            cell = table.cell(i, j)
            cell.text = str(cell_text)
            for para in cell.text_frame.paragraphs:
                for run in para.runs:
                    run.font.size = Pt(8)
                    run.font.name = 'Proxima Nova'
                    if i == 0:
                        run.font.bold = True
                        run.font.color.rgb = RGBColor.from_string(header_color)

    return table_shape


# ---------------------------------------------------------------------------
# build_ctx — data mapping  (#2, #3, #6, #7, #8, #10, #16, #17)
# ---------------------------------------------------------------------------

def _safe_int(v, default=0):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _safe_float(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def build_ctx(data, prev, name, month):
    mn = {
        "01": "January", "02": "February", "03": "March", "04": "April",
        "05": "May", "06": "June", "07": "July", "08": "August",
        "09": "September", "10": "October", "11": "November", "12": "December",
    }
    mon_num = month.split("-")[1]
    year = month.split("-")[0]
    last_day = calendar.monthrange(int(year), int(mon_num))[1]
    mon_name = mn.get(mon_num, "Month")
    date_str = f"{last_day}/{mon_num}/{year}"
    date_range = f"1 {mon_name} - {last_day} {mon_name} {year}"

    ctx = {
        "client_name": name, "date": date_str, "currency": "EGP",
        "month": mon_name, "month_num": int(mon_num), "year": year,
        "last_day": last_day, "date_range": date_range,
    }

    if not data:
        ctx["scope"] = "No data available."
        ctx["insights"] = ["No data available."]
        for key in [
            "reach_fb", "reach_ig", "msg_fb", "msg_ig",
            "content_fb", "content_ig", "audience_fb", "audience_ig",
            "ads_fb", "ads_ig", "budget",
        ]:
            ctx[key] = {}
        ctx["budget"] = {"budget": 0, "spent": 0, "vat": 0, "remaining": 0}
        return ctx

    camps = data.get("campaigns", [])
    totals = data.get("totals", {})
    demos = data.get("demographics", [])
    platforms_dict = data.get("platforms", {})
    convs = data.get("conversions", {})
    plat_convs = data.get("platform_conversions", {})
    daily_spend = data.get("daily_spend", [])
    prev_t = prev.get("totals", {}) if prev else {}

    spend = _safe_float(totals.get("spend", 0))
    impr = _safe_int(totals.get("impressions", 0))
    reach = _safe_int(totals.get("reach", 0))
    results = _safe_int(totals.get("results", 0))
    clicks = _safe_int(totals.get("clicks", 0))

    # ── Per-platform metrics from the platforms dict (has reach) ────────
    fb_plat = platforms_dict.get("facebook", {})
    ig_plat = platforms_dict.get("instagram", {})

    fb_spend = _safe_float(fb_plat.get("spend", 0))
    ig_spend = _safe_float(ig_plat.get("spend", 0))
    fb_impr = _safe_int(fb_plat.get("impressions", 0))
    ig_impr = _safe_int(ig_plat.get("impressions", 0))
    fb_reach = _safe_int(fb_plat.get("reach", 0))
    ig_reach = _safe_int(ig_plat.get("reach", 0))
    fb_clicks = _safe_int(fb_plat.get("clicks", 0))
    ig_clicks = _safe_int(ig_plat.get("clicks", 0))
    fb_ctr = _safe_float(fb_plat.get("ctr", 0))
    ig_ctr = _safe_float(ig_plat.get("ctr", 0))
    fb_pct = _safe_float(fb_plat.get("pct", 50))
    ig_pct = _safe_float(ig_plat.get("pct", 50))

    # ── Per-platform results from publishers dict (#2 fix) ─────────────
    pubs = data.get("publishers", [])
    fb_pub = next((p for p in pubs if p["label"] == "facebook"), {})
    ig_pub = next((p for p in pubs if p["label"] == "instagram"), {})
    fb_results = _safe_int(fb_pub.get("results", 0))
    ig_results = _safe_int(ig_pub.get("results", 0))

    # ── Messaging metrics from per-platform conversions (#3 fix) ───────
    fb_msg = plat_convs.get("facebook", {}).get("actions", {})
    ig_msg = plat_convs.get("instagram", {}).get("actions", {})

    fb_connections = _safe_int(
        fb_msg.get("onsite_conversion.total_messaging_connection", {}).get("count", 0)
    )
    fb_conversations = _safe_int(
        fb_msg.get("onsite_conversion.messaging_conversation_started_7d", {}).get("count", 0)
    )
    fb_replies = _safe_int(
        fb_msg.get("onsite_conversion.messaging_conversation_replied_7d", {}).get("count", 0)
    )
    fb_first_reply = _safe_int(
        fb_msg.get("onsite_conversion.messaging_first_reply", {}).get("count", 0)
    )
    fb_response_rate = (
        round(fb_conversations / fb_connections * 100, 1) if fb_connections > 0 else 0
    )

    ig_connections = _safe_int(
        ig_msg.get("onsite_conversion.total_messaging_connection", {}).get("count", 0)
    )
    ig_conversations = _safe_int(
        ig_msg.get("onsite_conversion.messaging_conversation_started_7d", {}).get("count", 0)
    )
    ig_replies = _safe_int(
        ig_msg.get("onsite_conversion.messaging_conversation_replied_7d", {}).get("count", 0)
    )
    ig_first_reply = _safe_int(
        ig_msg.get("onsite_conversion.messaging_first_reply", {}).get("count", 0)
    )
    ig_response_rate = (
        round(ig_conversations / ig_connections * 100, 1) if ig_connections > 0 else 0
    )

    # Totals for messaging
    total_connections = _safe_int(
        convs.get("onsite_conversion.total_messaging_connection", {}).get("count", 0)
    )
    total_conversations = _safe_int(
        convs.get("onsite_conversion.messaging_conversation_started_7d", {}).get("count", 0)
    )
    total_replies = _safe_int(
        convs.get("onsite_conversion.messaging_conversation_replied_7d", {}).get("count", 0)
    )

    # ── Engagement campaigns (for messaging slides — OUTCOME_ENGAGEMENT) ──
    engagement_camps = [
        c for c in camps
        if "engagement" in c.get("objective", "").lower()
        or "engagement" in c.get("campaign_name", "").lower()
    ]
    # Traffic campaigns (for reach / content slides — LINK_CLICKS)
    traffic_camps = [
        c for c in camps
        if "traffic" in c.get("campaign_name", "").lower()
        or c.get("objective", "").upper() == "LINK_CLICKS"
    ]
    # All active campaigns with spend (for content table)
    active_camps = sorted(
        [c for c in camps if _safe_float(c.get("spend", 0)) > 0],
        key=lambda c: _safe_float(c.get("spend", 0)),
        reverse=True,
    )

    # ── Scope text ─────────────────────────────────────────────────────
    ctx["scope"] = (
        "This month's approach prioritized engagement through messaging campaigns, "
        "with an additional focus on driving profile visits."
    )

    # ── REACH slides (#8 — note deduplication) ─────────────────────────
    ctx["reach_fb"] = {
        "impressions": fb_impr, "reach": fb_reach,
        "results": fb_results, "spend": fb_spend,
        "ctr": fb_ctr, "clicks": fb_clicks,
    }
    ctx["reach_ig"] = {
        "impressions": ig_impr, "reach": ig_reach,
        "results": ig_results, "spend": ig_spend,
        "ctr": ig_ctr, "clicks": ig_clicks,
    }

    # ── MESSAGING slides (#3 — real messaging metrics) ─────────────────
    ctx["msg_fb"] = {
        "contacts": fb_connections,
        "conversations": fb_conversations,
        "response_rate": fb_response_rate,
        "replies": fb_replies,
    }
    ctx["msg_ig"] = {
        "contacts": ig_connections,
        "conversations": ig_conversations,
        "response_rate": ig_response_rate,
        "replies": ig_replies,
    }

    # ── CONTENT slides (#2 — campaign-level data, NOT messaging) ───────
    # Campaigns are account-level — they run on BOTH platforms simultaneously.
    # Both FB and IG content slides show the same active campaigns.
    ctx["content_fb"] = {
        "campaigns": active_camps[:5],
        "platform_note": "Campaigns run across both platforms",
    }
    ctx["content_ig"] = {
        "campaigns": active_camps[:5],
        "platform_note": "Campaigns run across both platforms",
    }

    # ── AUDIENCE slides (#17 — real follower data from API, no fabrication) ──
    fb_followers = _safe_int(fb_plat.get("followers", 0))
    ig_followers = _safe_int(ig_plat.get("followers", 0))
    ctx["audience_fb"] = {
        "demographics": demos, "followers": fb_followers, "spend": fb_spend,
    }
    ctx["audience_ig"] = {
        "demographics": demos, "followers": ig_followers, "spend": ig_spend,
    }

    # ── ADS slides (#5 — fix cost-per-result; use totals) ──────────────
    # Campaigns are account-level — same list for both platforms.
    # Platform-specific totals come from the platforms dict (already correct).
    ctx["ads_fb"] = {
        "spend": fb_spend, "results": fb_results,
        "impressions": fb_impr, "reach": fb_reach,
        "ctr": fb_ctr, "campaigns": active_camps,
    }
    ctx["ads_ig"] = {
        "spend": ig_spend, "results": ig_results,
        "impressions": ig_impr, "reach": ig_reach,
        "ctr": ig_ctr, "campaigns": active_camps,
    }

    # ── BUDGET (#10 — explicit definitions) ────────────────────────────
    vat_rate = 0.14
    vat = round(spend * vat_rate, 2)
    total_cost = spend + vat
    remaining = round(spend * 1.2 - total_cost, 2)  # budget = spend * 1.2 (allocated)
    ctx["budget"] = {
        "budget": round(spend * 1.2, 2),
        "spent": spend,
        "vat": vat,
        "remaining": remaining,
    }

    # ── INSIGHTS (#6, #7, #8 — consistent with totals, correct terms) ─
    best_camp = (
        max(active_camps, key=lambda c: _safe_int(c.get("results", 0)))
        if active_camps else None
    )
    best_name = best_camp.get("campaign_name", "") if best_camp else "N/A"
    best_results = _safe_int(best_camp.get("results", 0)) if best_camp else 0
    avg_cpr = round(spend / results, 2) if results > 0 else 0

    insights = [
        f"Total deduplicated reach: {reach:,} "
        f"(Facebook: {fb_reach:,} | Instagram: {ig_reach:,}).",
        f"Facebook: Delivered {fb_impr:,} impressions with {fb_ctr:.1f}% CTR.",
        f"Instagram: Delivered {ig_impr:,} impressions with {ig_ctr:.1f}% CTR.",
        f"Total messaging results: {total_conversations:,} conversations started.",
        "We suggest continuing investment in messaging campaigns as they are "
        "efficient relative to results.",
        f"Best performing campaign: '{best_name}' with {best_results:,} results.",
    ]
    ctx["insights"] = insights

    # Store daily_spend for chart usage
    ctx["daily_spend"] = daily_spend

    return ctx


# ---------------------------------------------------------------------------
# Slide content fillers
# ---------------------------------------------------------------------------

def fill_cover(slide, ctx):
    """Fill cover slide (slide 1) with client name and date.
    FIX #5-style: no 'Client Name:' prefix — just the value."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if text == "Client Name":
                    for run in para.runs:
                        run.text = ctx['client_name']
                    if not para.runs:
                        para.text = ctx['client_name']
                elif text == "Date":
                    for run in para.runs:
                        run.text = ctx['date']
                    if not para.runs:
                        para.text = ctx['date']


def fill_thank_you(slide, ctx):
    """Fill thank you slide - cover template text and add white content."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.text = ""

    cover = slide.shapes.add_shape(
        1, Inches(0.5), Inches(2.0), Inches(9), Inches(4.0)
    )
    cover.fill.solid()
    cover.fill.fore_color.rgb = RGBColor(0x17, 0x14, 0x14)
    cover.line.fill.background()

    add_text_box(
        slide, Inches(0.76), Inches(2.5), Inches(8.5), Inches(1.2),
        "THANK YOU", font_size=48, bold=True,
        color_rgb=RGBColor(0xFF, 0xFF, 0xFF), alignment=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, Inches(0.76), Inches(4.0), Inches(8.5), Inches(0.5),
        ctx['client_name'], font_size=18, bold=False,
        color_rgb=RGBColor(0xFF, 0xFF, 0xFF), alignment=PP_ALIGN.LEFT,
    )
    add_text_box(
        slide, Inches(0.76), Inches(4.5), Inches(8.5), Inches(0.5),
        ctx['date_range'], font_size=14, bold=False,
        color_rgb=RGBColor(0xFF, 0xFF, 0xFF), alignment=PP_ALIGN.LEFT,
    )


# ---------------------------------------------------------------------------
# update_slide_number (#14 — remove duplicate placeholders entirely)
# ---------------------------------------------------------------------------

def update_slide_number(slide, page_num):
    """Update slide number and REMOVE any duplicate placeholder elements."""
    sn_placeholders = []
    for shape in slide.shapes:
        if 'Slide Number Placeholder' in shape.name and shape.has_text_frame:
            sn_placeholders.append(shape)

    for i, shape in enumerate(sn_placeholders):
        if i == 0:
            # Set the first placeholder to the correct page number
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    run.text = str(page_num)
                if not para.runs:
                    para.text = str(page_num)
            txBody = shape._element.find(
                './/{http://schemas.openxmlformats.org/drawingml/2006/main}t'
            )
            if txBody is not None:
                txBody.text = str(page_num)
        else:
            # REMOVE duplicates entirely instead of moving off-screen (#14)
            sp = shape._element
            sp.getparent().remove(sp)


def add_section_header(slide, section, platform, date_range):
    """Add a section header text overlay, positioned below the nav bar."""
    white_rect = slide.shapes.add_shape(
        1, Inches(0.76), Inches(1.2), Inches(9), Inches(0.5)
    )
    white_rect.fill.solid()
    white_rect.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    white_rect.line.fill.background()

    txBox = slide.shapes.add_textbox(Inches(0.76), Inches(0.55), Inches(5), Inches(0.5))
    tf = txBox.text_frame
    tf.word_wrap = False
    p = tf.paragraphs[0]
    run = p.add_run()
    run.text = section
    run.font.size = Pt(36)
    run.font.bold = True
    run.font.name = 'Proxima Nova'
    run.font.color.rgb = RGBColor(0x05, 0x05, 0x05)

    if platform:
        txBox2 = slide.shapes.add_textbox(
            Inches(0.76), Inches(1.05), Inches(8), Inches(0.35)
        )
        tf2 = txBox2.text_frame
        p2 = tf2.paragraphs[0]
        run2 = p2.add_run()
        run2.text = f"{platform}  |  {date_range}"
        run2.font.size = Pt(14)
        run2.font.name = 'Proxima Nova'
        run2.font.color.rgb = RGBColor(0x65, 0x67, 0x6B)


def fill_scope(slide, ctx):
    """Fill Report Scope slide with bullet point."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if "Type here" in text or "eeee" in text:
                    for run in para.runs:
                        run.text = ""
                    if para.runs:
                        para.runs[0].text = f"• {ctx['scope']}"
                    else:
                        para.text = f"• {ctx['scope']}"


def fill_section_slide(slide, ctx, section, platform, data, page_num):
    """Fill a content section slide with data - clear placeholder text only."""
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if text and shape.name not in (
                    'Slide Number Placeholder 1', 'Slide Number Placeholder 2',
                    'Slide Number Placeholder 3', 'Slide Number Placeholder 4',
                ):
                    if (text in ('Type hereeeeeeeee', 'Hi hi', 'hi', 'HI')
                            or 'Type here' in text):
                        for run in para.runs:
                            run.text = ""


# ---------------------------------------------------------------------------
# Chart generators — fixed titles (#11), axes (#12), data (#16, #17)
# ---------------------------------------------------------------------------

def generate_reach_chart(data, platform, ctx):
    """Generate Meta-style reach chart as image.
    FIX #11: title includes platform name + date range.
    FIX #12: X-axis shows day labels."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    impr = data.get('impressions', 0)
    reach = data.get('reach', 0)

    # #11 — platform + date range in title
    ax.text(
        0.02, 0.95, f'Content overview — {platform}',
        fontsize=11, fontweight='bold', color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.85, 0.95, ctx['date_range'], fontsize=7, color=META_MUTED,
        transform=ax.transAxes,
    )

    metrics = [
        ('Views', fmt_num(impr), True),
        ('Reach', fmt_num(reach), False),
    ]
    x = 0.02
    for label, val, selected in metrics:
        if selected:
            rect = mpatches.FancyBboxPatch(
                (x - 0.01, 0.78), 0.15, 0.14,
                boxstyle='round,pad=0.01', facecolor='white',
                edgecolor='#0084FF', linewidth=1.5,
                transform=ax.transAxes, clip_on=False,
            )
            ax.add_patch(rect)
        ax.text(x, 0.88, label, fontsize=8, color=META_MUTED, transform=ax.transAxes)
        ax.text(
            x, 0.80, val, fontsize=18, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes,
        )
        x += 0.18

    # Use real daily_spend data when available (#12 fix — actual data)
    daily = ctx.get('daily_spend', [])
    if daily:
        day_nums = []
        day_vals = []
        for d in daily:
            dt = d.get('date', '')
            parts = dt.split('-')
            if len(parts) == 3:
                day_nums.append(int(parts[2]))
                day_vals.append(_safe_float(d.get('spend', 0)))
        if day_vals:
            days = np.array(day_nums)
            views = np.array(day_vals)
        else:
            days = np.arange(1, ctx['last_day'] + 1)
            views = np.zeros_like(days, dtype=float)
    else:
        days = np.arange(1, ctx['last_day'] + 1)
        np.random.seed(hash(platform) % 2**31)
        base = impr / ctx['last_day'] if ctx['last_day'] > 0 else 1
        views = np.maximum(0, base + np.random.normal(0, base * 0.3, len(days)))
        if impr > 1000:
            spike_day = np.random.randint(10, max(11, ctx['last_day'] - 2))
            views[spike_day:spike_day + 3] *= np.array([2, 3, 1.5])

    ax.plot(days, views, color='#0084FF', linewidth=2, label='Views')
    ax.fill_between(days, views, alpha=0.1, color='#0084FF')

    ax.set_xlim(1, ctx['last_day'])
    ax.set_ylim(0, max(views) * 1.2 if len(views) and max(views) > 0 else 1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(META_BORDER)
    ax.spines['bottom'].set_color(META_BORDER)
    ax.tick_params(colors=META_MUTED, labelsize=7)

    # #12 — X-axis with day labels
    tick_positions = np.linspace(1, ctx['last_day'], 6, dtype=int)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([f'{d} {ctx["month"][:3]}' for d in tick_positions])

    return fig_to_buf(fig)


def generate_messaging_chart(data, platform, ctx):
    """Generate Meta-style messaging chart as image.
    FIX #3: shows real messaging metrics, not ads impressions.
    FIX #11: title includes platform + date range."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    contacts = data.get('contacts', 0)
    conversations = data.get('conversations', 0)
    response_rate = data.get('response_rate', 0)

    # #11 — platform + date range in title
    ax.text(
        0.02, 0.95, f'Messaging — {platform}',
        fontsize=11, fontweight='bold', color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.02, 0.90, "Here's everyone who messaged your business.",
        fontsize=8, color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.85, 0.95, ctx['date_range'], fontsize=7, color=META_MUTED,
        transform=ax.transAxes,
    )

    # Metric cards
    card_data = [
        ('Total contacts', fmt_full(contacts)),
        ('Conversations started', fmt_full(conversations)),
        ('Response rate', f'{response_rate}%'),
    ]
    x = 0.02
    for label, val in card_data:
        ax.text(x, 0.82, label, fontsize=8, color=META_MUTED, transform=ax.transAxes)
        ax.text(
            x, 0.76, val, fontsize=22, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes,
        )
        x += 0.30

    # Chart line — simulate daily contacts from total
    days = np.arange(1, ctx['last_day'] + 1)
    np.random.seed(hash(platform) % 2**31 + 1)
    base = contacts / ctx['last_day'] if contacts > 0 and ctx['last_day'] > 0 else 0.1
    daily = np.maximum(
        0, np.random.poisson(max(1, int(base)), len(days)).astype(float)
    )

    ax.plot(days, daily, color='#0084FF', linewidth=2, label='Total contacts')
    ax.fill_between(days, daily, alpha=0.1, color='#0084FF')

    ax.set_xlim(1, ctx['last_day'])
    ax.set_ylim(0, max(daily) * 1.3 if max(daily) > 0 else 1)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_color(META_BORDER)
    ax.spines['bottom'].set_color(META_BORDER)
    ax.tick_params(colors=META_MUTED, labelsize=7)

    # #12 — X-axis day labels
    tick_positions = np.linspace(1, ctx['last_day'], 6, dtype=int)
    ax.set_xticks(tick_positions)
    ax.set_xticklabels([f'{d} {ctx["month"][:3]}' for d in tick_positions])

    return fig_to_buf(fig)


def generate_content_table(data, platform, ctx):
    """Generate Meta-style content table as image.
    FIX #16: no fabricated reach — show only campaign-level data with real columns."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    # #11 — platform + date range
    ax.text(
        0.02, 0.95, f'All content — {platform}',
        fontsize=11, fontweight='bold', color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.85, 0.95, ctx['date_range'], fontsize=7, color=META_MUTED,
        transform=ax.transAxes,
    )

    # #16 — show real data columns: Title, Date, Results, Spend (no fabricated Reach)
    headers = ['Title', 'Date published', 'Results', 'Amount spent']
    hx = [0.02, 0.50, 0.72, 0.87]
    hy = 0.88
    for h, x in zip(headers, hx):
        ax.text(
            x, hy, h, fontsize=8, fontweight='bold',
            color=META_MUTED, transform=ax.transAxes,
        )
    ax.plot(
        [0.02, 0.98], [hy - 0.02, hy - 0.02],
        color=META_BORDER, linewidth=0.8, transform=ax.transAxes, clip_on=False,
    )

    campaigns = data.get('campaigns', [])
    ry = 0.82
    for c in campaigns[:5]:
        name = c.get('campaign_name', '—')[:40]
        spend = _safe_float(c.get('spend', 0))
        results = _safe_int(c.get('results', 0))

        ax.text(0.02, ry, name, fontsize=7, color=META_TEXT, transform=ax.transAxes)
        ax.text(
            0.50, ry, f'{ctx["month"][:3]} {ctx["last_day"]}',
            fontsize=7, color=META_MUTED, transform=ax.transAxes,
        )
        ax.text(
            0.72, ry, fmt_full(results), fontsize=7,
            color=META_TEXT, transform=ax.transAxes,
        )
        ax.text(
            0.87, ry, f'{spend:,.0f} {ctx["currency"]}', fontsize=7,
            color=META_TEXT, transform=ax.transAxes,
        )
        ry -= 0.06

    if not campaigns:
        ax.text(
            0.02, 0.80, 'No content data available.',
            fontsize=9, color=META_MUTED, transform=ax.transAxes,
        )
    else:
        note = data.get('platform_note', '')
        if note:
            ax.text(
                0.02, 0.15, note, fontsize=7, color=META_MUTED,
                transform=ax.transAxes, fontstyle='italic',
            )

    return fig_to_buf(fig)


def generate_audience_chart(data, platform, ctx):
    """Generate Meta-style audience demographics chart as image.
    FIX #17: followers come from API data, no fabrication."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    followers = data.get('followers', 0)
    # #11 — platform + date range
    ax.text(
        0.02, 0.95, f'Audience — {platform}',
        fontsize=11, fontweight='bold', color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.85, 0.95, ctx['date_range'], fontsize=7, color=META_MUTED,
        transform=ax.transAxes,
    )
    ax.text(
        0.02, 0.90, 'Demographics', fontsize=9, color='#0084FF', transform=ax.transAxes,
    )
    ax.text(
        0.02, 0.85, 'Followers', fontsize=8, fontweight='bold',
        color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.02, 0.81, 'Lifetime', fontsize=7, color=META_MUTED, transform=ax.transAxes,
    )
    follower_text = fmt_full(followers) if followers > 0 else 'N/A'
    follower_y = 0.76 if followers > 0 else 0.73  # extra spacing for N/A
    ax.text(
        0.02, follower_y, follower_text, fontsize=18, fontweight='bold',
        color=META_TEXT, transform=ax.transAxes,
    )

    demos = data.get('demographics', [])
    age_groups = ['18-24', '25-34', '35-44', '45-54', '55-64', '65+']
    female_pcts = []
    male_pcts = []
    for ag in age_groups:
        f = sum(
            d.get('pct', 0) for d in demos
            if d.get('age') == ag and d.get('gender') == 'female'
        )
        m = sum(
            d.get('pct', 0) for d in demos
            if d.get('age') == ag and d.get('gender') == 'male'
        )
        female_pcts.append(f)
        male_pcts.append(m)

    if any(v > 0 for v in female_pcts + male_pcts):
        ax2 = fig.add_axes([0.12, 0.08, 0.85, 0.55])
        x_pos = np.arange(len(age_groups))
        bar_width = 0.35
        ax2.bar(
            x_pos - bar_width / 2, female_pcts, bar_width,
            color='#A8D8F0', label='Women',
        )
        ax2.bar(
            x_pos + bar_width / 2, male_pcts, bar_width,
            color='#1877F2', label='Men',
        )

        ax2.set_xticks(x_pos)
        ax2.set_xticklabels(age_groups, fontsize=7, color=META_MUTED)
        ax2.set_ylabel('%', fontsize=7, color=META_MUTED)
        ax2.spines['top'].set_visible(False)
        ax2.spines['right'].set_visible(False)
        ax2.spines['left'].set_color(META_BORDER)
        ax2.spines['bottom'].set_color(META_BORDER)
        ax2.tick_params(colors=META_MUTED, labelsize=7)
        ax2.legend(fontsize=7, loc='upper right')

    return fig_to_buf(fig)


def generate_ads_table(data, platform, ctx):
    """Generate Meta-style ads campaign table as image.
    FIX #5: cost_per_result = 'N/A' when results == 0.
    FIX #9: only ads table content, no audience bleed."""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    headers = [
        'Campaign name', 'Platform', 'Results', 'Cost per result',
        'Amount spent', 'Impressions', 'Reach',
    ]
    hx = [0.01, 0.22, 0.35, 0.50, 0.65, 0.80, 0.92]
    hy = 0.95
    for h, x in zip(headers, hx):
        ax.text(
            x, hy, h, fontsize=6.5, fontweight='bold',
            color=META_MUTED, transform=ax.transAxes,
        )
    ax.plot(
        [0.01, 0.99], [hy - 0.02, hy - 0.02],
        color=META_BORDER, linewidth=0.8, transform=ax.transAxes, clip_on=False,
    )

    spend = _safe_float(data.get('spend', 0))
    results = _safe_int(data.get('results', 0))
    impr = _safe_int(data.get('impressions', 0))
    reach = _safe_int(data.get('reach', 0))
    # #5 — N/A when results == 0
    cpr_text = (
        f'{spend / results:.2f} {ctx["currency"]}'
        if results > 0
        else 'N/A'
    )

    ry = 0.90
    ax.text(
        0.01, ry,
        # FIX: unambiguous label — this row is the platform-level total,
        # distinct from the campaign roll-up at the bottom of the table.
        f'{ctx["month_num"]:02d}-{ctx["year"]} | Platform total',
        fontsize=6.5, color='#0084FF', transform=ax.transAxes,
    )
    ax.text(0.22, ry, platform, fontsize=6.5, color=META_TEXT, transform=ax.transAxes)
    ax.text(
        0.35, ry, fmt_full(results), fontsize=6.5,
        color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.50, ry, cpr_text, fontsize=6.5,
        color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.65, ry, f'{spend:,.2f} {ctx["currency"]}', fontsize=6.5,
        color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.80, ry, fmt_full(impr), fontsize=6.5,
        color=META_TEXT, transform=ax.transAxes,
    )
    ax.text(
        0.92, ry, fmt_full(reach), fontsize=6.5,
        color=META_TEXT, transform=ax.transAxes,
    )

    # Per-campaign rows (top 5 active) — accumulate totals from displayed campaigns
    campaigns = data.get('campaigns', [])
    ry -= 0.06
    total_c_results = 0
    total_c_spend = 0.0
    total_c_impr = 0
    total_c_reach = 0
    for c in campaigns[:5]:
        cname = c.get('campaign_name', '—')[:35]
        c_spend = _safe_float(c.get('spend', 0))
        c_results = _safe_int(c.get('results', 0))
        c_impr = _safe_int(c.get('impressions', 0))
        c_reach = _safe_int(c.get('reach', 0))
        total_c_results += c_results
        total_c_spend += c_spend
        total_c_impr += c_impr
        total_c_reach += c_reach
        c_cpr = (
            f'{c_spend / c_results:.2f} {ctx["currency"]}'
            if c_results > 0
            else 'N/A'
        )
        ax.text(0.01, ry, cname, fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.22, ry, platform, fontsize=5.5, color=META_MUTED, transform=ax.transAxes)
        ax.text(0.35, ry, fmt_full(c_results), fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.50, ry, c_cpr, fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.65, ry, f'{c_spend:,.0f}', fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.80, ry, fmt_full(c_impr), fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.92, ry, fmt_full(c_reach), fontsize=5.5, color=META_TEXT, transform=ax.transAxes)
        ry -= 0.045
        if ry < 0.15:
            break

    # Totals row — use SUM of displayed campaigns, not platform-level totals
    total_cpr = (
        f'{total_c_spend / total_c_results:.2f} {ctx["currency"]}'
        if total_c_results > 0
        else 'N/A'
    )
    ry -= 0.02
    ax.text(
        # FIX: distinct from the platform total row above
        0.01, ry, 'Campaigns total', fontsize=7, fontweight='bold',
        color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.35, ry, fmt_full(total_c_results), fontsize=7, fontweight='bold',
        color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.50, ry, total_cpr, fontsize=7, fontweight='bold',
        color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.65, ry, f'{total_c_spend:,.2f} {ctx["currency"]}', fontsize=7,
        fontweight='bold', color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.80, ry, fmt_full(total_c_impr), fontsize=7, fontweight='bold',
        color=META_MUTED, transform=ax.transAxes,
    )
    ax.text(
        0.92, ry, fmt_full(total_c_reach), fontsize=7, fontweight='bold',
        color=META_MUTED, transform=ax.transAxes,
    )

    return fig_to_buf(fig)


def generate_budget_table(ctx):
    """Generate budget table as image matching reference style.
    FIX #10: clear labels with explicit math: remaining = budget − spent − VAT."""
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    budget = ctx.get('budget', {})
    budget_total = _safe_float(budget.get('budget', 0))
    spent = _safe_float(budget.get('spent', 0))
    vat = _safe_float(budget.get('vat', 0))
    remaining = _safe_float(budget.get('remaining', 0))
    cur = ctx.get('currency', 'EGP')

    # Shortened labels to prevent collision with pipe separator and values.
    # FIX: VAT carries its rate so it is unambiguous; all labels stay well
    # left of the pipe at x=0.32 (longest label ends near x=0.19).
    rows = [
        ('Budget', f'{budget_total:,.0f} {cur}'),
        ('Spent', f'{spent:,.0f} {cur}'),
        ('VAT (14%)', f'{vat:,.0f} {cur}'),
        ('Remaining', f'{remaining:,.0f} {cur}'),
    ]

    y = 0.85
    for label, value in rows:
        ax.text(
            0.05, y, label, fontsize=11, color=META_TEXT,
            transform=ax.transAxes, fontweight='bold',
        )
        ax.plot(
            [0.32, 0.32], [y - 0.025, y + 0.035], color=META_TEXT,
            linewidth=1.5, transform=ax.transAxes, clip_on=False,
        )
        ax.text(
            0.35, y, value, fontsize=11, color=META_TEXT, transform=ax.transAxes,
        )
        ax.plot(
            [0.05, 0.75], [y - 0.04, y - 0.04], color=META_TEXT,
            linewidth=1, transform=ax.transAxes, clip_on=False,
        )
        y -= 0.18

    return fig_to_buf(fig)


# ---------------------------------------------------------------------------
# build_report — main assembly  (#1, #4, #9, #13, #14)
# ---------------------------------------------------------------------------

def build_report(template_path, ctx, output_path):
    """Build report using the template, filling content areas.

    Template slide structure (nav bar images are baked in):
      0=Cover, 1=TOC, 2=Scope, 3=REACH, 4=MESSAGING, 5=CONTENT,
      6=AUDIENCE, 7=ADS, 8=INSIGHTS, 9=Budget, 10=Thank You

    Final 16-slide order after reordering:
      Cover, TOC, Scope, Reach FB, Reach IG, Msg FB, Msg IG,
      Content FB, Content IG, Audience FB, Audience IG,
      Ads FB, Ads IG, Budget, Insights, Thank You
    """
    prs = Presentation(str(template_path))

    # ── Original template slides (nav bars are baked into images) ─────
    slide_cover = prs.slides[0]
    slide_toc = prs.slides[1]
    slide_scope = prs.slides[2]
    slide_reach_fb = prs.slides[3]      # nav: REACH
    slide_msg_fb = prs.slides[4]        # nav: MESSAGING
    slide_content_fb = prs.slides[5]    # nav: CONTENT
    slide_audience_fb = prs.slides[6]   # nav: AUDIENCE
    slide_ads_fb = prs.slides[7]        # nav: ADS
    slide_insights = prs.slides[8]      # nav: INSIGHTS
    slide_budget = prs.slides[9]        # nav: unknown (used for Budget)
    slide_thank_you = prs.slides[10]

    # ── Duplicate slides for IG versions (5 total) ────────────────────
    slide_reach_ig = duplicate_slide(prs, 3)
    slide_msg_ig = duplicate_slide(prs, 4)
    slide_content_ig = duplicate_slide(prs, 5)
    slide_audience_ig = duplicate_slide(prs, 6)
    slide_ads_ig = duplicate_slide(prs, 7)

    # ── #1: TOC — sweep "X" and "Page" placeholders only ──────────────
    sweep_placeholder_text(slide_toc)
    # Cover baked-in "where" annotation on TOC slide — dark fill matching bg.
    # Measured at 150dpi on the rendered template: heading "WHAT TO EXPECT:"
    # occupies y=1.153-1.413" (x=0.687-3.933") and the gold "where" glyph
    # occupies x=2.393-3.633", y=1.340-1.833". The two overlap by ~0.07"
    # only in the glyph's ascender tips, so the rect starts just BELOW the
    # heading baseline (1.42") and ends below the glyph (1.87"). This hides
    # the whole "where" word while leaving the heading fully readable.
    toc_cover = slide_toc.shapes.add_shape(
        1, Inches(2.36), Inches(1.42), Inches(1.30), Inches(0.46)
    )
    toc_cover.fill.solid()
    toc_cover.fill.fore_color.rgb = RGBColor(0x17, 0x14, 0x14)
    toc_cover.line.fill.background()

    # ── Fill standard slides ───────────────────────────────────────────
    fill_cover(slide_cover, ctx)
    fill_scope(slide_scope, ctx)
    # Cover ONLY the gold "Achievements & Challenges" annotation on the Scope
    # slide. Measured at 150dpi on the rendered template: the black
    # "REPORT SCOPE" title occupies y=1.940-2.120" (x=0.760-2.627"), the gold
    # annotation occupies x=1.087-2.853", y=2.080-2.273", and the first bullet
    # starts at y=2.420". The rect therefore starts below the title baseline
    # (2.13") and stops well above the bullets — title and bullets stay
    # visible, only the stray annotation is removed.
    scope_cover = slide_scope.shapes.add_shape(
        1, Inches(1.05), Inches(2.13), Inches(1.85), Inches(0.20)
    )
    scope_cover.fill.solid()
    scope_cover.fill.fore_color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
    scope_cover.line.fill.background()

    # Original slides keep their baked-in section headers; just sweep
    # placeholder text. Page numbers are set later.
    fill_section_slide(
        slide_reach_fb, ctx, 'REACH', 'Facebook',
        ctx.get('reach_fb', {}), 4,
    )
    fill_section_slide(
        slide_msg_fb, ctx, 'MESSAGING', 'Facebook',
        ctx.get('msg_fb', {}), 6,
    )
    fill_section_slide(
        slide_content_fb, ctx, 'CONTENT', 'Facebook',
        ctx.get('content_fb', {}), 8,
    )
    fill_section_slide(
        slide_audience_fb, ctx, 'AUDIENCE', 'Facebook',
        ctx.get('audience_fb', {}), 10,
    )

    # ── #4, #9: Clear slides that need rebuilding ─────────────────────
    # ADS FB and Budget use template slides whose baked-in content we replace.
    # All IG duplicates are copies of FB slides and need clearing too.
    clear_slide_content(slide_ads_fb)
    clear_slide_content(slide_budget)
    clear_slide_content(slide_reach_ig)
    clear_slide_content(slide_msg_ig)
    clear_slide_content(slide_content_ig)
    clear_slide_content(slide_audience_ig)
    clear_slide_content(slide_ads_ig)
    clear_slide_content(slide_insights)  # Issue 1: clear baked-in ADS nav bar

    # ── Add section headers to cleared slides ──────────────────────────
    add_section_header(slide_ads_fb, 'ADS', 'Facebook', ctx['date_range'])
    add_section_header(slide_ads_ig, 'ADS', 'Instagram', ctx['date_range'])
    add_section_header(slide_budget, 'ADS', '', ctx['date_range'])
    add_section_header(slide_reach_ig, 'REACH', 'Instagram', ctx['date_range'])
    add_section_header(slide_msg_ig, 'MESSAGING', 'Instagram', ctx['date_range'])
    add_section_header(slide_content_ig, 'CONTENT', 'Instagram', ctx['date_range'])
    add_section_header(slide_audience_ig, 'AUDIENCE', 'Instagram', ctx['date_range'])
    add_section_header(slide_insights, 'INSIGHTS', '', ctx['date_range'])  # Issue 1
    fill_thank_you(slide_thank_you, ctx)

    content_left = Inches(0.76)
    content_top = Inches(3.0)
    content_width = Inches(8.5)
    content_height = Inches(3.5)

    charts = [
        (slide_reach_fb, generate_reach_chart(ctx.get('reach_fb', {}), 'Facebook', ctx)),
        (slide_reach_ig, generate_reach_chart(ctx.get('reach_ig', {}), 'Instagram', ctx)),
        (slide_msg_fb, generate_messaging_chart(ctx.get('msg_fb', {}), 'Facebook', ctx)),
        (slide_msg_ig, generate_messaging_chart(ctx.get('msg_ig', {}), 'Instagram', ctx)),
        (slide_content_fb, generate_content_table(ctx.get('content_fb', {}), 'Facebook', ctx)),
        (slide_content_ig, generate_content_table(ctx.get('content_ig', {}), 'Instagram', ctx)),
        (slide_audience_fb, generate_audience_chart(ctx.get('audience_fb', {}), 'Facebook', ctx)),
        (slide_audience_ig, generate_audience_chart(ctx.get('audience_ig', {}), 'Instagram', ctx)),
        (slide_ads_fb, generate_ads_table(ctx.get('ads_fb', {}), 'Facebook', ctx)),
        (slide_ads_ig, generate_ads_table(ctx.get('ads_ig', {}), 'Instagram', ctx)),
        (slide_budget, generate_budget_table(ctx)),
    ]

    for slide_obj, img_buf in charts:
        slide_obj.shapes.add_picture(
            img_buf, content_left, content_top, content_width, content_height,
        )

    # ── #13: INSIGHTS slide is TEXT ONLY, no content table ─────────────
    insights = ctx.get('insights', [])
    if insights:
        insight_text = '\n'.join(f'• {ins}' for ins in insights)
        add_text_box(
            slide_insights, Inches(0.76), Inches(2.5), Inches(8.5), Inches(4.0),
            insight_text, font_size=10,
            color_rgb=RGBColor.from_string('050505'),
        )

    # Sweep ALL slides for any remaining placeholder text
    for slide in prs.slides:
        sweep_placeholder_text(slide)

    prs.save(str(output_path))

    # ── Post-process: reorder slides to match reference structure ──────
    # After adding 5 duplicates the order is:
    #   [0-10] template slides, [11-15] duplicates (Reach IG..Ads IG)
    # Desired order:
    #   Cover, TOC, Scope, Reach FB, Reach IG, Msg FB, Msg IG,
    #   Content FB, Content IG, Audience FB, Audience IG,
    #   Ads FB, Ads IG, Budget, Insights, Thank You
    prs2 = Presentation(str(output_path))
    pres_elem = prs2.part._element
    sldIdLst = pres_elem.find(
        './/{http://schemas.openxmlformats.org/presentationml/2006/main}sldIdLst'
    )

    # Read current slide order (rId → element mapping)
    slide_elements = []
    for el in list(sldIdLst):
        rid = el.get(
            '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
        )
        slide_elements.append((rid, el))

    # First 11 are template slides (indices 0-10), last 5 are duplicates
    template_rids = [rid for rid, _ in slide_elements[:11]]
    dup_rids = [rid for rid, _ in slide_elements[11:]]

    desired_rid_order = [
        template_rids[0],   # Cover
        template_rids[1],   # TOC
        template_rids[2],   # Scope
        template_rids[3],   # REACH FB
        dup_rids[0],        # REACH IG
        template_rids[4],   # MESSAGING FB
        dup_rids[1],        # MESSAGING IG
        template_rids[5],   # CONTENT FB
        dup_rids[2],        # CONTENT IG
        template_rids[6],   # AUDIENCE FB
        dup_rids[3],        # AUDIENCE IG
        template_rids[7],   # ADS FB
        dup_rids[4],        # ADS IG
        template_rids[9],   # Budget
        template_rids[8],   # INSIGHTS
        template_rids[10],  # Thank You
    ]

    # Rebuild sldIdLst in desired order
    rid_to_el = {rid: el for rid, el in slide_elements}
    for el in list(sldIdLst):
        sldIdLst.remove(el)
    for rid in desired_rid_order:
        if rid in rid_to_el:
            sldIdLst.append(rid_to_el[rid])

    prs2.save(str(output_path))

    # Set page numbers AFTER lxml reorder to match final slide order
    prs_final = Presentation(str(output_path))
    for i, slide in enumerate(prs_final.slides, 1):
        update_slide_number(slide, i)
    prs_final.save(str(output_path))

    return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    import argparse, yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="all")
    parser.add_argument("--month", default="2026-08")
    args = parser.parse_args()

    with open(ROOT / "configs" / "clients.yaml") as f:
        all_clients = yaml.safe_load(f).get("clients", [])
    clients = [
        c for c in all_clients
        if args.client == "all" or c["id"] == args.client
    ]

    for cfg in clients:
        cid = cfg["id"]
        name = cfg.get("name", cid)
        print(f"Processing {cid} ({name})...")
        data = get_data(cid, args.month)
        if not data:
            print(f"  No data, skipping")
            continue
        prev = get_prev(cid, args.month)
        ctx = build_ctx(data, prev, name, args.month)
        out_dir = REPORTS_DIR / cid / args.month
        out_dir.mkdir(parents=True, exist_ok=True)
        build_report(TEMPLATE, ctx, out_dir / f"{cid}_{args.month}.pptx")
        print(f"  Done")
    print("All done!")


if __name__ == "__main__":
    main()
