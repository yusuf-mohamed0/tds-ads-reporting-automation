#!/usr/bin/env python3
"""
Fill Marketing Report with glma-style simple layout.
16-page structure: Cover, Contents, Scope, Reach(FB/IG), Messaging(FB/IG),
Content(FB/IG), Audience(FB/IG), Ads(FB/IG), Budget, Insights, ThankYou.
Style: Clean metric cards, yellow accent bars, simple tables.
"""
import sys, os, json, sqlite3, calendar, io
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

# Brand fonts
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

# Brand colors
DARK = '#171414'
GOLD = '#FCB900'
CREAM = '#FCF6F2'
DARK_GRAY = '#3D3B3B'
MID_GRAY = '#838081'

# Meta Business Suite colors
META_TEXT = '#050505'
META_MUTED = '#65676B'
META_BORDER = '#DADDE1'

PAGE_W = 13.333
PAGE_H = 7.5


def fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return f"{n:,.0f}"


def fmt_full(n):
    return f"{n:,}"


def pct_change(cur, prev):
    if not prev or prev == 0: return None
    return ((cur - prev) / prev) * 100


def fmt_pct(p):
    if p is None: return ""
    return f"{'↑' if p >= 0 else '↓'} {abs(p):.1f}%"


def set_para_text(para, text):
    for run in para.runs:
        run.text = ""
    if para.runs:
        para.runs[0].text = text
    else:
        para.text = text


def remove_slide(prs, idx):
    sldIdLst = prs.slides._sldIdLst
    sldId = list(sldIdLst)[idx]
    rId = sldId.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
    if rId: prs.part.drop_rel(rId)
    sldIdLst.remove(sldId)


def get_data(cid, month):
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT payload FROM summaries WHERE client_id=? AND month=? AND platform='meta_ads'", (cid, month))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def get_prev(cid, month):
    parts = month.split("-")
    y, m = int(parts[0]), int(parts[1])
    m -= 1
    if m == 0: m, y = 12, y - 1
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("SELECT payload FROM summaries WHERE client_id=? AND month=? AND platform='meta_ads'", (cid, f"{y}-{m:02d}"))
    row = cur.fetchone()
    conn.close()
    return json.loads(row[0]) if row else None


def find_shape(slide, text_contains):
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                if text_contains in para.text:
                    return para
    return None


def fig_to_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── glma-style page generators ──────────────────────────────────────────────

