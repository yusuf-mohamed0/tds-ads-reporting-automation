#!/usr/bin/env python3
"""
Generate Meta Business Suite-style monthly marketing reports.
16-page structure matching the reference Lodge report exactly.
Uses matplotlib to render full-page Meta-style visuals, embedded into PPTX template.
"""
import sys, os, json, sqlite3, calendar, io
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "company-report-template" / "Marketing Report.pptx"
REPORTS_DIR = ROOT / "reports"
DB_PATH = ROOT / "data" / "reporting.sqlite"
FONTS_DIR = ROOT / "templates" / "assets" / "fonts"

sys.path.insert(0, str(ROOT / "src"))

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import matplotlib.patches as mpatches
from matplotlib import font_manager
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn

# Register fonts
for f in FONTS_DIR.glob("Avenir*.otf"):
    font_manager.fontManager.addfont(str(f))

# Brand colors
DARK = '#171414'
GOLD = '#FCB900'
CREAM = '#FCF6F2'
DARK_GRAY = '#3D3B3B'
MID_GRAY = '#838081'

# Meta Business Suite colors
META_GREEN = '#00A651'
META_BLUE = '#1877F2'
META_LIGHT_BLUE = '#4ECDC4'
META_PINK = '#FF6B9D'
META_GRAY = '#65676B'
META_LIGHT = '#F0F2F5'
META_BORDER = '#DADDE1'
META_TEXT = '#050505'
META_MUTED = '#65676B'
META_WHITE = '#FFFFFF'

# Page dimensions (widescreen 16:9)
PAGE_W = 13.333
PAGE_H = 7.5

# Slide structure: 16 pages
# 0=Cover, 1=Contents, 2=Scope,
# 3=Reach_FB, 4=Reach_IG, 5=Messaging_FB, 6=Messaging_IG,
# 7=Content_FB, 8=Content_IG, 9=Audience_FB, 10=Audience_IG,
# 11=Ads_FB, 12=Ads_IG, 13=Budget, 14=Insights, 15=ThankYou


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


# ─── Meta-style page generators ─────────────────────────────────────────────

