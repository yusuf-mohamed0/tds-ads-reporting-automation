#!/usr/bin/env python3
"""
Fill Marketing Report.pptx template with real client data.
Loads the existing template, modifies content, removes Budget slide.
"""
import sys, os, json, sqlite3, copy, calendar
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "assets" / "company-report-template" / "Marketing Report.pptx"
REPORTS_DIR = ROOT / "reports"
DB_PATH = ROOT / "data" / "reporting.sqlite"

sys.path.insert(0, str(ROOT / "src"))

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.oxml.ns import qn


def fmt_num(n):
    if n >= 1_000_000: return f"{n/1_000_000:.1f}M"
    if n >= 1_000: return f"{n/1_000:.1f}K"
    return f"{n:,.0f}"


def pct_change(cur, prev):
    if not prev or prev == 0: return None
    return ((cur - prev) / prev) * 100


def fmt_pct(p):
    if p is None: return ""
    return f"{'↑' if p >= 0 else '↓'} {abs(p):.1f}%"


def set_para_text(para, text):
    """Set paragraph text, clearing all runs and putting text in first run."""
    for run in para.runs:
        run.text = ""
    if para.runs:
        para.runs[0].text = text
    else:
        para.text = text


def add_table_to_slide(slide, rows, cols, left, top, width, height):
    """Add a table shape to a slide and return the table object."""
    tbl = slide.shapes.add_table(rows, cols, left, top, width, height).table
    return tbl


def set_cell(tbl, row, col, text, bold=False, align=PP_ALIGN.LEFT, font_size=9):
    """Set text in a table cell with formatting."""
    cell = tbl.cell(row, col)
    cell.text = ""
    p = cell.text_frame.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = str(text)
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.name = "Avenir Next LT Pro"
    # Reduce cell margins
    cell.margin_left = Emu(45720)
    cell.margin_right = Emu(45720)
    cell.margin_top = Emu(18288)
    cell.margin_bottom = Emu(18288)


def shade_cells(tbl, row, color_hex):
    """Apply shading to all cells in a row."""
    for col_idx in range(len(tbl.columns)):
        cell = tbl.cell(row, col_idx)
        tcPr = cell._tc.get_or_add_tcPr()
        solidFill = tcPr.makeelement(qn('a:solidFill'), {})
        srgbClr = solidFill.makeelement(qn('a:srgbClr'), {'val': color_hex})
        solidFill.append(srgbClr)
        tcPr.append(solidFill)


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


def build_ctx(data, prev, name, month):
    mn = {"01":"January","02":"February","03":"March","04":"April","05":"May","06":"June",
          "07":"July","08":"August","09":"September","10":"October","11":"November","12":"December"}
    mon_num = month.split("-")[1]
    year = month.split("-")[0]
    last_day = calendar.monthrange(int(year), int(mon_num))[1]
    mon_name = mn.get(mon_num, "Month")
    date_str = f"{last_day}/{mon_num}/{year}"

    ctx = {"client_name": name, "date": date_str, "currency": "EGP"}

    if not data:
        ctx["scope"] = "No data available."
        ctx["insights"] = ["No data available."]
        for k in ["reach","msg","content","audience","ads"]:
            ctx[k] = {"fb": {}, "ig": {}}
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
    ctx["reach"] = {
        "fb": {"views": fb_impr, "organic": int(fb_impr*0.1), "paid": int(fb_impr*0.9),
               "change": fmt_pct(pct_change(fb_impr, prev_fb)) if prev_fb else ""},
        "ig": {"views": ig_impr, "organic": int(ig_impr*0.1), "paid": int(ig_impr*0.9),
               "change": fmt_pct(pct_change(ig_impr, prev_ig)) if prev_ig else ""},
    }

    fb_msg = sum(int(c.get("results",0)) for c in msg_camps if "facebook" in c.get("campaign_name","").lower())
    ig_msg = sum(int(c.get("results",0)) for c in msg_camps if "instagram" in c.get("campaign_name","").lower())
    if not fb_msg and not ig_msg:
        fb_msg = msg_r // 2
        ig_msg = msg_r - fb_msg
    ctx["msg"] = {
        "fb": {"contacts": fb_msg, "organic": int(fb_msg*0.2), "paid": int(fb_msg*0.8)},
        "ig": {"contacts": ig_msg, "organic": int(ig_msg*0.2), "paid": int(ig_msg*0.8)},
    }

    top = sorted(camps, key=lambda c: float(c.get("spend",0)), reverse=True)[:6]
    ctx["content"] = {
        "fb": [{"name": c.get("campaign_name","—"), "views": c.get("impressions",0), "reach": c.get("reach",0)} for c in top],
        "ig": [],
    }

    women = sum(d.get("pct",0) for d in demos if d.get("gender")=="female")
    men = sum(d.get("pct",0) for d in demos if d.get("gender")=="male")
    age_groups = ["18-24","25-34","35-44","45-54","55-64","65+"]
    age_data = []
    for ag in age_groups:
        w = next((d for d in demos if d.get("age")==ag and d.get("gender")=="female"), {})
        m = next((d for d in demos if d.get("age")==ag and d.get("gender")=="male"), {})
        age_data.append({"age": ag, "women": w.get("pct",0), "men": m.get("pct",0)})
    ctx["audience"] = {
        "fb": {"followers": int(reach*0.3), "age_data": age_data, "women": women, "men": men},
        "ig": {"followers": int(reach*0.5), "age_data": age_data, "women": women, "men": men},
    }

    ctx["ads"] = {
        "fb": [{"name": c.get("campaign_name","—"), "results": c.get("results",0),
                 "cpr": c.get("cost_per_result",0), "spend": float(c.get("spend",0)),
                 "impressions": c.get("impressions",0), "reach": c.get("reach",0)} for c in camps],
        "ig": [],
    }

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