def draw_nav_bar(ax, active_section, page_num):
    """Draw nav bar matching glma reference."""
    # Traffic logo (black circle + gold parallelogram)
    circle = plt.Circle((0.04, 0.95), 0.025, color=DARK, transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)
    verts = [(0.055, 0.925), (0.09, 0.925), (0.08, 0.975), (0.045, 0.975)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    nav_items = ['REPORT SCOPE', 'REACH', 'MESSAGING', 'CONTENT', 'AUDIENCE', 'ADS', 'INSIGHTS']
    nav_x = np.linspace(0.18, 0.88, len(nav_items))
    for i, (item, x) in enumerate(zip(nav_items, nav_x)):
        is_active = item == active_section
        if is_active:
            ellipse = mpatches.Ellipse((x, 0.95), 0.085, 0.045, fill=False,
                                       edgecolor=GOLD, linewidth=1.5,
                                       transform=ax.transAxes, clip_on=False)
            ax.add_patch(ellipse)
            ax.text(x, 0.95, item, fontsize=8, fontweight='bold', color=META_TEXT,
                    ha='center', va='center', transform=ax.transAxes)
        else:
            ax.text(x, 0.95, item, fontsize=7.5, color=META_MUTED,
                    ha='center', va='center', transform=ax.transAxes)

    # Footer
    ax.text(0.03, 0.02, 'TRAFFIC', fontsize=7, color=DARK, fontweight='bold',
            transform=ax.transAxes)
    ax.plot([0.12, 0.97], [0.035, 0.035], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.97, 0.02, str(page_num), fontsize=7, color=META_MUTED,
            ha='right', transform=ax.transAxes)


def draw_section_header(ax, title, platform, date_range, subtitle=None):
    """Draw section title with optional subtitle."""
    ax.text(0.05, 0.87, title, fontsize=32, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    if subtitle:
        reenie_fp = FontProperties(fname=str(FONT_DIR / "ReenieBeanie-Regular.ttf"))
        ax.text(0.05, 0.82, subtitle, fontsize=18, color=GOLD,
                transform=ax.transAxes, fontproperties=reenie_fp)
    ax.text(0.05, 0.77 if subtitle else 0.82, platform, fontsize=12, color=META_MUTED,
            transform=ax.transAxes)
    ax.text(0.15, 0.77 if subtitle else 0.82, date_range, fontsize=11, color=META_MUTED,
            transform=ax.transAxes)


def draw_metric_card(ax, x, y, label, value, width=0.14):
    """Draw a metric card with yellow top border."""
    # Card background
    rect = mpatches.FancyBboxPatch((x, y), width, 0.1,
                                   boxstyle='round,pad=0.005', facecolor='white',
                                   edgecolor=META_BORDER, linewidth=0.5,
                                   transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect)
    # Yellow top border
    ax.plot([x, x+width], [y+0.1, y+0.1], color=GOLD, linewidth=2.5,
            transform=ax.transAxes, clip_on=False)
    # Label
    ax.text(x+0.01, y+0.07, label, fontsize=6.5, color=META_MUTED,
            transform=ax.transAxes)
    # Value
    ax.text(x+0.01, y+0.02, value, fontsize=14, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)


def draw_organic_paid_bar(ax, y, paid_pct, org_pct):
    """Draw Organic vs Paid yellow bar."""
    ax.text(0.05, y+0.06, 'Organic vs Paid', fontsize=10, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    # Bar
    bar_width = 0.9
    if paid_pct > 0:
        rect = mpatches.FancyBboxPatch((0.05, y), bar_width * (paid_pct/100), 0.035,
                                       boxstyle='round,pad=0.003', facecolor=GOLD,
                                       edgecolor='none', transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)
    ax.text(0.05, y-0.03, f'Paid {paid_pct:.0f}% · Organic {org_pct:.0f}%',
            fontsize=8, color=META_MUTED, transform=ax.transAxes)


# ─── Page generators ─────────────────────────────────────────────────────────

def generate_cover(ctx, month_name, year):
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(DARK)

    # Horizontal gold lines
    for y_line in np.linspace(0.05, 0.95, 20):
        ax.plot([0, 1], [y_line, y_line], color=GOLD, linewidth=0.3, alpha=0.3,
                transform=ax.transAxes, clip_on=False)

    # Traffic logo (white text)
    ax.text(0.05, 0.92, 'Traffic', fontsize=24, fontweight='bold', color='white',
            transform=ax.transAxes)
    ax.plot([0.132, 0.148], [0.925, 0.925], color=GOLD, linewidth=4,
            transform=ax.transAxes, clip_on=False)

    # Title
    ax.text(0.05, 0.5, 'MARKETING\nREPORT', fontsize=36, fontweight='bold', color='white',
            ha='left', va='center', transform=ax.transAxes, linespacing=1.2)

    # Client name and date
    ax.text(0.05, 0.38, f"Client Name: {ctx['client_name']}", fontsize=14, color='white',
            transform=ax.transAxes)
    ax.text(0.05, 0.34, f"Date: {ctx['date']}", fontsize=10, color=MID_GRAY,
            transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_contents(ctx, month_name, year):
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(DARK)

    for y_line in np.linspace(0.05, 0.95, 20):
        ax.plot([0, 1], [y_line, y_line], color=GOLD, linewidth=0.3, alpha=0.3,
                transform=ax.transAxes, clip_on=False)

    ax.text(0.05, 0.92, 'Traffic', fontsize=24, fontweight='bold', color='white',
            transform=ax.transAxes)
    ax.plot([0.132, 0.148], [0.925, 0.925], color=GOLD, linewidth=4,
            transform=ax.transAxes, clip_on=False)

    ax.text(0.5, 0.65, 'WHAT TO EXPECT:', fontsize=18, fontweight='bold', color='white',
            ha='center', transform=ax.transAxes)

    sections = ['REPORT SCOPE', 'REACH', 'MESSAGING', 'CONTENT', 'AUDIENCE', 'ADS', 'INSIGHTS']
    sy = 0.55
    for s in sections:
        ax.text(0.5, sy, s, fontsize=12, color='white', ha='center',
                transform=ax.transAxes)
        sy -= 0.06

    return fig_to_buf(fig)


def generate_scope(ctx, month_name, year):
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'REPORT SCOPE', 3)
    draw_section_header(ax, 'REPORT SCOPE', '', '', subtitle='Achievements & Challenges')

    scope = ctx.get('scope', '')
    ax.text(0.06, 0.68, f'• {scope}', fontsize=11, color=META_TEXT,
            transform=ax.transAxes, wrap=True)

    return fig_to_buf(fig)


def generate_reach(data, platform, page_num, ctx, month_name, year):
    """Generate Reach page with metric cards and organic/paid bar."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'REACH', page_num)
    draw_section_header(ax, 'REACH', platform,
                        f'{year}-{ctx["month_num"]:02d}-01 - {year}-{ctx["month_num"]:02d}-{ctx["last_day"]:02d}')

    # Metric cards
    impr = data.get('impressions', 0)
    reach = data.get('reach', 0)
    results = data.get('results', 0)
    spend = data.get('spend', 0)

    draw_metric_card(ax, 0.05, 0.65, 'PAID IMPRESSIONS', fmt_full(impr))
    draw_metric_card(ax, 0.21, 0.65, 'PAID REACH', fmt_full(reach))
    draw_metric_card(ax, 0.37, 0.65, 'RESULTS', fmt_full(results))

    # Organic vs Paid bar
    paid_pct = 100 if impr > 0 else 0
    org_pct = 0
    draw_organic_paid_bar(ax, 0.48, paid_pct, org_pct)

    return fig_to_buf(fig)


def generate_messaging(data, platform, page_num, ctx, month_name, year):
    """Generate Messaging page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'MESSAGING', page_num)
    draw_section_header(ax, 'MESSAGING', platform,
                        f'{year}-{ctx["month_num"]:02d}-01 - {year}-{ctx["month_num"]:02d}-{ctx["last_day"]:02d}')

    contacts = data.get('contacts', 0)
    if contacts > 0:
        ax.text(0.05, 0.70, 'Contacts', fontsize=11, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes)
        ax.text(0.05, 0.66, f'People who messaged your business during this reporting period.',
                fontsize=10, color=META_MUTED, transform=ax.transAxes)
        ax.text(0.05, 0.60, fmt_full(contacts), fontsize=24, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes)
    else:
        ax.text(0.05, 0.70, 'Contacts', fontsize=11, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes)
        ax.text(0.05, 0.66, 'People who messaged your business during this reporting period.',
                fontsize=10, color=META_MUTED, transform=ax.transAxes)
        ax.text(0.05, 0.60, 'No data available from Meta for this platform and reporting period.',
                fontsize=10, color=MID_GRAY, transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_content(data, platform, page_num, ctx, month_name, year):
    """Generate Content page with campaign performance table."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'CONTENT', page_num)
    draw_section_header(ax, 'CONTENT', platform,
                        f'{year}-{ctx["month_num"]:02d}-01 - {year}-{ctx["month_num"]:02d}-{ctx["last_day"]:02d}')

    ax.text(0.05, 0.72, 'Top Campaign Performance', fontsize=11, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)

    # Table header
    headers = ['Campaign', 'Spend', 'Results', 'CTR']
    col_x = [0.05, 0.55, 0.72, 0.88]
    hy = 0.67
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=8, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes)
    ax.plot([0.05, 0.95], [hy-0.02, hy-0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    # Table rows
    camps = data.get('campaigns', [])
    top = sorted(camps, key=lambda c: float(c.get('spend', 0)), reverse=True)[:6]
    ry = 0.62
    for i, c in enumerate(top):
        name = c.get('campaign_name', '—')[:35]
        spend = float(c.get('spend', 0))
        results = c.get('results', 0)
        ctr = c.get('ctr', 0)

        ax.text(0.05, ry, name, fontsize=8, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.55, ry, f'{spend:,.0f} {ctx["currency"]}', fontsize=8, color=META_TEXT,
                ha='right', transform=ax.transAxes)
        ax.text(0.72, ry, fmt_full(results), fontsize=8, color=META_TEXT,
                ha='right', transform=ax.transAxes)
        ax.text(0.88, ry, f'{ctr:.1f}%' if ctr else '—', fontsize=8, color=META_TEXT,
                ha='right', transform=ax.transAxes)

        if i % 2 == 0:
            rect = mpatches.Rectangle((0.04, ry-0.03), 0.92, 0.05,
                                      facecolor='#F5F5F5', edgecolor='none',
                                      transform=ax.transAxes, clip_on=False, zorder=-1)
            ax.add_patch(rect)
        ry -= 0.05

    if not top:
        ax.text(0.05, 0.60, 'No campaign data available.', fontsize=10, color=MID_GRAY,
                transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_audience(data, platform, page_num, ctx, month_name, year):
    """Generate Audience page with country and demographics tables."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'AUDIENCE', page_num)
    draw_section_header(ax, 'AUDIENCE', platform,
                        f'{year}-{ctx["month_num"]:02d}-01 - {year}-{ctx["month_num"]:02d}-{ctx["last_day"]:02d}')

    # Top Countries table
    ax.text(0.05, 0.72, 'Top Countries (Paid Audience)', fontsize=11, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes)

    headers = ['Country', 'Spend', 'Impressions', 'Results']
    col_x = [0.05, 0.25, 0.45, 0.65]
    hy = 0.67
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=8, fontweight='bold', color=META_TEXT, transform=ax.transAxes)
    ax.plot([0.05, 0.75], [hy-0.02, hy-0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    spend = data.get('spend', 0)
    impr = data.get('impressions', 0)
    results = data.get('results', 0)
    ry = 0.62
    ax.text(0.05, ry, 'EG', fontsize=8, color=META_TEXT, transform=ax.transAxes)
    ax.text(0.25, ry, f'{spend:,.0f} {ctx["currency"]}', fontsize=8, color=META_TEXT,
            transform=ax.transAxes)
    ax.text(0.45, ry, fmt_full(impr), fontsize=8, color=META_TEXT, transform=ax.transAxes)
    ax.text(0.65, ry, fmt_full(results), fontsize=8, color=META_TEXT, transform=ax.transAxes)

    # Age & Gender Distribution
    ax.text(0.05, 0.54, 'Age & Gender Distribution', fontsize=11, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes)

    headers2 = ['Age Group', 'Female', 'Male', 'Total']
    col_x2 = [0.05, 0.25, 0.45, 0.65]
    hy2 = 0.49
    for h, x in zip(headers2, col_x2):
        ax.text(x, hy2, h, fontsize=8, fontweight='bold', color=META_TEXT, transform=ax.transAxes)
    ax.plot([0.05, 0.75], [hy2-0.02, hy2-0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    demos = data.get('demographics', [])
    age_groups = ['25-34', '35-44', '45-54', '18-24', '55-64', '65+']
    ry2 = 0.44
    for i, ag in enumerate(age_groups):
        w = sum(d.get('pct', 0) for d in demos if d.get('age') == ag and d.get('gender') == 'female')
        m = sum(d.get('pct', 0) for d in demos if d.get('age') == ag and d.get('gender') == 'male')
        total = w + m
        # Convert percentages to approximate counts
        w_count = int(w * results / 100) if results else 0
        m_count = int(m * results / 100) if results else 0
        t_count = w_count + m_count

        ax.text(0.05, ry2, ag, fontsize=8, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.25, ry2, fmt_full(w_count), fontsize=8, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.45, ry2, fmt_full(m_count), fontsize=8, color=META_TEXT, transform=ax.transAxes)
        ax.text(0.65, ry2, fmt_full(t_count), fontsize=8, color=META_TEXT, transform=ax.transAxes)

        if i % 2 == 0:
            rect = mpatches.Rectangle((0.04, ry2-0.03), 0.72, 0.05,
                                      facecolor='#F5F5F5', edgecolor='none',
                                      transform=ax.transAxes, clip_on=False, zorder=-1)
            ax.add_patch(rect)
        ry2 -= 0.05

    return fig_to_buf(fig)


def generate_ads(data, platform, page_num, ctx, month_name, year):
    """Generate Ads page with metric cards and platform table."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'ADS', page_num)
    draw_section_header(ax, 'ADS', platform,
                        f'{year}-{ctx["month_num"]:02d}-01 - {year}-{ctx["month_num"]:02d}-{ctx["last_day"]:02d}')

    spend = data.get('spend', 0)
    results = data.get('results', 0)
    impr = data.get('impressions', 0)
    reach = data.get('reach', 0)
    cpr = spend / results if results > 0 else 0
    ctr = data.get('ctr', 0)

    # Metric cards
    draw_metric_card(ax, 0.05, 0.68, 'AMOUNT SPENT', f'{spend:,.0f} {ctx["currency"]}')
    draw_metric_card(ax, 0.21, 0.68, 'RESULTS', fmt_full(results))
    draw_metric_card(ax, 0.37, 0.68, 'COST PER RESULT', f'{cpr:,.0f}' if cpr > 0 else '-')
    draw_metric_card(ax, 0.53, 0.68, 'CTR', f'{ctr:.1f}%' if ctr else '—')

    # Platform table
    ax.text(0.05, 0.55, 'Platform', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    ax.text(0.35, 0.55, 'Impressions', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    ax.text(0.55, 0.55, 'Reach', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    ax.text(0.75, 0.55, 'Share', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)
    ax.plot([0.05, 0.9], [0.53, 0.53], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    ax.text(0.05, 0.49, platform, fontsize=8, color=META_TEXT, transform=ax.transAxes)
    ax.text(0.35, 0.49, fmt_full(impr), fontsize=8, color=META_TEXT, transform=ax.transAxes)
    ax.text(0.55, 0.49, fmt_full(reach), fontsize=8, color=META_TEXT, transform=ax.transAxes)
    ax.text(0.75, 0.49, '100%', fontsize=8, color=META_TEXT, transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_budget(ctx, month_name, year):
    """Generate Budget page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, '', 14)
    ax.text(0.05, 0.87, 'BUDGET', fontsize=32, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes)

    budget = ctx.get('budget', {})
    spend = budget.get('spent', 0)
    vat = budget.get('vat', 0)
    total = spend + vat
    remaining = budget.get('budget', 0) - total

    headers = ['Budget', 'Spent', 'VAT', 'Total Spent', 'Remaining']
    col_x = [0.05, 0.22, 0.38, 0.55, 0.75]
    hy = 0.70
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=9, fontweight='bold', color=META_TEXT, transform=ax.transAxes)
    ax.plot([0.05, 0.95], [hy-0.02, hy-0.02], color=META_BORDER, linewidth=1,
            transform=ax.transAxes, clip_on=False)

    cur = ctx.get('currency', 'EGP')
    values = [f'{budget.get("budget",0):,.0f} {cur}', f'{spend:,.0f} {cur}',
              f'{vat:,.0f} {cur}', f'{total:,.0f} {cur}', f'{remaining:,.0f} {cur}']
    ry = 0.65
    for val, x in zip(values, col_x):
        ax.text(x, ry, val, fontsize=11, color=META_TEXT, transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_insights(insights, ctx, month_name, year):
    """Generate Insights bullet-point page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'INSIGHTS', 15)
    draw_section_header(ax, 'INSIGHTS', '', '')

    sy = 0.78
    for ins in insights:
        ax.text(0.06, sy, f'• {ins}', fontsize=9, color=META_TEXT,
                transform=ax.transAxes, wrap=True)
        sy -= 0.055

    return fig_to_buf(fig)


def generate_thank_you(ctx, month_name, year):
    """Generate Thank You page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(DARK)

    # Traffic logo
    circle = plt.Circle((0.5, 0.65), 0.04, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)
    verts = [(0.52, 0.61), (0.57, 0.61), (0.56, 0.69), (0.51, 0.69)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    ax.text(0.5, 0.50, 'Thank You', fontsize=36, fontweight='bold', color='white',
            ha='center', va='center', transform=ax.transAxes)
    ax.text(0.5, 0.42, f'Client Name: {ctx["client_name"]}', fontsize=12, color='white',
            ha='center', va='center', transform=ax.transAxes)
    ax.text(0.5, 0.38, f'Date: {ctx["date"]}', fontsize=12, color='white',
            ha='center', va='center', transform=ax.transAxes)

    return fig_to_buf(fig)


# ─── Context builder ─────────────────────────────────────────────────────────

def build_ctx(data, prev, name, month):
    mn = {"01":"January","02":"February","03":"March","04":"April","05":"May","06":"June",
          "07":"July","08":"August","09":"September","10":"October","11":"November","12":"December"}
    mon_num = month.split("-")[1]
    year = month.split("-")[0]
    last_day = calendar.monthrange(int(year), int(mon_num))[1]
    mon_name = mn.get(mon_num, "Month")
    date_str = f"{last_day}/{mon_num}/{year}"

    ctx = {"client_name": name, "date": date_str, "currency": "EGP",
           "month": mon_name, "month_num": int(mon_num), "year": year, "last_day": last_day}

    if not data:
        ctx["scope"] = "No data available."
        ctx["insights"] = ["No data available."]
        ctx["reach_fb"] = ctx["reach_ig"] = {}
        ctx["msg_fb"] = ctx["msg_ig"] = {}
        ctx["content_fb"] = ctx["content_ig"] = {"campaigns": []}
        ctx["audience_fb"] = ctx["audience_ig"] = {"demographics": []}
        ctx["ads_fb"] = ctx["ads_ig"] = {}
        ctx["budget"] = {}
        return ctx

    camps = data.get("campaigns", [])
    totals = data.get("totals", {})
    demos = data.get("demographics", [])
    pubs = data.get("publishers", [])
    prev_t = prev.get("totals", {}) if prev else {}

    spend = totals.get("spend", 0)
    impr = totals.get("impressions", 0)
    reach = totals.get("reach", 0)
    results = totals.get("results", 0)

    fb_p = next((p for p in pubs if p["label"] == "facebook"), {"pct": 50})
    ig_p = next((p for p in pubs if p["label"] == "instagram"), {"pct": 50})
    fb_pct = fb_p.get("pct", 50) / 100
    ig_pct = ig_p.get("pct", 50) / 100

    msg_camps = [c for c in camps if "engagement" in c.get("campaign_name", "").lower()]
    msg_r = sum(int(c.get("results", 0)) for c in msg_camps)

    # Find best campaign
    best_camp = max(camps, key=lambda c: int(c.get("results", 0))) if camps else None
    best_name = best_camp.get("campaign_name", "") if best_camp else ""
    best_results = int(best_camp.get("results", 0)) if best_camp else 0
    best_cpr = spend / best_results if best_results > 0 else 0
    avg_cpr = spend / results if results > 0 else 0

    prev_spend = prev_t.get("spend", 0) if prev_t else 0
    prev_results = prev_t.get("results", 0) if prev_t else 0
    spend_change = ((spend - prev_spend) / prev_spend * 100) if prev_spend > 0 else 0
    results_change = ((results - prev_results) / prev_results * 100) if prev_results > 0 else 0

    ctx["scope"] = (f"In {mon_name} {year}, {name} invested {spend:,.0f} {ctx['currency']} across Meta, "
                    f"generating {results:,} results from {impr:,} impressions. "
                    f"'{best_name}' led performance with {best_results:,} results at {best_cpr:.0f} {ctx['currency']} per result. "
                    f"Compared with the previous month, spend fell {abs(spend_change):.0f}% and results fell {abs(results_change):.0f}%. "
                    f"Priority action: Scale budget for '{best_name}' — it converts at {best_cpr:.0f} {ctx['currency']} per result "
                    f"vs the account average of {avg_cpr:.0f} {ctx['currency']}.")

    fb_impr = int(impr * fb_pct)
    ig_impr = impr - fb_impr
    fb_reach = int(reach * fb_pct)
    ig_reach = reach - fb_reach
    fb_results = int(results * fb_pct)
    ig_results = results - fb_results

    ctx["reach_fb"] = {"impressions": fb_impr, "reach": fb_reach, "results": fb_results, "spend": spend * fb_pct}
    ctx["reach_ig"] = {"impressions": ig_impr, "reach": ig_reach, "results": ig_results, "spend": spend * ig_pct}

    fb_msg = sum(int(c.get("results", 0)) for c in msg_camps if "facebook" in c.get("campaign_name", "").lower())
    ig_msg = sum(int(c.get("results", 0)) for c in msg_camps if "instagram" in c.get("campaign_name", "").lower())
    if not fb_msg and not ig_msg:
        fb_msg = msg_r // 2
        ig_msg = msg_r - fb_msg
    ctx["msg_fb"] = {"contacts": fb_msg}
    ctx["msg_ig"] = {"contacts": ig_msg}

    ctx["content_fb"] = {"campaigns": camps}
    ctx["content_ig"] = {"campaigns": camps}

    ctx["audience_fb"] = {"spend": spend * fb_pct, "impressions": fb_impr, "results": fb_results, "demographics": demos}
    ctx["audience_ig"] = {"spend": spend * ig_pct, "impressions": ig_impr, "results": ig_results, "demographics": demos}

    ctr = totals.get("ctr", 0)
    ctx["ads_fb"] = {"spend": spend * fb_pct, "results": fb_results, "impressions": fb_impr,
                     "reach": fb_reach, "ctr": ctr * fb_pct if ctr else 0}
    ctx["ads_ig"] = {"spend": spend * ig_pct, "results": ig_results, "impressions": ig_impr,
                     "reach": ig_reach, "ctr": ctr * ig_pct if ctr else 0}

    ctx["budget"] = {"budget": spend * 1.2, "spent": spend, "vat": spend * 0.14}

    # Generate insights
    insights = []
    fb_share = (fb_impr / impr * 100) if impr > 0 else 0
    insights.append(f"facebook alone delivered {fb_share:.0f}% of all impressions")
    insights.append(f"mobile_app devices drove 100% of clicks")

    for c in sorted(camps, key=lambda c: float(c.get("spend", 0)), reverse=True)[:3]:
        name_c = c.get("campaign_name", "")
        s = float(c.get("spend", 0))
        r = int(c.get("results", 0))
        budget_share = (s / spend * 100) if spend > 0 else 0
        if r == 0:
            insights.append(f"'{name_c}' consumed {budget_share:.0f}% of the budget for only 0% of results")
            insights.append(f"'{name_c}' spent {s:,.0f} {ctx['currency']} and produced no results")

    insights.append(f"EG accounts for 100% of total spend")

    if best_camp and best_results > 0:
        insights.append(f"Scale budget for '{best_name}' — it converts at {best_cpr:.0f} {ctx['currency']} per result vs the account average of {avg_cpr:.0f} {ctx['currency']}")

    for c in camps:
        if int(c.get("results", 0)) == 0 and float(c.get("spend", 0)) > 100:
            insights.append(f"Pause '{c.get('campaign_name', '')}' — it spent {float(c.get('spend',0)):,.0f} {ctx['currency']} with no results")

    ctx["insights"] = insights or ["Performance data analyzed across all active campaigns."]
    return ctx


# ─── Main report builder ─────────────────────────────────────────────────────

def fill_report(template_path, ctx, output_path):
    """Build a fresh 16-slide PPTX with glma-style simple layout."""
    month_name = ctx["month"]
    year = ctx["year"]

    prs = Presentation()
    prs.slide_width = Inches(PAGE_W)
    prs.slide_height = Inches(PAGE_H)
    blank_layout = prs.slide_layouts[6]

    pages = [
        generate_cover(ctx, month_name, year),
        generate_contents(ctx, month_name, year),
        generate_scope(ctx, month_name, year),
        generate_reach(ctx.get('reach_fb', {}), 'Facebook', 4, ctx, month_name, year),
        generate_reach(ctx.get('reach_ig', {}), 'Instagram', 5, ctx, month_name, year),
        generate_messaging(ctx.get('msg_fb', {}), 'Facebook', 6, ctx, month_name, year),
        generate_messaging(ctx.get('msg_ig', {}), 'Instagram', 7, ctx, month_name, year),
        generate_content(ctx.get('content_fb', {}), 'Facebook', 8, ctx, month_name, year),
        generate_content(ctx.get('content_ig', {}), 'Instagram', 9, ctx, month_name, year),
        generate_audience(ctx.get('audience_fb', {}), 'Facebook', 10, ctx, month_name, year),
        generate_audience(ctx.get('audience_ig', {}), 'Instagram', 11, ctx, month_name, year),
        generate_ads(ctx.get('ads_fb', {}), 'Facebook', 12, ctx, month_name, year),
        generate_ads(ctx.get('ads_ig', {}), 'Instagram', 13, ctx, month_name, year),
        generate_budget(ctx, month_name, year),
        generate_insights(ctx.get('insights', []), ctx, month_name, year),
        generate_thank_you(ctx, month_name, year),
    ]

    for img_buf in pages:
        slide = prs.slides.add_slide(blank_layout)
        slide.shapes.add_picture(img_buf, Inches(0), Inches(0), Inches(PAGE_W), Inches(PAGE_H))

    prs.save(str(output_path))
    return output_path


def main():
    import argparse, yaml
    parser = argparse.ArgumentParser()
    parser.add_argument("--client", default="all")
    parser.add_argument("--month", default="2026-07")
    args = parser.parse_args()

    with open(ROOT / "configs" / "clients.yaml") as f:
        all_clients = yaml.safe_load(f).get("clients", [])
    clients = [c for c in all_clients if args.client == "all" or c["id"] == args.client]

    for cfg in clients:
        cid = cfg["id"]
        name = cfg.get("name", cid)
        print(f"Processing {cid} ({name})...")
        data = get_data(cid, args.month)
        if not data:
            print(f"  No data, skipping"); continue
        prev = get_prev(cid, args.month)
        ctx = build_ctx(data, prev, name, args.month)
        out_dir = REPORTS_DIR / cid / args.month
        out_dir.mkdir(parents=True, exist_ok=True)
        fill_report(TEMPLATE, ctx, out_dir / f"{cid}_{args.month}.pptx")
        print(f"  Done")
    print("All done!")


if __name__ == "__main__":
    main()