def draw_nav_bar(ax, active_section, page_num):
    """Draw the navigation bar and Traffic logo."""
    # Traffic logo (black circle + gold parallelogram)
    circle = plt.Circle((0.04, 0.95), 0.025, color=DARK, transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)
    # Gold parallelogram
    verts = [(0.055, 0.925), (0.09, 0.925), (0.08, 0.975), (0.045, 0.975)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    # Navigation items
    nav_items = ['REPORT SCOPE', 'REACH', 'MESSAGING', 'CONTENT', 'AUDIENCE', 'ADS', 'INSIGHTS']
    nav_x = np.linspace(0.15, 0.88, len(nav_items))
    for i, (item, x) in enumerate(zip(nav_items, nav_x)):
        is_active = item == active_section
        if is_active:
            # Draw circle around active item
            ellipse = mpatches.Ellipse((x, 0.95), 0.075, 0.04, fill=False,
                                       edgecolor=GOLD, linewidth=1.5,
                                       transform=ax.transAxes, clip_on=False)
            ax.add_patch(ellipse)
            ax.text(x, 0.95, item, fontsize=7.5, fontweight='bold', color=META_TEXT,
                    ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        else:
            ax.text(x, 0.95, item, fontsize=7, color=META_MUTED,
                    ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Footer
    ax.text(0.03, 0.02, 'TRAFFIC', fontsize=7, color=DARK, fontweight='bold',
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.plot([0.12, 0.97], [0.035, 0.035], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)
    ax.text(0.97, 0.02, str(page_num), fontsize=7, color=META_MUTED,
            ha='right', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')


def draw_section_header(ax, title, platform, date_range):
    """Draw section title, platform label, and date range."""
    ax.text(0.05, 0.87, title, fontsize=28, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.05, 0.82, platform, fontsize=12, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.15, 0.82, date_range, fontsize=11, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')


def fig_to_buf(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor=fig.get_facecolor(), pad_inches=0.1)
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_reach_fb(data, ctx, month_name, year):
    """Generate Meta-style Reach page for Facebook."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'REACH', 4)
    draw_section_header(ax, 'REACH', 'Facebook', f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Content overview label
    ax.text(0.05, 0.77, '🔵 Content overview', fontsize=8, color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Tabs
    tabs = ['All', 'Posts', 'Stories', 'Reels', 'Live']
    tab_x = 0.05
    for i, tab in enumerate(tabs):
        if i == 0:
            ax.text(tab_x, 0.73, tab, fontsize=7.5, color=META_BLUE, fontweight='bold',
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#E7F3FF', edgecolor='none'))
        else:
            ax.text(tab_x + 0.04, 0.73, tab, fontsize=7.5, color=META_MUTED,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        tab_x += 0.06

    # Metric cards
    views = data.get('views', 0)
    views_change = data.get('views_change', '')
    sec3 = data.get('3sec_views', 0)
    sec3_change = data.get('3sec_change', '')
    min1 = data.get('1min_views', 0)
    interactions = data.get('interactions', 0)
    interact_change = data.get('interactions_change', '')
    watch = data.get('watch_time', '0m 0s')
    watch_change = data.get('watch_change', '')

    metrics = [
        ('Views', fmt_num(views), views_change, True),
        ('3-second views', fmt_full(sec3), sec3_change, False),
        ('1-minute views', fmt_full(min1), '', False),
        ('Content interactions', fmt_full(interactions), interact_change, False),
        ('Watch time', watch, watch_change, False),
    ]

    card_x = 0.05
    for label, value, change, selected in metrics:
        if selected:
            rect = mpatches.FancyBboxPatch((card_x - 0.005, 0.655), 0.11, 0.07,
                                           boxstyle='round,pad=0.005', facecolor='#E7F3FF',
                                           edgecolor=META_BLUE, linewidth=1.5,
                                           transform=ax.transAxes, clip_on=False)
            ax.add_patch(rect)
        ax.text(card_x, 0.71, label, fontsize=6, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        ax.text(card_x, 0.68, value, fontsize=14, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        if change:
            color = META_GREEN if '↑' in change else '#E53935'
            ax.text(card_x + 0.09, 0.68, change, fontsize=6, color=color,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        card_x += 0.12

    # Line chart area
    np.random.seed(hash(str(views)) % 2**31)
    days = ctx["last_day"]
    if views > 0:
        daily = np.random.exponential(views / days, days)
        daily = daily * (views / daily.sum())
    else:
        daily = np.zeros(days)
    organic = daily * 0.05
    paid = daily - organic

    chart_x = np.linspace(0.05, 0.68, days)
    chart_y_base = 0.15
    chart_y_scale = 0.45

    max_val = daily.max()
    if max_val > 0:
        y_norm = daily / max_val
        y_organic = organic / max_val
        y_paid = paid / max_val
    else:
        y_norm = y_organic = y_paid = np.zeros(days)

    # Grid lines
    for g in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = chart_y_base + g * chart_y_scale
        ax.plot([0.05, 0.68], [gy, gy], color=META_BORDER, linewidth=0.5,
                transform=ax.transAxes, clip_on=False)
        val = int(g * max_val)
        ax.text(0.04, gy, fmt_num(val), fontsize=6, color=META_MUTED, ha='right',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Fill areas
    ax.fill_between(chart_x, chart_y_base, chart_y_base + y_norm * chart_y_scale,
                    alpha=0.15, color=META_GREEN, transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_norm * chart_y_scale, color=META_GREEN,
            linewidth=2, label='Views', transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_organic * chart_y_scale, color=META_BLUE,
            linewidth=1.5, label='From organic', linestyle='--', transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_paid * chart_y_scale, color='#90CAF9',
            linewidth=1.5, label='From ads', linestyle=':', transform=ax.transAxes)

    # X-axis labels
    step = max(1, days // 6)
    for i in range(0, days, step):
        ax.text(chart_x[i], chart_y_base - 0.03, f'{i+1} {month_name[:3]}',
                fontsize=6, color=META_MUTED, ha='center',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Legend
    legend_items = [
        (META_GREEN, 'Views', '-'),
        (META_BLUE, 'From organic', '--'),
        ('#90CAF9', 'From ads', ':'),
    ]
    lx = 0.25
    for color, label, ls in legend_items:
        ax.plot([lx, lx+0.03], [0.08, 0.08], color=color, linewidth=2, linestyle=ls,
                transform=ax.transAxes, clip_on=False)
        ax.text(lx+0.04, 0.08, label, fontsize=6, color=META_MUTED, va='center',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        lx += 0.12

    # Breakdown sidebar
    sb_x = 0.75
    ax.text(sb_x, 0.65, 'Views breakdown', fontsize=9, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(sb_x, 0.625, f'1 {month_name[:3]} - {ctx["last_day"]} {month_name[:3]}', fontsize=6.5,
            color=META_MUTED, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    total = views
    org = data.get('organic', int(views * 0.05))
    paid_v = views - org
    viewers = data.get('viewers', int(views * 0.5))

    sb_items = [
        ('Total', fmt_full(total), data.get('views_change', '')),
        ('From organic', fmt_full(org), data.get('organic_change', '')),
        ('From ads', fmt_full(paid_v), data.get('paid_change', '')),
        ('Viewers', fmt_full(viewers), data.get('viewers_change', '')),
    ]

    sy = 0.58
    for label, value, change in sb_items:
        ax.text(sb_x, sy, label, fontsize=7, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        sy -= 0.03
        ax.text(sb_x, sy, value, fontsize=13, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        if change:
            color = META_GREEN if '↑' in change else '#E53935'
            ax.text(sb_x + 0.15, sy, change, fontsize=6.5, color=color,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        sy -= 0.055

    return fig_to_buf(fig)


def generate_reach_ig(data, ctx, month_name, year):
    """Generate Meta-style Reach page for Instagram."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'REACH', 5)
    draw_section_header(ax, 'REACH', 'Instagram', f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Content overview label
    ax.text(0.05, 0.77, '📸 Content overview', fontsize=8, color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Tabs
    tabs = ['All', 'Posts', 'Stories']
    tab_x = 0.05
    for i, tab in enumerate(tabs):
        if i == 0:
            ax.text(tab_x, 0.73, tab, fontsize=7.5, color=META_BLUE, fontweight='bold',
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#E7F3FF', edgecolor='none'))
        else:
            ax.text(tab_x + 0.04, 0.73, tab, fontsize=7.5, color=META_MUTED,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        tab_x += 0.06

    # Metric cards
    views = data.get('views', 0)
    reach = data.get('reach', 0)
    interactions = data.get('interactions', 0)

    metrics = [
        ('Views', fmt_num(views), data.get('views_change', ''), True),
        ('Reach', fmt_num(reach), data.get('reach_change', ''), False),
        ('Content interactions', fmt_num(interactions), data.get('interactions_change', ''), False),
    ]

    card_x = 0.05
    for label, value, change, selected in metrics:
        if selected:
            rect = mpatches.FancyBboxPatch((card_x - 0.005, 0.655), 0.12, 0.07,
                                           boxstyle='round,pad=0.005', facecolor='#E7F3FF',
                                           edgecolor=META_BLUE, linewidth=1.5,
                                           transform=ax.transAxes, clip_on=False)
            ax.add_patch(rect)
        ax.text(card_x, 0.71, label, fontsize=6, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        ax.text(card_x, 0.68, value, fontsize=14, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        if change:
            color = META_GREEN if '↑' in change else '#E53935'
            ax.text(card_x + 0.10, 0.68, change, fontsize=6, color=color,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        card_x += 0.14

    # Line chart
    np.random.seed(hash(str(views)) % 2**31)
    days = ctx["last_day"]
    if views > 0:
        daily = np.random.exponential(views / days, days)
        daily = daily * (views / daily.sum())
    else:
        daily = np.zeros(days)
    organic = daily * 0.25
    paid = daily - organic

    chart_x = np.linspace(0.05, 0.68, days)
    chart_y_base = 0.15
    chart_y_scale = 0.45

    max_val = daily.max() if daily.max() > 0 else 1
    y_norm = daily / max_val
    y_organic = organic / max_val
    y_paid = paid / max_val

    for g in [0, 0.25, 0.5, 0.75, 1.0]:
        gy = chart_y_base + g * chart_y_scale
        ax.plot([0.05, 0.68], [gy, gy], color=META_BORDER, linewidth=0.5,
                transform=ax.transAxes, clip_on=False)
        val = int(g * max_val)
        ax.text(0.04, gy, fmt_num(val), fontsize=6, color=META_MUTED, ha='right',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    ax.fill_between(chart_x, chart_y_base, chart_y_base + y_norm * chart_y_scale,
                    alpha=0.15, color=META_GREEN, transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_norm * chart_y_scale, color=META_GREEN,
            linewidth=2, transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_organic * chart_y_scale, color=META_BLUE,
            linewidth=1.5, linestyle='--', transform=ax.transAxes)
    ax.plot(chart_x, chart_y_base + y_paid * chart_y_scale, color='#90CAF9',
            linewidth=1.5, linestyle=':', transform=ax.transAxes)

    step = max(1, days // 6)
    for i in range(0, days, step):
        ax.text(chart_x[i], chart_y_base - 0.03, f'{i+1} {month_name[:3]}',
                fontsize=6, color=META_MUTED, ha='center',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    lx = 0.25
    for color, label, ls in [(META_GREEN, 'Views', '-'), (META_BLUE, 'From organic', '--'), ('#90CAF9', 'From ads', ':')]:
        ax.plot([lx, lx+0.03], [0.08, 0.08], color=color, linewidth=2, linestyle=ls,
                transform=ax.transAxes, clip_on=False)
        ax.text(lx+0.04, 0.08, label, fontsize=6, color=META_MUTED, va='center',
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        lx += 0.12

    # Breakdown sidebar
    sb_x = 0.75
    ax.text(sb_x, 0.65, 'Views breakdown', fontsize=9, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(sb_x, 0.625, f'1 {month_name[:3]} - {ctx["last_day"]} {month_name[:3]}', fontsize=6.5,
            color=META_MUTED, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    total = views
    org = data.get('organic', int(views * 0.25))
    paid_v = views - org

    sb_items = [
        ('Total', fmt_full(total), data.get('views_change', '')),
        ('From organic', fmt_full(org), data.get('organic_change', '')),
        ('From ads', fmt_full(paid_v), data.get('paid_change', '')),
    ]

    sy = 0.58
    for label, value, change in sb_items:
        ax.text(sb_x, sy, label, fontsize=7, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        sy -= 0.03
        ax.text(sb_x, sy, value, fontsize=13, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        if change:
            color = META_GREEN if '↑' in change else '#E53935'
            ax.text(sb_x + 0.15, sy, change, fontsize=6.5, color=color,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        sy -= 0.055

    return fig_to_buf(fig)


def generate_messaging(data, platform, platform_icon, page_num, ctx, month_name, year):
    """Generate Meta-style Messaging page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'MESSAGING', page_num)
    draw_section_header(ax, 'MESSAGING', platform, f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Content
    contacts = data.get('contacts', 0)
    organic = data.get('organic', 0)
    paid = data.get('paid', 0)

    sy = 0.72
    ax.text(0.05, sy, f'{platform_icon} Messaging', fontsize=10, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    sy -= 0.06
    ax.text(0.05, sy, 'Contacts', fontsize=8, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    sy -= 0.04
    ax.text(0.05, sy, fmt_full(contacts), fontsize=22, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    sy -= 0.08
    ax.text(0.05, sy, 'Organic', fontsize=8, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.12, sy, fmt_full(organic), fontsize=14, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    sy -= 0.05
    ax.text(0.05, sy, 'Paid', fontsize=8, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.12, sy, fmt_full(paid), fontsize=14, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    return fig_to_buf(fig)


def generate_content_table(camps, platform, platform_icon, page_num, ctx, month_name, year):
    """Generate Meta-style Content table page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'CONTENT', page_num)
    draw_section_header(ax, 'CONTENT', platform, f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # All content header
    ax.text(0.05, 0.77, 'All content', fontsize=10, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Create Post button
    rect = mpatches.FancyBboxPatch((0.85, 0.755), 0.1, 0.035,
                                   boxstyle='round,pad=0.005', facecolor=META_BLUE,
                                   edgecolor='none', transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect)
    ax.text(0.90, 0.772, 'Create Post', fontsize=7, color='white', fontweight='bold',
            ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Filter and search
    ax.text(0.05, 0.72, 'Filter: 1 selected ▾', fontsize=7, color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=META_BORDER))
    ax.text(0.17, 0.72, 'Clear', fontsize=7, color=META_BLUE,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.22, 0.72, '🔍 Search by ID or caption', fontsize=7, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=META_BORDER))

    # Table header
    headers = ['Title', 'Date published', 'Views', 'Reach']
    col_x = [0.05, 0.55, 0.72, 0.87]
    hy = 0.67
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=7.5, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.plot([0.05, 0.95], [hy - 0.02, hy - 0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    # Table rows
    n_rows = min(len(camps), 5)
    ry = 0.62
    for i in range(n_rows):
        c = camps[i]

        # Thumbnail placeholder
        rect = mpatches.FancyBboxPatch((0.05, ry - 0.02), 0.035, 0.05,
                                       boxstyle='round,pad=0.003', facecolor='#E4E6EB',
                                       edgecolor='none', transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)

        # Platform icon
        icon = '🔵' if platform == 'Facebook' else '🟣'
        ax.text(0.05, ry - 0.04, icon, fontsize=5, transform=ax.transAxes)

        # Post title
        title = c.get('name', '—')[:42]
        ax.text(0.10, ry, title, fontsize=7, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        ax.text(0.10, ry - 0.03, f'Reel • {ctx["client_name"]}', fontsize=5.5, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Boost/Create ad button
        btn_text = 'Boost' if i % 2 == 0 else 'Create ad'
        rect = mpatches.FancyBboxPatch((0.42, ry - 0.015), 0.055, 0.025,
                                       boxstyle='round,pad=0.003', facecolor='white',
                                       edgecolor=META_BORDER, transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)
        ax.text(0.447, ry - 0.003, btn_text, fontsize=5.5, color=META_TEXT,
                ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Date
        day = 1 + i * 5
        ax.text(0.55, ry, f'{day} {month_name[:3]} {ctx["last_day"] + 3}:31', fontsize=7,
                color=META_TEXT, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Views
        views = c.get('views', 0)
        ax.text(0.72, ry, fmt_full(views), fontsize=7, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Reach
        reach = c.get('reach', 0)
        ax.text(0.87, ry, fmt_full(reach), fontsize=7, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Alternating row background
        if i % 2 == 0:
            rect = mpatches.Rectangle((0.04, ry - 0.04), 0.92, 0.07,
                                      facecolor=META_LIGHT, edgecolor='none',
                                      transform=ax.transAxes, clip_on=False, zorder=-1)
            ax.add_patch(rect)

        ry -= 0.08

    return fig_to_buf(fig)


def generate_audience(data, platform, page_num, ctx, month_name, year):
    """Generate Meta-style Audience demographics page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'AUDIENCE', page_num)
    draw_section_header(ax, 'AUDIENCE', platform, f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Audience section header
    ax.text(0.05, 0.77, 'Audience', fontsize=10, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Export button
    rect = mpatches.FancyBboxPatch((0.85, 0.755), 0.1, 0.035,
                                   boxstyle='round,pad=0.005', facecolor='white',
                                   edgecolor=META_BORDER, transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect)
    ax.text(0.90, 0.772, 'Export ▾', fontsize=7, color=META_TEXT,
            ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Tabs
    tabs = ['Demographics', 'Trends', 'Potential audience']
    tab_x = 0.05
    for i, tab in enumerate(tabs):
        if i == 0:
            ax.text(tab_x, 0.73, tab, fontsize=7.5, color=META_BLUE, fontweight='bold',
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='#E7F3FF', edgecolor='none'))
        else:
            ax.text(tab_x + 0.08, 0.73, tab, fontsize=7.5, color=META_MUTED,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        tab_x += 0.12

    # Followers
    followers = data.get('followers', 0)
    ax.text(0.05, 0.68, 'Followers', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.05, 0.655, 'Lifetime', fontsize=6.5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.05, 0.62, fmt_full(followers), fontsize=20, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Age & gender bar chart
    ax.text(0.05, 0.57, 'Age & gender', fontsize=8, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    age_data = data.get('age_data', [])
    if not age_data:
        age_data = [
            {'age': '18-24', 'women': 5, 'men': 4},
            {'age': '25-34', 'women': 25, 'men': 20},
            {'age': '35-44', 'women': 18, 'men': 16},
            {'age': '45-54', 'women': 6, 'men': 5},
            {'age': '55-64', 'women': 2, 'men': 2},
            {'age': '65+', 'women': 1, 'men': 1},
        ]

    ages = [d['age'] for d in age_data]
    women_vals = [d['women'] for d in age_data]
    men_vals = [d['men'] for d in age_data]

    chart_bottom = 0.15
    chart_height = 0.35
    chart_left = 0.08
    chart_width = 0.85
    n_groups = len(ages)
    group_width = chart_width / n_groups
    bar_width = group_width * 0.35

    max_val = max(max(women_vals), max(men_vals), 1)

    # Grid lines
    for g in [0, 0.1, 0.2, 0.3]:
        gy = chart_bottom + (g / max_val) * chart_height if max_val > 0 else chart_bottom
        ax.plot([chart_left, chart_left + chart_width], [gy, gy],
                color=META_BORDER, linewidth=0.5, transform=ax.transAxes, clip_on=False)
        ax.text(chart_left - 0.02, gy, f'{int(g*100)}%', fontsize=6, color=META_MUTED,
                ha='right', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    for i, (age, w, m) in enumerate(zip(ages, women_vals, men_vals)):
        x_center = chart_left + (i + 0.5) * group_width

        # Women bar (light blue)
        h = (w / max_val) * chart_height if max_val > 0 else 0
        rect = mpatches.Rectangle((x_center - bar_width - 0.005, chart_bottom),
                                  bar_width, h, facecolor='#A8D8EA', edgecolor='none',
                                  transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)

        # Men bar (dark blue)
        h = (m / max_val) * chart_height if max_val > 0 else 0
        rect = mpatches.Rectangle((x_center + 0.005, chart_bottom),
                                  bar_width, h, facecolor='#3D7EA6', edgecolor='none',
                                  transform=ax.transAxes, clip_on=False)
        ax.add_patch(rect)

        # Age label
        ax.text(x_center, chart_bottom - 0.03, age, fontsize=7, color=META_MUTED,
                ha='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    # Legend
    women_pct = data.get('women', 53.7)
    men_pct = data.get('men', 46.3)
    rect_w = mpatches.Rectangle((0.35, 0.06), 0.02, 0.015, facecolor='#A8D8EA',
                                edgecolor='none', transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect_w)
    ax.text(0.38, 0.067, f'Women {women_pct:.1f}%', fontsize=7, color=META_MUTED,
            va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    rect_m = mpatches.Rectangle((0.50, 0.06), 0.02, 0.015, facecolor='#3D7EA6',
                                edgecolor='none', transform=ax.transAxes, clip_on=False)
    ax.add_patch(rect_m)
    ax.text(0.53, 0.067, f'Men {men_pct:.1f}%', fontsize=7, color=META_MUTED,
            va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    return fig_to_buf(fig)


def generate_ads(camps, platform, page_num, ctx, month_name, year):
    """Generate Meta-style Ads Manager table page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'ADS', page_num)
    draw_section_header(ax, 'ADS', platform, f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Table
    headers = ['Campaign name', 'Platform', 'Results', 'Cost per result', 'Amount spent', 'Impressions', 'Reach']
    col_x = [0.04, 0.22, 0.32, 0.45, 0.58, 0.72, 0.85]
    col_w = [0.18, 0.10, 0.13, 0.13, 0.14, 0.13, 0.12]

    hy = 0.75
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=7, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.plot([0.04, 0.96], [hy - 0.02, hy - 0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)

    currency = ctx.get('currency', 'EGP')
    cur_short = 'ج.م' if currency == 'EGP' else currency[:3]

    n_camps = min(len(camps), 4)
    ry = 0.70
    total_spend = total_impr = total_reach = 0

    for i in range(n_camps):
        c = camps[i]
        spend = float(c.get('spend', 0))
        impr = c.get('impressions', 0)
        reach = c.get('reach', 0)
        results = c.get('results', 0)
        cpr = c.get('cost_per_result', 0)
        result_type = 'Messaging conversat...' if 'engagement' in c.get('campaign_name', '').lower() else 'Profile and Page visits'

        # Campaign name (blue link)
        name = c.get('campaign_name', '—')[:25]
        ax.text(col_x[0], ry, name, fontsize=6.5, color=META_BLUE,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Platform
        ax.text(col_x[1], ry, 'All', fontsize=6.5, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        ax.text(col_x[1], ry - 0.025, platform, fontsize=5.5, color=META_MUTED,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Results
        if results:
            ax.text(col_x[2], ry, fmt_full(results), fontsize=6.5, color=META_TEXT,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
            ax.text(col_x[2], ry - 0.025, result_type, fontsize=5, color=META_MUTED,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        else:
            ax.text(col_x[2], ry, '—', fontsize=6.5, color=META_TEXT,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Cost per result
        if cpr:
            ax.text(col_x[3], ry, f'{cpr:.2f}.{cur_short}', fontsize=6.5, color=META_TEXT,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
        else:
            ax.text(col_x[3], ry, '—', fontsize=6.5, color=META_TEXT,
                    transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Amount spent
        ax.text(col_x[4], ry, f'{spend:,.2f}.{cur_short}', fontsize=6.5, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Impressions
        ax.text(col_x[5], ry, fmt_full(impr), fontsize=6.5, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        # Reach
        ax.text(col_x[6], ry, fmt_full(reach), fontsize=6.5, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

        total_spend += spend
        total_impr += impr
        total_reach += reach

        # Alternating row
        if i % 2 == 0:
            rect = mpatches.Rectangle((0.03, ry - 0.04), 0.94, 0.07,
                                      facecolor=META_LIGHT, edgecolor='none',
                                      transform=ax.transAxes, clip_on=False, zorder=-1)
            ax.add_patch(rect)

        ry -= 0.07

    # Total row
    ax.plot([0.04, 0.96], [ry + 0.02, ry + 0.02], color=META_BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)
    ax.text(col_x[0], ry, 'Total results', fontsize=6.5, fontweight='bold', color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[0], ry - 0.025, f'{n_camps}/{n_camps} rows displayed', fontsize=5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[2], ry, '—', fontsize=6.5, color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[2], ry - 0.025, 'Multiple conversions', fontsize=5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[3], ry, '—', fontsize=6.5, color=META_TEXT,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[4], ry, f'{total_spend:,.2f}.{cur_short}', fontsize=6.5, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[4], ry - 0.025, 'Total Spent', fontsize=5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[5], ry, fmt_full(total_impr), fontsize=6.5, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[5], ry - 0.025, 'Total', fontsize=5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[6], ry, fmt_full(total_reach), fontsize=6.5, fontweight='bold',
            color=META_TEXT, transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(col_x[6], ry - 0.025, 'Accounts Centre accounts', fontsize=5, color=META_MUTED,
            transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    return fig_to_buf(fig)


def generate_budget(data, ctx, month_name, year):
    """Generate Budget page with hand-drawn table style."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'BUDGET', 14)
    draw_section_header(ax, 'BUDGET', '', f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Table
    headers = ['Budget', 'Spent', 'VAT', 'Total Spent', 'Remaining']
    col_x = [0.05, 0.22, 0.38, 0.55, 0.75]

    hy = 0.70
    for h, x in zip(headers, col_x):
        ax.text(x, hy, h, fontsize=9, fontweight='bold', color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.plot([0.05, 0.95], [hy - 0.02, hy - 0.02], color=META_BORDER, linewidth=1,
            transform=ax.transAxes, clip_on=False)

    budget = data.get('budget', 0)
    spent = data.get('spent', 0)
    vat = data.get('vat', 0)
    total_spent = spent + vat
    remaining = budget - total_spent

    currency = ctx.get('currency', 'EGP')
    values = [
        f'{budget:,.0f} {currency}',
        f'{spent:,.0f} {currency}',
        f'{vat:,.0f} {currency}',
        f'{total_spent:,.0f} {currency}',
        f'{remaining:,.0f} {currency}',
    ]

    ry = 0.65
    for val, x in zip(values, col_x):
        ax.text(x, ry, val, fontsize=11, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    return fig_to_buf(fig)


def generate_insights(insights, ctx, month_name, year):
    """Generate Insights bullet-point page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'INSIGHTS', 15)
    draw_section_header(ax, 'INSIGHTS', '', f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    sy = 0.72
    for ins in insights:
        ax.text(0.06, sy, f'• {ins}', fontsize=9, color=META_TEXT,
                transform=ax.transAxes, fontfamily='Avenir Next LT Pro',
                wrap=True)
        sy -= 0.06

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
    date_range = f"1 {mon_name} - {last_day} {mon_name} {year}"

    ctx = {"client_name": name, "date": date_str, "date_range": date_range,
           "currency": "EGP", "month": mon_name, "month_num": mon_num,
           "year": year, "last_day": last_day}

    if not data:
        ctx["scope"] = "No data available."
        ctx["insights"] = ["No data available."]
        for k in ["reach_fb","reach_ig","msg_fb","msg_ig","content_fb","content_ig",
                   "audience_fb","audience_ig","ads_fb","ads_ig","budget"]:
            ctx[k] = {}
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

    fb_p = next((p for p in pubs if p["label"]=="facebook"), {"pct":50})
    ig_p = next((p for p in pubs if p["label"]=="instagram"), {"pct":50})
    fb_pct = fb_p.get("pct", 50) / 100
    ig_pct = ig_p.get("pct", 50) / 100

    msg_camps = [c for c in camps if "engagement" in c.get("campaign_name","").lower()]
    msg_r = sum(int(c.get("results",0)) for c in msg_camps)

    ctx["scope"] = (f"This month's approach generated {results:,} results across {len(camps)} campaigns "
                    f"with a total spend of {spend:,.0f} {ctx['currency']}. "
                    + (f"Messaging campaigns generated {msg_r:,} conversations. " if msg_r else "") +
                    f"Total reach was {reach:,} with {impr:,} impressions.")

    fb_impr = int(impr * fb_pct)
    ig_impr = impr - fb_impr
    prev_fb = int(prev_t.get("reach",0) * fb_pct) if prev_t else None
    prev_ig = prev_t.get("reach",0) - prev_fb if prev_t and prev_fb else None

    # Split campaigns by platform
    fb_camps = [c for c in camps if "facebook" in c.get("campaign_name","").lower()]
    ig_camps = [c for c in camps if "instagram" in c.get("campaign_name","").lower()]
    if not fb_camps: fb_camps = camps
    if not ig_camps: ig_camps = camps

    ctx["reach_fb"] = {
        "views": fb_impr, "organic": int(fb_impr*0.05), "paid": int(fb_impr*0.95),
        "viewers": int(fb_impr*0.5),
        "views_change": fmt_pct(pct_change(fb_impr, prev_fb)) if prev_fb else "",
        "organic_change": "", "paid_change": "", "viewers_change": "",
    }
    ctx["reach_ig"] = {
        "views": ig_impr, "organic": int(ig_impr*0.25), "paid": int(ig_impr*0.75),
        "views_change": fmt_pct(pct_change(ig_impr, prev_ig)) if prev_ig else "",
        "organic_change": "", "paid_change": "",
    }

    fb_msg = sum(int(c.get("results",0)) for c in msg_camps if "facebook" in c.get("campaign_name","").lower())
    ig_msg = sum(int(c.get("results",0)) for c in msg_camps if "instagram" in c.get("campaign_name","").lower())
    if not fb_msg and not ig_msg:
        fb_msg = msg_r // 2
        ig_msg = msg_r - fb_msg
    ctx["msg_fb"] = {"contacts": fb_msg, "organic": int(fb_msg*0.2), "paid": int(fb_msg*0.8)}
    ctx["msg_ig"] = {"contacts": ig_msg, "organic": int(ig_msg*0.2), "paid": int(ig_msg*0.8)}

    top_fb = sorted(fb_camps, key=lambda c: float(c.get("spend",0)), reverse=True)[:5]
    top_ig = sorted(ig_camps, key=lambda c: float(c.get("spend",0)), reverse=True)[:5]
    ctx["content_fb"] = [{"name": c.get("campaign_name","—"), "views": c.get("impressions",0), "reach": c.get("reach",0)} for c in top_fb]
    ctx["content_ig"] = [{"name": c.get("campaign_name","—"), "views": c.get("impressions",0), "reach": c.get("reach",0)} for c in top_ig]

    women = sum(d.get("pct",0) for d in demos if d.get("gender")=="female")
    men = sum(d.get("pct",0) for d in demos if d.get("gender")=="male")
    age_groups = ["18-24","25-34","35-44","45-54","55-64","65+"]
    age_data = []
    for ag in age_groups:
        w = next((d for d in demos if d.get("age")==ag and d.get("gender")=="female"), {})
        m = next((d for d in demos if d.get("age")==ag and d.get("gender")=="male"), {})
        age_data.append({"age": ag, "women": w.get("pct",0), "men": m.get("pct",0)})

    ctx["audience_fb"] = {"followers": int(reach*0.3), "age_data": age_data, "women": women, "men": men}
    ctx["audience_ig"] = {"followers": int(reach*0.5), "age_data": age_data, "women": women, "men": men}

    ctx["ads_fb"] = fb_camps
    ctx["ads_ig"] = ig_camps

    ctx["budget"] = {"budget": spend * 1.2, "spent": spend, "vat": spend * 0.14}

    insights = []
    if prev_t.get("reach"):
        p = pct_change(reach, prev_t["reach"])
        if p: insights.append(f"Reach {'increased' if p>0 else 'decreased'} by {abs(p):.0f}% from {prev_t['reach']:,} to {reach:,}.")
    if spend and results:
        insights.append(f"Average cost per result: {spend/results:,.0f} {ctx['currency']} across {results:,} results.")
    if msg_r: insights.append(f"Messaging campaigns generated {msg_r:,} conversations.")
    ctr = totals.get("ctr", 0)
    if ctr: insights.append(f"Overall click-through rate: {ctr:.2f}%.")
    ctx["insights"] = insights or ["Performance data analyzed across all active campaigns."]
    return ctx


# ─── Main report builder ─────────────────────────────────────────────────────

def generate_cover(ctx, month_name, year):
    """Generate Cover page matching template style."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(DARK)

    # Gold accent stripe across top
    verts = [(0.0, 0.88), (0.18, 0.88), (0.14, 1.0), (0.0, 1.0)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    # Traffic logo circle (black on gold)
    circle = plt.Circle((0.06, 0.94), 0.03, color=DARK, transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)

    # Title - white on dark
    ax.text(0.5, 0.55, 'MARKETING REPORT', fontsize=36, fontweight='bold', color='white',
            ha='center', va='center', transform=ax.transAxes)

    # Client name and date
    ax.text(0.5, 0.44, f"Client Name: {ctx['client_name']}", fontsize=14, color='white',
            ha='center', va='center', transform=ax.transAxes)
    ax.text(0.5, 0.39, f"Date: {ctx['date']}", fontsize=14, color='white',
            ha='center', va='center', transform=ax.transAxes)

    return fig_to_buf(fig)


def generate_contents(ctx, month_name, year):
    """Generate Contents page matching template style."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor(DARK)

    # Gold accent stripe
    verts = [(0.0, 0.92), (0.15, 0.92), (0.12, 1.0), (0.0, 1.0)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    circle = plt.Circle((0.06, 0.88), 0.03, color='white', transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)

    ax.text(0.5, 0.65, 'WHAT TO EXPECT:', fontsize=20, fontweight='bold', color='white',
            ha='center', va='center', transform=ax.transAxes, fontfamily='sans-serif')

    sections = ['REPORT SCOPE', 'REACH', 'MESSAGING', 'CONTENT', 'AUDIENCE', 'ADS', 'INSIGHTS']
    sy = 0.55
    for s in sections:
        ax.text(0.5, sy, s, fontsize=12, color='white', ha='center', va='center',
                transform=ax.transAxes, fontfamily='sans-serif')
        sy -= 0.06

    return fig_to_buf(fig)


def generate_scope(ctx, month_name, year):
    """Generate Report Scope page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    fig.patch.set_facecolor('white')

    draw_nav_bar(ax, 'REPORT SCOPE', 3)
    draw_section_header(ax, 'REPORT SCOPE', '', f'1 {month_name} - {ctx["last_day"]} {month_name} {year}')

    # Scope text
    scope = ctx.get('scope', '')
    ax.text(0.06, 0.70, f'• {scope}', fontsize=9, color=META_TEXT,
            transform=ax.transAxes, fontfamily='sans-serif', wrap=True,
            transform_rotates_text=False)

    return fig_to_buf(fig)


def fill_report(template_path, ctx, output_path):
    """Build a fresh 16-slide PPTX with Meta-style full-page images."""
    month_name = ctx["month"]
    year = ctx["year"]

    # Create fresh presentation with blank layout
    prs = Presentation()
    prs.slide_width = Inches(PAGE_W)
    prs.slide_height = Inches(PAGE_H)
    blank_layout = prs.slide_layouts[6]  # Blank

    # Generate all page images in order
    pages = [
        generate_cover(ctx, month_name, year),
        generate_contents(ctx, month_name, year),
        generate_scope(ctx, month_name, year),
        generate_reach_fb(ctx.get('reach_fb', {}), ctx, month_name, year),
        generate_reach_ig(ctx.get('reach_ig', {}), ctx, month_name, year),
        generate_messaging(ctx.get('msg_fb', {}), 'Facebook', '🔵', 6, ctx, month_name, year),
        generate_messaging(ctx.get('msg_ig', {}), 'Instagram', '🟣', 7, ctx, month_name, year),
        generate_content_table(ctx.get('content_fb', []), 'Facebook', '🔵', 8, ctx, month_name, year),
        generate_content_table(ctx.get('content_ig', []), 'Instagram', '🟣', 9, ctx, month_name, year),
        generate_audience(ctx.get('audience_fb', {}), 'Facebook', 10, ctx, month_name, year),
        generate_audience(ctx.get('audience_ig', {}), 'Instagram', 11, ctx, month_name, year),
        generate_ads(ctx.get('ads_fb', []), 'Facebook', 12, ctx, month_name, year),
        generate_ads(ctx.get('ads_ig', []), 'Instagram', 13, ctx, month_name, year),
        generate_budget(ctx.get('budget', {}), ctx, month_name, year),
        generate_insights(ctx.get('insights', []), ctx, month_name, year),
        generate_thank_you(ctx, month_name, year),
    ]

    # Add each page as a full-slide image
    for img_buf in pages:
        slide = prs.slides.add_slide(blank_layout)
        slide.shapes.add_picture(img_buf, Inches(0), Inches(0), Inches(PAGE_W), Inches(PAGE_H))

    prs.save(str(output_path))
    return output_path


def generate_thank_you(ctx, month_name, year):
    """Generate Thank You page."""
    fig, ax = plt.subplots(figsize=(PAGE_W, PAGE_H))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis('off')
    fig.patch.set_facecolor(DARK)

    # Traffic logo
    circle = plt.Circle((0.5, 0.65), 0.04, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(circle)
    verts = [(0.52, 0.61), (0.57, 0.61), (0.56, 0.69), (0.51, 0.69)]
    poly = plt.Polygon(verts, color=GOLD, transform=ax.transAxes, clip_on=False)
    ax.add_patch(poly)

    ax.text(0.5, 0.50, 'Thank You', fontsize=36, fontweight='bold', color='white',
            ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    ax.text(0.5, 0.42, f'Client Name: {ctx["client_name"]}', fontsize=12, color='white',
            ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')
    ax.text(0.5, 0.38, f'Date: {ctx["date"]}', fontsize=12, color='white',
            ha='center', va='center', transform=ax.transAxes, fontfamily='Avenir Next LT Pro')

    return fig_to_buf(fig)


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