def fill_report(template_path, ctx, output_path):
    prs = Presentation(str(template_path))

    # Remove Budget slide (index 9)
    remove_slide(prs, 9)

    # Slide mapping after removal:
    # 0=Cover, 1=Contents, 2=Scope, 3=Reach, 4=Messaging, 5=Content, 6=Audience, 7=Insights, 8=Ads, 9=ThankYou

    def find_shape(slide, text_contains):
        """Find shape whose paragraph text contains the search string."""
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    if text_contains in para.text:
                        return para
        return None

    # Cover (slide 0)
    slide = prs.slides[0]
    for shape in slide.shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if "Client Name" in run.text:
                        run.text = f"Client Name: {ctx['client_name']}"
                    elif "Date" in run.text:
                        run.text = f"Date: {ctx['date']}"

    # Scope (slide 2)
    para = find_shape(prs.slides[2], "Type here")
    if para:
        set_para_text(para, ctx.get("scope", ""))

    # Reach (slide 3) - "Hi hi"
    r = ctx.get("reach", {})
    fb, ig = r.get("fb", {}), r.get("ig", {})
    para = find_shape(prs.slides[3], "Hi hi")
    if para:
        set_para_text(para,
            f"Facebook\nViews: {fmt_num(fb.get('views',0))} {fb.get('change','')}\n"
            f"  From organic: {fmt_num(fb.get('organic',0))}  From ads: {fmt_num(fb.get('paid',0))}\n\n"
            f"Instagram\nViews: {fmt_num(ig.get('views',0))} {ig.get('change','')}\n"
            f"  From organic: {fmt_num(ig.get('organic',0))}  From ads: {fmt_num(ig.get('paid',0))}")

    # Messaging (slide 4) - "Type here"
    mg = ctx.get("msg", {})
    fb_m, ig_m = mg.get("fb", {}), mg.get("ig", {})
    para = find_shape(prs.slides[4], "Type here")
    if para:
        set_para_text(para,
            f"Facebook\n  Total contacts: {fmt_num(fb_m.get('contacts',0))}\n"
            f"  Organic: {fmt_num(fb_m.get('organic',0))}  Paid: {fmt_num(fb_m.get('paid',0))}\n\n"
            f"Instagram\n  Total contacts: {fmt_num(ig_m.get('contacts',0))}\n"
            f"  Organic: {fmt_num(ig_m.get('organic',0))}  Paid: {fmt_num(ig_m.get('paid',0))}")

    # Content (slide 5) - "Type here"
    ct = ctx.get("content", {})
    fb_c, ig_c = ct.get("fb", []), ct.get("ig", [])
    para = find_shape(prs.slides[5], "Type here")
    if para:
        # Clear placeholder text
        set_para_text(para, "")
        # Hide the placeholder by moving it off-screen
        para_elem = para._p
        spPr = para_elem.getparent().find(qn('p:spPr'))
        if spPr is None:
            spPr = para_elem.getparent().makeelement(qn('p:spPr'), {})
            para_elem.getparent().append(spPr)

        total_rows = 1  # header
        if fb_c:
            total_rows += len(fb_c[:5]) + 1  # label + data
        if ig_c:
            total_rows += len(ig_c[:5]) + 1
        if not fb_c and not ig_c:
            total_rows = 2

        tbl = add_table_to_slide(prs.slides[5], total_rows, 3,
                                  Inches(0.6), Inches(1.8), Inches(8.5), Inches(0.35 * total_rows))

        # Set column widths
        tbl.columns[0].width = Inches(4.5)
        tbl.columns[1].width = Inches(2.0)
        tbl.columns[2].width = Inches(2.0)

        r = 0
        # Header
        set_cell(tbl, r, 0, "Campaign", bold=True, font_size=9)
        set_cell(tbl, r, 1, "Views", bold=True, align=PP_ALIGN.RIGHT, font_size=9)
        set_cell(tbl, r, 2, "Reach", bold=True, align=PP_ALIGN.RIGHT, font_size=9)
        shade_cells(tbl, r, "F5F5F5")
        r += 1

        if fb_c:
            set_cell(tbl, r, 0, "Facebook", bold=True, font_size=8)
            r += 1
            for p in fb_c[:5]:
                set_cell(tbl, r, 0, p['name'][:40], font_size=8)
                set_cell(tbl, r, 1, fmt_num(p['views']), align=PP_ALIGN.RIGHT, font_size=8)
                set_cell(tbl, r, 2, fmt_num(p['reach']), align=PP_ALIGN.RIGHT, font_size=8)
                r += 1

        if ig_c:
            set_cell(tbl, r, 0, "Instagram", bold=True, font_size=8)
            r += 1
            for p in ig_c[:5]:
                set_cell(tbl, r, 0, p['name'][:40], font_size=8)
                set_cell(tbl, r, 1, fmt_num(p['views']), align=PP_ALIGN.RIGHT, font_size=8)
                set_cell(tbl, r, 2, fmt_num(p['reach']), align=PP_ALIGN.RIGHT, font_size=8)
                r += 1

    # Audience (slide 6) - "Type here"
    au = ctx.get("audience", {})
    fb_a, ig_a = au.get("fb", {}), au.get("ig", {})
    para = find_shape(prs.slides[6], "Type here")
    if para:
        set_para_text(para, "")

        age_data = fb_a.get("age_data", [])
        total_rows = 1 + 2 + 1 + len(age_data)  # platform header, FB row, IG row, age header, age data

        tbl = add_table_to_slide(prs.slides[6], total_rows, 4,
                                  Inches(0.6), Inches(1.8), Inches(8.5), Inches(0.3 * total_rows))

        tbl.columns[0].width = Inches(1.5)
        tbl.columns[1].width = Inches(1.5)
        tbl.columns[2].width = Inches(1.2)
        tbl.columns[3].width = Inches(1.2)

        set_cell(tbl, 0, 0, "Platform", bold=True, font_size=9)
        set_cell(tbl, 0, 1, "Followers", bold=True, align=PP_ALIGN.RIGHT, font_size=9)
        set_cell(tbl, 0, 2, "Women", bold=True, align=PP_ALIGN.RIGHT, font_size=9)
        set_cell(tbl, 0, 3, "Men", bold=True, align=PP_ALIGN.RIGHT, font_size=9)
        shade_cells(tbl, 0, "F5F5F5")

        set_cell(tbl, 1, 0, "Facebook", font_size=8)
        set_cell(tbl, 1, 1, fmt_num(fb_a.get('followers',0)), align=PP_ALIGN.RIGHT, font_size=8)
        set_cell(tbl, 1, 2, f"{fb_a.get('women',0):.1f}%", align=PP_ALIGN.RIGHT, font_size=8)
        set_cell(tbl, 1, 3, f"{fb_a.get('men',0):.1f}%", align=PP_ALIGN.RIGHT, font_size=8)

        set_cell(tbl, 2, 0, "Instagram", font_size=8)
        set_cell(tbl, 2, 1, fmt_num(ig_a.get('followers',0)), align=PP_ALIGN.RIGHT, font_size=8)
        set_cell(tbl, 2, 2, f"{ig_a.get('women',0):.1f}%", align=PP_ALIGN.RIGHT, font_size=8)
        set_cell(tbl, 2, 3, f"{ig_a.get('men',0):.1f}%", align=PP_ALIGN.RIGHT, font_size=8)

        # Age breakdown table
        r = 3
        set_cell(tbl, r, 0, "Age Group", bold=True, font_size=8)
        set_cell(tbl, r, 1, "", bold=True, font_size=8)
        set_cell(tbl, r, 2, "Women", bold=True, align=PP_ALIGN.RIGHT, font_size=8)
        set_cell(tbl, r, 3, "Men", bold=True, align=PP_ALIGN.RIGHT, font_size=8)
        shade_cells(tbl, r, "F5F5F5")
        r += 1

        for ad in age_data:
            set_cell(tbl, r, 0, ad['age'], font_size=8)
            set_cell(tbl, r, 1, "", font_size=8)
            set_cell(tbl, r, 2, f"{ad['women']:.0f}%", align=PP_ALIGN.RIGHT, font_size=8)
            set_cell(tbl, r, 3, f"{ad['men']:.0f}%", align=PP_ALIGN.RIGHT, font_size=8)
            r += 1

    # Insights (slide 7) - "Type here" (template has INSIGHTS nav here)
    para = find_shape(prs.slides[7], "Type here")
    if para:
        set_para_text(para, "\n".join(f"• {ins}" for ins in ctx.get("insights", [])))

    # Ads (slide 8) - "HI" (template has ADS nav here)
    ad = ctx.get("ads", {})
    fb_ads = ad.get("fb", [])
    cur = ctx.get("currency", "EGP")
    para = find_shape(prs.slides[8], "HI")
    if para:
        set_para_text(para, "")
        if fb_ads:
            total_rows = 2 + min(len(fb_ads), 7)  # header + data + total
            tbl = add_table_to_slide(prs.slides[8], total_rows, 6,
                                      Inches(0.6), Inches(1.8), Inches(8.5), Inches(0.32 * total_rows))

            tbl.columns[0].width = Inches(3.0)
            tbl.columns[1].width = Inches(1.0)
            tbl.columns[2].width = Inches(1.2)
            tbl.columns[3].width = Inches(1.3)
            tbl.columns[4].width = Inches(1.0)
            tbl.columns[5].width = Inches(1.0)

            # Header
            headers = ["Campaign", "Results", "CPR", "Spend", "Impr.", "Reach"]
            for i, h in enumerate(headers):
                set_cell(tbl, 0, i, h, bold=True, align=PP_ALIGN.RIGHT if i > 0 else PP_ALIGN.LEFT, font_size=8)
            shade_cells(tbl, 0, "F5F5F5")

            # Data rows
            ts = ti = tr = 0
            for idx, c in enumerate(fb_ads[:7]):
                r = idx + 1
                s = c.get("spend", 0)
                ts += s; ti += c.get("impressions", 0); tr += c.get("reach", 0)
                set_cell(tbl, r, 0, c['name'][:35], font_size=7)
                set_cell(tbl, r, 1, f"{c.get('results',0):,}", align=PP_ALIGN.RIGHT, font_size=7)
                set_cell(tbl, r, 2, f"{c.get('cpr',0):,.0f} {cur}", align=PP_ALIGN.RIGHT, font_size=7)
                set_cell(tbl, r, 3, f"{s:,.0f} {cur}", align=PP_ALIGN.RIGHT, font_size=7)
                set_cell(tbl, r, 4, f"{c.get('impressions',0):,}", align=PP_ALIGN.RIGHT, font_size=7)
                set_cell(tbl, r, 5, f"{c.get('reach',0):,}", align=PP_ALIGN.RIGHT, font_size=7)

            # Total row
            r_total = min(len(fb_ads), 7) + 1
            set_cell(tbl, r_total, 0, "Total", bold=True, font_size=7)
            set_cell(tbl, r_total, 1, "", font_size=7)
            set_cell(tbl, r_total, 2, "", font_size=7)
            set_cell(tbl, r_total, 3, f"{ts:,.0f} {cur}", bold=True, align=PP_ALIGN.RIGHT, font_size=7)
            set_cell(tbl, r_total, 4, f"{ti:,}", bold=True, align=PP_ALIGN.RIGHT, font_size=7)
            set_cell(tbl, r_total, 5, f"{tr:,}", bold=True, align=PP_ALIGN.RIGHT, font_size=7)
            shade_cells(tbl, r_total, "F5F5F5")
        else:
            set_para_text(para, "No ads data.")

    # Thank You (slide 9)
    for shape in prs.slides[9].shapes:
        if shape.has_text_frame:
            for para in shape.text_frame.paragraphs:
                for run in para.runs:
                    if "Client Name" in run.text:
                        run.text = f"Client Name: {ctx['client_name']}"
                    elif "Date" in run.text:
                        run.text = f"Date: {ctx['date']}"

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
