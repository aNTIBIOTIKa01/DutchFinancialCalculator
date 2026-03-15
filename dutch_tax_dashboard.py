"""
🇳🇱 Dutch Financial Dashboard — v4
• Setup tab for all inputs (Scenario A & B)
• Income & Tax, Buy vs Rent, Scenario A/B, Sensitivity, Data & Export tabs
• Box 1 / Box 3 / ZVW / Zorgtoeslag / Hypotheekrenteaftrek / 30% ruling
• Adjustable timeline + annual salary growth
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from io import BytesIO
import os, json


# ════════════════════════════════════════════════════════════════════════════
# PDF EXPORT  —  white A4 report with matplotlib charts + Retirement section
# ════════════════════════════════════════════════════════════════════════════

def _chart_png(fig_fn, width_in=6.5, height_in=2.8, dpi=150):
    """
    Call fig_fn(fig, ax) to draw onto a matplotlib figure, return PNG BytesIO.
    Always uses a clean white background matching the PDF palette.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import io as _io

    BLUE   = "#1d4ed8"
    GREEN  = "#15803d"
    RED    = "#b91c1c"
    AMBER  = "#b45309"
    TEAL   = "#0f766e"
    GRID   = "#e2e8f0"
    TICK   = "#475569"

    fig, ax = plt.subplots(figsize=(width_in, height_in))
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    ax.tick_params(colors=TICK, labelsize=7)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(GRID)
    ax.spines["bottom"].set_color(GRID)
    ax.yaxis.grid(True, color=GRID, linewidth=0.5, zorder=0)
    ax.set_axisbelow(True)

    fig_fn(fig, ax, BLUE=BLUE, GREEN=GREEN, RED=RED, AMBER=AMBER, TEAL=TEAL, GRID=GRID)

    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    buf.seek(0)
    return buf


def generate_pdf_report(pa, pb, df_m_a, df_w_a, df_m_b, df_w_b,
                         ab_mode=False,
                         ret_params=None) -> bytes:
    """
    Professional minimalist A4 PDF with embedded matplotlib charts.
    White background, blue accent, clean tables, full Retirement section.
    Pass ret_params dict with retirement inputs; falls back to defaults if None.
    """
    import io, datetime as _dt
    import numpy as _np
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak, KeepTogether, Image,
    )

    # ── palette ──────────────────────────────────────────────────────────────
    DARK    = colors.HexColor("#1e293b")
    MID     = colors.HexColor("#475569")
    LIGHT   = colors.HexColor("#94a3b8")
    RULE    = colors.HexColor("#e2e8f0")
    BLUE    = colors.HexColor("#1d4ed8")
    GREEN   = colors.HexColor("#15803d")
    RED     = colors.HexColor("#b91c1c")
    AMBER   = colors.HexColor("#b45309")
    TEAL    = colors.HexColor("#0f766e")
    HDR_BG  = colors.HexColor("#1e3a5f")
    ZEBRA   = colors.HexColor("#f8fafc")
    WHITE   = colors.white

    PAGE_W, PAGE_H = A4
    LM, RM = 2.0 * cm, 2.0 * cm
    W = PAGE_W - LM - RM

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=LM, rightMargin=RM,
        topMargin=2.6*cm, bottomMargin=2.2*cm,
        title="Dutch Financial Dashboard — Pro Report",
        author="Dutch Financial Dashboard",
    )

    # ── style helpers ────────────────────────────────────────────────────────
    _sc = {}
    def S(name, **kw):
        key = (name, tuple(sorted(kw.items())))
        if key not in _sc:
            _sc[key] = ParagraphStyle(name, **kw)
        return _sc[key]

    sH1  = S("H1",  fontSize=15, leading=20, textColor=BLUE,
              fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=4)
    sH2  = S("H2",  fontSize=11, leading=15, textColor=DARK,
              fontName="Helvetica-Bold", spaceBefore=8, spaceAfter=3)
    sBod = S("Bod", fontSize=9,  leading=13, textColor=MID,
              fontName="Helvetica", spaceAfter=4)
    sCap = S("Cap", fontSize=7.5,leading=11, textColor=LIGHT,
              fontName="Helvetica-Oblique", spaceAfter=3)
    sOK  = S("OK",  fontSize=9,  leading=13, textColor=GREEN,
              fontName="Helvetica-Bold", spaceAfter=3)
    sWRN = S("WRN", fontSize=9,  leading=13, textColor=RED,
              fontName="Helvetica-Bold", spaceAfter=3)

    def HR(thick=0.5, color=RULE):
        return HRFlowable(width="100%", thickness=thick, color=color,
                          spaceAfter=4, spaceBefore=4)

    # ── embed chart ───────────────────────────────────────────────────────────
    def embed(fig_fn, caption="", w=W, h=5.5*cm, **extra):
        """Draw a matplotlib chart via fig_fn, embed as Image."""
        png = _chart_png(lambda fig, ax, **kw: fig_fn(fig, ax, **kw),
                         width_in=w / cm * 0.39370,
                         height_in=h / cm * 0.39370)
        items = [Image(png, width=w, height=h)]
        if caption:
            items.append(Paragraph(caption, sCap))
        return items

    # ── KPI row ──────────────────────────────────────────────────────────────
    def kpi_row(items):
        n  = len(items)
        cw = [W / n] * n
        vals = [Paragraph(f"<b>{v}</b>",
                    S(f"KV{i}{n}", fontSize=14, leading=18, textColor=c,
                      fontName="Helvetica-Bold", alignment=TA_CENTER))
                for i, (_, v, c) in enumerate(items)]
        labs = [Paragraph(lbl,
                    S(f"KL{i}{n}", fontSize=7.5, leading=10, textColor=LIGHT,
                      fontName="Helvetica", alignment=TA_CENTER))
                for i, (lbl, _, _) in enumerate(items)]
        t = Table([vals, labs], colWidths=cw)
        t.setStyle(TableStyle([
            ("BOX",         (0,0),(-1,-1), 0.3, RULE),
            ("INNERGRID",   (0,0),(-1,-1), 0.3, RULE),
            ("TOPPADDING",  (0,0),(-1,-1), 9),
            ("BOTTOMPADDING",(0,0),(-1,-1), 9),
            ("LEFTPADDING", (0,0),(-1,-1), 6),
            ("RIGHTPADDING",(0,0),(-1,-1), 6),
            ("LINEBELOW",   (0,0),(-1,0),  0.8, RULE),
        ]))
        return t

    # ── data table ───────────────────────────────────────────────────────────
    def dtbl(headers, rows, cw=None):
        n  = len(headers)
        cw = cw or [W / n] * n
        hrow = [Paragraph(h, S(f"TH{i}{h[:3]}", fontSize=8, leading=10,
                               textColor=WHITE, fontName="Helvetica-Bold",
                               alignment=TA_CENTER))
                for i, h in enumerate(headers)]
        tdata = [hrow]
        for ri, row in enumerate(rows):
            tdata.append([
                Paragraph(str(cell), S(f"TD{ri}{ci}", fontSize=8, leading=10,
                          textColor=DARK, fontName="Helvetica", alignment=TA_CENTER))
                for ci, cell in enumerate(row)
            ])
        ts = [
            ("BACKGROUND",    (0,0),(-1,0),  HDR_BG),
            ("TOPPADDING",    (0,0),(-1,-1), 5),
            ("BOTTOMPADDING", (0,0),(-1,-1), 5),
            ("LEFTPADDING",   (0,0),(-1,-1), 5),
            ("RIGHTPADDING",  (0,0),(-1,-1), 5),
            ("BOX",           (0,0),(-1,-1), 0.3, RULE),
            ("INNERGRID",     (0,1),(-1,-1), 0.3, RULE),
            ("LINEBELOW",     (0,0),(-1,0),  0.3, colors.HexColor("#3b82f6")),
        ]
        for ri in range(1, len(tdata)):
            ts.append(("BACKGROUND", (0,ri),(-1,ri), ZEBRA if ri%2==0 else WHITE))
        return Table(tdata, colWidths=cw, style=TableStyle(ts),
                     hAlign="LEFT", repeatRows=1)

    # ── page header/footer ────────────────────────────────────────────────────
    def _on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.rect(0, PAGE_H - 0.55*cm, PAGE_W, 0.55*cm, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Helvetica-Bold", 7)
        canvas.drawString(LM, PAGE_H - 0.38*cm,
                          "Dutch Financial Dashboard  \u00b7  Pro Report")
        bx = PAGE_W - RM - 1.8*cm
        canvas.setFillColor(colors.HexColor("#fbbf24"))
        canvas.roundRect(bx, PAGE_H-0.50*cm, 1.7*cm, 0.40*cm, 3, fill=1, stroke=0)
        canvas.setFillColor(colors.HexColor("#1e1e1e"))
        canvas.setFont("Helvetica-Bold", 6.5)
        canvas.drawCentredString(bx+0.85*cm, PAGE_H-0.33*cm, "\u2b50 PRO PLAN")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.4)
        canvas.line(LM, 1.8*cm, PAGE_W-RM, 1.8*cm)
        canvas.setFillColor(LIGHT)
        canvas.setFont("Helvetica", 7)
        canvas.drawString(LM, 1.3*cm,
                          "Approximations only \u2014 consult a belastingadviseur / financieel planner.")
        canvas.drawRightString(PAGE_W-RM, 1.3*cm, f"Page {doc.page}")
        canvas.restoreState()

    # ════════════════════════════════════════════════════════════════
    # Retire params with defaults
    # ════════════════════════════════════════════════════════════════
    _rd = ret_params or {}
    ret_current_age  = _rd.get("ret_current_age",  32)
    ret_age_r        = _rd.get("ret_age",           67)
    ret_target       = _rd.get("ret_target_income", 3500)
    ret_aow_r        = _rd.get("ret_aow",           1450)
    ret_pension_r    = _rd.get("ret_pension",        500)
    ret_swr_r        = _rd.get("ret_swr",           0.035)
    ret_ret_pre      = _rd.get("ret_return_pre",    0.07)
    ret_ret_post     = _rd.get("ret_return_post",   0.04)

    years_to_ret_r   = max(ret_age_r - ret_current_age, 1)
    pillar12_r       = ret_aow_r + ret_pension_r
    pension_gap_r    = max(ret_target - pillar12_r, 0)
    capital_needed_r = pension_gap_r * 12 / ret_swr_r if ret_swr_r > 0 else 0
    fire_r           = ret_target * 12 / ret_swr_r if ret_swr_r > 0 else 0

    _start_cap_r     = df_w_a.iloc[-1]["Total Wealth (Buy)"]
    _avg_sav_r       = df_m_a["Net Saving"].mean()
    _r_mo_r          = (1 + ret_ret_pre) ** (1/12) - 1
    _cap_r           = _start_cap_r
    _proj_m          = len(df_m_a)
    _sav_list        = list(df_m_a["Net Saving"])
    _mc              = 0
    _n_yrs_proj      = pa.get("n_years", 5)
    for _yr in range(years_to_ret_r):
        for _mo in range(12):
            _s = _sav_list[_mc] if _mc < _proj_m else _avg_sav_r
            _cap_r = _cap_r * (1 + _r_mo_r) + _s
            _mc += 1
    proj_cap_ret = max(_cap_r, 0)

    # Depletion curve
    _r_mo_post_r   = (1 + ret_ret_post) ** (1/12) - 1
    _dep_yrs_r     = min(100 - ret_age_r, 50)
    _dep_curve_r   = [proj_cap_ret]
    _cap_d_r       = proj_cap_ret
    for _yr in range(_dep_yrs_r):
        for _mo in range(12):
            _cap_d_r = _cap_d_r * (1 + _r_mo_post_r) - pension_gap_r
        _dep_curve_r.append(max(_cap_d_r, 0))
        if _cap_d_r <= 0:
            _dep_curve_r += [0] * (_dep_yrs_r - _yr - 1)
            break

    # Portfolio growth curve
    _port_curve = [_start_cap_r]
    _cap_g = _start_cap_r
    _mc2 = 0
    for _yr in range(years_to_ret_r):
        for _mo in range(12):
            _s = _sav_list[_mc2] if _mc2 < _proj_m else _avg_sav_r
            _cap_g = _cap_g * (1 + _r_mo_r) + _s
            _mc2 += 1
        _port_curve.append(_cap_g)

    import datetime as _dt2
    _base_yr = _dt2.date.today().year
    _port_years = [_base_yr + y for y in range(len(_port_curve))]

    # ════════════════════════════════════════════════════════════════
    # STORY
    # ════════════════════════════════════════════════════════════════
    story = []
    today = _dt.date.today()
    p     = pa
    sg    = p.get("sal_growth", 0.0)

    # ── COVER ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 1.0*cm))
    story.append(Paragraph("Dutch Financial Dashboard",
        S("CVT", fontSize=26, leading=32, textColor=DARK,
          fontName="Helvetica-Bold", alignment=TA_LEFT)))
    story.append(Paragraph("Personal Financial Projection  \u2014  Pro Report",
        S("CVS", fontSize=12, leading=16, textColor=MID,
          fontName="Helvetica", alignment=TA_LEFT, spaceAfter=4)))
    story.append(HR(1.5, BLUE))
    _scen = p.get("scenario_label") or "Scenario A"
    _yrs  = p.get("n_years", 5)
    story.append(Paragraph(
        f"Scenario: <b>{_scen}</b> \u00a0\u00b7\u00a0 "
        f"Horizon: <b>{_yrs} years</b> \u00a0\u00b7\u00a0 "
        f"Generated: <b>{today:%d %B %Y}</b>",
        S("CVMeta", fontSize=9, leading=13, textColor=MID,
          fontName="Helvetica", spaceAfter=10)))
    _badge_row = [[Paragraph(
        "\u2b50  PRO PLAN  \u2014  All features included  \u2014  "
        "Income &amp; Tax \u00b7 Buy vs Rent \u00b7 Mortgage \u00b7 "
        "Scenario A/B \u00b7 Actuals \u00b7 Retirement \u00b7 PDF Export",
        S("BadgeTxt", fontSize=8.5, leading=12, textColor=WHITE,
          fontName="Helvetica-Bold", alignment=TA_CENTER))]]
    _badge_t = Table(_badge_row, colWidths=[W])
    _badge_t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,-1),BLUE),
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",(0,0),(-1,-1),10),("RIGHTPADDING",(0,0),(-1,-1),10),
    ]))
    story.append(_badge_t)
    story.append(Spacer(1, 0.4*cm))

    import datetime as _dt3
    cur_yr = _dt3.date.today().year
    _a30s  = p.get("ruling_s",True) and p.get("rs_s",p["rs"]) <= cur_yr < p.get("re_s",p["re"])
    _a30p  = p.get("ruling_p",False) and p.get("rs_p",p["rs"]) <= cur_yr < p.get("re_p",p["re"])
    net_s_now = net_monthly_calc(p["inc_s"], cur_yr, _a30s)
    net_p_now = net_monthly_calc(p["inc_p"], cur_yr, _a30p) if p["partner"] else 0
    mp_now    = mort_payment(p["house_price"], p["dp"], p["mort_rate"])
    fixed_now = sum(p.get(k,0) for k in
                    ["hi","cf","ci","gr","ot","utilities","phone","subscriptions","gym","dog"])
    story.append(kpi_row([
        ("Gross income / yr",  f"\u20ac\u202f{p['inc_s']:,.0f}",          DARK),
        ("Net income / mo",    f"\u20ac\u202f{net_s_now+net_p_now:,.0f}", GREEN),
        ("House price",        f"\u20ac\u202f{p['house_price']:,.0f}",     BLUE),
        ("Mortgage / mo",      f"\u20ac\u202f{mp_now:,.0f}",              RED),
    ]))
    story.append(Spacer(1,0.15*cm))
    story.append(kpi_row([
        ("Fixed expenses / mo",f"\u20ac\u202f{fixed_now:,.0f}",           AMBER),
        ("Starting savings",   f"\u20ac\u202f{p.get('savings',0):,.0f}",  TEAL),
        ("Retirement age",     f"{ret_age_r}",                      MID),
        ("Capital needed",     f"\u20ac\u202f{capital_needed_r:,.0f}",
         GREEN if proj_cap_ret >= capital_needed_r else RED),
    ]))
    story.append(Spacer(1,0.5*cm))
    story.append(HR(0.3, RULE))
    story.append(Paragraph(
        "\u26a0\ufe0f  Approximations of Dutch tax law 2026\u20132030.  "
        "Always consult a qualified belastingadviseur / financieel planner.",
        sCap))

    # ── TABLE OF CONTENTS ────────────────────────────────────────────────────
    story.append(PageBreak())
    story.append(Paragraph("Contents", sH1))
    story.append(HR(1.0, BLUE))
    _toc = [
        ("1", "Income &amp; Tax",
         "Annual net income \u00b7 30% ruling impact \u00b7 monthly P&amp;L \u00b7 chart"),
        ("2", "Buy vs Rent",
         "Wealth projection chart \u00b7 crossover date \u00b7 year-end summary"),
        ("3", "Mortgage Analysis",
         "Annuity vs Linear chart \u00b7 MRI benefit \u00b7 30-year net cost"),
        ("4", "Monthly Expenses",
         "Expense breakdown chart \u00b7 future recurring costs"),
    ]
    _sec = 4
    if ab_mode:
        _sec += 1
        _toc.append((str(_sec), "Scenario A/B Comparison",
                     "Side-by-side outcome table for both scenarios"))
    _sec += 1
    _toc.append((str(_sec), "Retirement Planning",
                 "Portfolio growth chart \u00b7 income waterfall \u00b7 depletion curve \u00b7 sensitivity table"))
    _sec += 1
    _toc.append((str(_sec), "Setup Summary", "All input parameters used in this report"))

    _toc_rows = []
    for num, title, desc in _toc:
        _toc_rows.append([
            Paragraph(num, S(f"TN{num}", fontSize=10, leading=14, textColor=BLUE,
                             fontName="Helvetica-Bold")),
            Paragraph(f"<b>{title}</b>", S(f"TT{num}", fontSize=10, leading=14,
                                           textColor=DARK, fontName="Helvetica-Bold")),
            Paragraph(desc, S(f"TD{num}", fontSize=8.5, leading=12,
                              textColor=MID, fontName="Helvetica")),
        ])
    _toc_t = Table(_toc_rows, colWidths=[0.7*cm, 5.2*cm, W-5.9*cm])
    _toc_t.setStyle(TableStyle([
        ("TOPPADDING",(0,0),(-1,-1),7),("BOTTOMPADDING",(0,0),(-1,-1),7),
        ("LEFTPADDING",(0,0),(-1,-1),4),("RIGHTPADDING",(0,0),(-1,-1),4),
        ("LINEBELOW",(0,0),(-1,-1),0.3,RULE),("VALIGN",(0,0),(-1,-1),"MIDDLE"),
    ]))
    story.append(_toc_t)
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # 1 — INCOME & TAX
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("1  \u2014  Income &amp; Tax", sH1))
    story.append(HR(1.0, BLUE))

    years  = sorted(df_m_a["Year"].unique())
    ruling_active = p.get("ruling_s", True)
    re_yr  = p.get("re_s", p["re"])

    story.append(Paragraph("Annual Net Income vs Tax Burden", sH2))
    h_tax = ["Year", "30% Ruling", "Gross / yr", "Net / yr", "Net / mo", "Eff. Rate"]
    r_tax = []
    for yr in years:
        a30   = ruling_active and p.get("rs_s", p["rs"]) <= yr < re_yr
        gross = p["inc_s"] * (1 + sg) ** (yr - 2026)
        net_a = net_annual_calc(gross, yr, a30)
        r_tax.append([str(yr), "\u2713" if a30 else "\u2014",
                      f"\u20ac\u202f{gross:,.0f}", f"\u20ac\u202f{net_a:,.0f}",
                      f"\u20ac\u202f{net_a/12:,.0f}", f"{(gross-net_a)/gross*100:.1f}%"])
    story.append(dtbl(h_tax, r_tax, [W*0.10,W*0.13,W*0.20,W*0.20,W*0.20,W*0.17]))
    story.append(Spacer(1,0.25*cm))

    if ruling_active:
        net_on  = net_monthly_calc(p["inc_s"]*(1+sg)**(re_yr-1-2026), re_yr-1, True)
        net_off = net_monthly_calc(p["inc_s"]*(1+sg)**(re_yr-2026),   re_yr,   False)
        drop    = net_on - net_off
        story.append(Paragraph(
            f"\u26a0\ufe0f  30% ruling expires Jan {re_yr}: monthly net drops "
            f"\u20ac\u202f{drop:,.0f}  (\u20ac\u202f{net_on:,.0f} \u2192 \u20ac\u202f{net_off:,.0f}/mo).", sWRN))

    # CHART: net income + expenses + savings
    _dates_num = list(range(len(df_m_a)))
    _net_vals  = list(df_m_a["Total Net"])
    _exp_vals  = list(df_m_a["Total Expenses"])
    _sav_vals  = list(df_m_a["Net Saving"])
    _date_lbls = [d.strftime("%b %y") for d in df_m_a["Date"]]

    def _draw_income(fig, ax, **kw):
        ax.fill_between(_dates_num, _net_vals, alpha=0.12, color=kw["BLUE"])
        ax.plot(_dates_num, _net_vals, color=kw["BLUE"], lw=2, label="Net Income")
        ax.plot(_dates_num, _exp_vals, color=kw["RED"],  lw=1.5, label="Total Expenses")
        ax.plot(_dates_num, _sav_vals, color=kw["GREEN"], lw=1.5, ls="--", label="Monthly Savings")
        step = max(1, len(_dates_num)//8)
        ax.set_xticks(_dates_num[::step])
        ax.set_xticklabels(_date_lbls[::step], rotation=30, ha="right", fontsize=6.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x:,.0f}")
        ax.legend(fontsize=7, framealpha=0.9)
        ax.set_title("Monthly Net Income, Expenses & Savings", fontsize=9, fontweight="bold",
                     color="#1e293b", pad=6)

    story += embed(_draw_income,
                   "Blue = net income, red = total expenses, green dashed = monthly savings surplus.")

    story.append(Paragraph("Monthly P&amp;L \u2014 First 24 Months", sH2))
    h_pnl = ["Date","Net Income","Total Expenses","Housing","MRI Benefit","Savings"]
    r_pnl = []
    for _, row in df_m_a.head(24).iterrows():
        r_pnl.append([row["Date"].strftime("%b %Y"),
                      f"\u20ac\u202f{row['Total Net']:,.0f}", f"\u20ac\u202f{row['Total Expenses']:,.0f}",
                      f"\u20ac\u202f{row['Housing Cost']:,.0f}", f"\u20ac\u202f{row['MRI Benefit']:,.0f}",
                      f"\u20ac\u202f{row['Net Saving']:,.0f}"])
    story.append(dtbl(h_pnl, r_pnl, [W*0.14,W*0.16,W*0.17,W*0.16,W*0.16,W*0.21]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # 2 — BUY VS RENT
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("2  \u2014  Buy vs Rent", sH1))
    story.append(HR(1.0, BLUE))

    dw    = df_w_a
    fin   = dw.iloc[-1]
    delta = fin["Wealth Delta"]
    story.append(kpi_row([
        ("End Wealth \u2014 Buy",  f"\u20ac\u202f{fin['Total Wealth (Buy)']:,.0f}",  GREEN),
        ("End Wealth \u2014 Rent", f"\u20ac\u202f{fin['Total Wealth (Rent)']:,.0f}", BLUE),
        ("Buy vs Rent Edge",("+" if delta>=0 else "")+f"\u20ac\u202f{delta:,.0f}",
         GREEN if delta>=0 else RED),
        ("Home Equity (end)", f"\u20ac\u202f{fin['Home Equity']:,.0f}", AMBER),
    ]))
    story.append(Spacer(1,0.2*cm))

    cx_row = dw[dw["Wealth Delta"]>0].head(1)
    if not cx_row.empty:
        cx_date = cx_row["Date"].iloc[0]
        cx_yrs  = (cx_date - dw["Date"].iloc[0]).days / 365.25
        story.append(Paragraph(
            f"Buying overtakes renting after <b>{cx_yrs:.1f} years</b> "
            f"(around <b>{cx_date:%B %Y}</b>).", sOK))
    else:
        story.append(Paragraph(
            "Within this projection window, buying has not overtaken renting.", sWRN))

    # CHART: wealth comparison
    _dw_dates = list(range(len(dw)))
    _dw_buy   = list(dw["Total Wealth (Buy)"])
    _dw_rent  = list(dw["Total Wealth (Rent)"])
    _dw_eq    = list(dw["Home Equity"])
    _dw_lbls  = [d.strftime("%b %y") for d in dw["Date"]]

    def _draw_bvr(fig, ax, **kw):
        ax.plot(_dw_dates, _dw_buy,  color=kw["GREEN"], lw=2.5, label="Total Wealth (Buy)")
        ax.plot(_dw_dates, _dw_rent, color=kw["RED"],   lw=2,   label="Total Wealth (Rent)")
        ax.plot(_dw_dates, _dw_eq,   color=kw["AMBER"], lw=1.5, ls=":", label="Home Equity")
        step = max(1, len(_dw_dates)//8)
        ax.set_xticks(_dw_dates[::step])
        ax.set_xticklabels(_dw_lbls[::step], rotation=30, ha="right", fontsize=6.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x/1e3:.0f}k")
        ax.legend(fontsize=7, framealpha=0.9)
        ax.set_title("Total Net Worth: Buy vs Rent", fontsize=9, fontweight="bold",
                     color="#1e293b", pad=6)

    story += embed(_draw_bvr, "Green = buy scenario, red = rent scenario, amber dotted = home equity.")

    story.append(Paragraph("Year-End Wealth Summary", sH2))
    daw = dw.groupby("Year").last().reset_index()
    h_w = ["Year","House Value","Mortgage Bal.","Home Equity",
           "Cash (Buy)","Wealth (Buy)","Wealth (Rent)","Buy Edge"]
    r_w = []
    for _, row in daw.iterrows():
        edge = row["Total Wealth (Buy)"] - row["Total Wealth (Rent)"]
        r_w.append([str(int(row["Year"])),
                    f"\u20ac\u202f{row['House Value']:,.0f}", f"\u20ac\u202f{row['Mortgage Balance']:,.0f}",
                    f"\u20ac\u202f{row['Home Equity']:,.0f}", f"\u20ac\u202f{row['Cash (Buy)']:,.0f}",
                    f"\u20ac\u202f{row['Total Wealth (Buy)']:,.0f}",
                    f"\u20ac\u202f{row['Total Wealth (Rent)']:,.0f}",
                    ("+" if edge>=0 else "")+f"\u20ac\u202f{edge:,.0f}"])
    story.append(dtbl(h_w, r_w, [W*0.09,W*0.13,W*0.12,W*0.12,W*0.12,W*0.13,W*0.13,W*0.16]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # 3 — MORTGAGE
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("3  \u2014  Mortgage Analysis", sH1))
    story.append(HR(1.0, BLUE))

    loan    = p["house_price"] * (1 - p["dp"])
    df_ann  = amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"],
                                    "Annuity (annuïteit)", 30)
    df_lin  = amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"],
                                    "Linear (lineair)", 30)
    ann_net1 = df_ann["Net_Payment"].iloc[0]
    lin_net1 = df_lin["Net_Payment"].iloc[0]
    ann_mri1 = df_ann["MRI_Benefit"].iloc[0]
    story.append(kpi_row([
        ("Loan Amount",            f"\u20ac\u202f{loan:,.0f}",     BLUE),
        ("Annuity Net/mo (mo 1)",  f"\u20ac\u202f{ann_net1:,.0f}", GREEN),
        ("Linear Net/mo (mo 1)",   f"\u20ac\u202f{lin_net1:,.0f}", AMBER),
        ("MRI Benefit/mo (mo 1)",  f"\u20ac\u202f{ann_mri1:,.0f}", TEAL),
    ]))
    story.append(Spacer(1,0.2*cm))

    # CHART: mortgage net payment over projection period
    n_proj = p.get("n_years",5) * 12
    _ann_d = list(range(min(n_proj, len(df_ann))))
    _ann_net = list(df_ann.head(n_proj)["Net_Payment"])
    _lin_net = list(df_lin.head(n_proj)["Net_Payment"])
    _mri_ann = list(df_ann.head(n_proj)["MRI_Benefit"])
    _mort_lbls = [d.strftime("%b %y") for d in df_ann.head(n_proj)["Date"]]

    def _draw_mort(fig, ax, **kw):
        ax.plot(_ann_d, _ann_net, color=kw["BLUE"], lw=2, label="Annuity Net")
        ax.plot(_ann_d, _lin_net, color=kw["AMBER"], lw=2, ls="--", label="Linear Net")
        ax.plot(_ann_d, _mri_ann, color=kw["GREEN"], lw=1.5, ls=":", label="MRI Benefit (Ann.)")
        step = max(1, len(_ann_d)//8)
        ax.set_xticks(_ann_d[::step])
        ax.set_xticklabels(_mort_lbls[::step], rotation=30, ha="right", fontsize=6.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x:,.0f}")
        ax.legend(fontsize=7, framealpha=0.9)
        ax.set_title("Net Monthly Mortgage Payment vs MRI Tax Benefit", fontsize=9,
                     fontweight="bold", color="#1e293b", pad=6)

    story += embed(_draw_mort, "Blue = annuity net, amber dashed = linear net, green dotted = MRI benefit.")

    story.append(Paragraph("Annuity vs Linear \u2014 Year-End Summary", sH2))
    df_ay = df_ann.groupby("Year").agg(
        Ann_Pay=("Payment","sum"), Ann_Int=("Interest","sum"),
        Ann_MRI=("MRI_Benefit","sum"), Ann_Bal=("Balance","last")).reset_index()
    df_ly = df_lin.groupby("Year").agg(
        Lin_Pay=("Payment","sum"), Lin_Int=("Interest","sum"),
        Lin_MRI=("MRI_Benefit","sum"), Lin_Bal=("Balance","last")).reset_index()
    df_yr = df_ay.merge(df_ly, on="Year").head(p.get("n_years",5))
    h_m   = ["Year","Ann.Pay/yr","Ann.Int/yr","Ann.MRI/yr","Ann.Bal",
              "Lin.Pay/yr","Lin.Int/yr","Lin.MRI/yr","Lin.Bal"]
    r_m   = []
    for _, row in df_yr.iterrows():
        r_m.append([str(int(row["Year"])),
                    f"\u20ac\u202f{row['Ann_Pay']:,.0f}", f"\u20ac\u202f{row['Ann_Int']:,.0f}",
                    f"\u20ac\u202f{row['Ann_MRI']:,.0f}", f"\u20ac\u202f{row['Ann_Bal']:,.0f}",
                    f"\u20ac\u202f{row['Lin_Pay']:,.0f}", f"\u20ac\u202f{row['Lin_Int']:,.0f}",
                    f"\u20ac\u202f{row['Lin_MRI']:,.0f}", f"\u20ac\u202f{row['Lin_Bal']:,.0f}"])
    story.append(dtbl(h_m, r_m, [W*0.09]+[W*0.114]*8))
    ann_30 = df_ann["Payment"].sum() - df_ann["MRI_Benefit"].sum()
    lin_30 = df_lin["Payment"].sum() - df_lin["MRI_Benefit"].sum()
    save30 = ann_30 - lin_30
    story.append(Spacer(1,0.2*cm))
    story.append(kpi_row([
        ("Annuity net total (30yr)", f"\u20ac\u202f{ann_30:,.0f}", RED),
        ("Linear net total (30yr)",  f"\u20ac\u202f{lin_30:,.0f}", GREEN),
        ("Saving with Linear",       f"\u20ac\u202f{save30:,.0f}", AMBER),
    ]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # 4 — EXPENSES
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph("4  \u2014  Monthly Expenses", sH1))
    story.append(HR(1.0, BLUE))

    exp_cats = [
        ("Health Insurance",    p["hi"]),
        ("Car (finance+ins.)",  p["cf"]+p["ci"]),
        ("Groceries",           p["gr"]),
        ("Utilities",           p.get("utilities",0)),
        ("Phone & Subscr.",     p.get("phone",0)+p.get("subscriptions",0)),
        ("Gym",                 p.get("gym",0)),
        ("Dog",                 p.get("dog",0)),
        ("Other",               p["ot"]),
    ]
    grand = sum(v for _,v in exp_cats) + mp_now
    _exp_labels = [c for c,v in exp_cats if v>0] + ["Mortgage"]
    _exp_vals_p = [v for _,v in exp_cats if v>0] + [mp_now]
    _pie_colors = ["#1d4ed8","#d97706","#15803d","#0f766e",
                   "#7c3aed","#db2777","#ea580c","#64748b","#b91c1c"]

    def _draw_pie(fig, ax, **kw):
        import matplotlib.pyplot as _plt
        ax.axis("off")
        wedges, texts, autotexts = ax.pie(
            _exp_vals_p,
            labels=_exp_labels,
            colors=_pie_colors[:len(_exp_vals_p)],
            autopct="%1.0f%%",
            startangle=90,
            pctdistance=0.75,
            labeldistance=1.05,
            textprops={"fontsize": 6.5},
        )
        for at in autotexts:
            at.set_fontsize(6)
            at.set_color("white")
        ax.set_title("Monthly Expense Breakdown", fontsize=9, fontweight="bold",
                     color="#1e293b", pad=6)

    story += embed(_draw_pie, "Proportion of each expense category at start of projection.",
                   h=6.0*cm)

    exp_rows = [[cat, f"\u20ac\u202f{val:,.0f}/mo", f"{val/grand*100:.1f}%"]
                for cat,val in exp_cats if val>0]
    exp_rows.append(["Mortgage (gross)", f"\u20ac\u202f{mp_now:,.0f}/mo",
                     f"{mp_now/grand*100:.1f}%"])
    exp_rows.append(["\u2014\u2014 TOTAL \u2014\u2014", f"\u20ac\u202f{grand:,.0f}/mo", "100%"])
    story.append(dtbl(["Category","Amount","% of Total"],
                      exp_rows, [W*0.52,W*0.26,W*0.22]))
    fe_list = pa.get("future_expenses",[])
    if fe_list:
        story.append(Spacer(1,0.2*cm))
        story.append(Paragraph("Planned Future Recurring Expenses", sH2))
        fe_rows = [[fe.get("name","—"), f"\u20ac\u202f{fe.get('amount',0):,.0f}/mo",
                    fe.get("start_ym","—"), fe.get("end_ym","ongoing"),
                    f"{fe.get('growth',0)*100:.1f}%/yr"] for fe in fe_list]
        story.append(dtbl(["Name","Amount","Start","End","Growth"],
                          fe_rows, [W*0.35,W*0.18,W*0.15,W*0.17,W*0.15]))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # 5 — SCENARIO A/B (optional)
    # ════════════════════════════════════════════════════════════════
    _sec_n = 5
    if ab_mode:
        story.append(Paragraph(f"{_sec_n}  \u2014  Scenario A/B Comparison", sH1))
        story.append(HR(1.0, BLUE))
        sa_name = pa.get("scenario_label") or "Scenario A"
        sb_name = pb.get("scenario_label") or "Scenario B"
        fin_a = df_w_a.iloc[-1]; fin_b = df_w_b.iloc[-1]

        # CHART: A vs B wealth
        _ab_a = list(df_w_a["Total Wealth (Buy)"])
        _ab_b = list(df_w_b["Total Wealth (Buy)"])
        _ab_d = list(range(len(_ab_a)))
        _ab_lbls = [d.strftime("%b %y") for d in df_w_a["Date"]]

        def _draw_ab(fig, ax, **kw):
            ax.plot(_ab_d, _ab_a, color=kw["BLUE"], lw=2.5, label=sa_name)
            ax.plot(_ab_d, _ab_b, color=kw["AMBER"], lw=2.5, ls="--", label=sb_name)
            step = max(1, len(_ab_d)//8)
            ax.set_xticks(_ab_d[::step])
            ax.set_xticklabels(_ab_lbls[::step], rotation=30, ha="right", fontsize=6.5)
            ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x/1e3:.0f}k")
            ax.legend(fontsize=7, framealpha=0.9)
            ax.set_title(f"Total Wealth: {sa_name} vs {sb_name}", fontsize=9,
                         fontweight="bold", color="#1e293b", pad=6)

        story += embed(_draw_ab)

        cmp_rows = [
            ["End Wealth (Buy)",
             f"\u20ac\u202f{fin_a['Total Wealth (Buy)']:,.0f}",
             f"\u20ac\u202f{fin_b['Total Wealth (Buy)']:,.0f}",
             f"\u20ac\u202f{fin_a['Total Wealth (Buy)']-fin_b['Total Wealth (Buy)']:,.0f}"],
            ["End Wealth (Rent)",
             f"\u20ac\u202f{fin_a['Total Wealth (Rent)']:,.0f}",
             f"\u20ac\u202f{fin_b['Total Wealth (Rent)']:,.0f}",
             f"\u20ac\u202f{fin_a['Total Wealth (Rent)']-fin_b['Total Wealth (Rent)']:,.0f}"],
            ["Home Equity",
             f"\u20ac\u202f{fin_a['Home Equity']:,.0f}",
             f"\u20ac\u202f{fin_b['Home Equity']:,.0f}",
             f"\u20ac\u202f{fin_a['Home Equity']-fin_b['Home Equity']:,.0f}"],
            ["Avg Net Income/mo",
             f"\u20ac\u202f{df_m_a['Total Net'].mean():,.0f}",
             f"\u20ac\u202f{df_m_b['Total Net'].mean():,.0f}",
             f"\u20ac\u202f{df_m_a['Total Net'].mean()-df_m_b['Total Net'].mean():,.0f}"],
            ["Avg Savings/mo",
             f"\u20ac\u202f{df_m_a['Net Saving'].mean():,.0f}",
             f"\u20ac\u202f{df_m_b['Net Saving'].mean():,.0f}",
             f"\u20ac\u202f{df_m_a['Net Saving'].mean()-df_m_b['Net Saving'].mean():,.0f}"],
        ]
        story.append(dtbl([" ", sa_name, sb_name, "Difference"],
                          cmp_rows, [W*0.30,W*0.23,W*0.23,W*0.24]))
        story.append(PageBreak())
        _sec_n = 6

    # ════════════════════════════════════════════════════════════════
    # RETIREMENT SECTION
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph(f"{_sec_n}  \u2014  Retirement Planning", sH1))
    story.append(HR(1.0, BLUE))
    _sec_n += 1

    story.append(kpi_row([
        ("Pension Gap / mo",        f"\u20ac\u202f{pension_gap_r:,.0f}",    RED),
        ("Capital Needed",          f"\u20ac\u202f{capital_needed_r:,.0f}", BLUE),
        ("FIRE Number",             f"\u20ac\u202f{fire_r:,.0f}",           AMBER),
        ("Projected Capital at Ret",f"\u20ac\u202f{proj_cap_ret:,.0f}",
         GREEN if proj_cap_ret >= capital_needed_r else RED),
    ]))
    story.append(Spacer(1,0.2*cm))
    _surplus = proj_cap_ret - capital_needed_r
    if _surplus >= 0:
        story.append(Paragraph(
            f"\u2705  Projected capital exceeds the capital needed by \u20ac\u202f{_surplus:,.0f}. "
            f"Your retirement plan looks on track.", sOK))
    else:
        story.append(Paragraph(
            f"\u26a0\ufe0f  Shortfall of \u20ac\u202f{abs(_surplus):,.0f} at retirement age {ret_age_r}. "
            f"Consider increasing savings, adjusting retirement age, or reducing target income.", sWRN))

    # CHART A: Portfolio growth to retirement
    def _draw_grow(fig, ax, **kw):
        ax.fill_between(range(len(_port_curve)), _port_curve,
                        alpha=0.1, color=kw["BLUE"])
        ax.plot(range(len(_port_curve)), _port_curve,
                color=kw["BLUE"], lw=2.5, label="Projected Portfolio")
        ax.axhline(capital_needed_r, color=kw["RED"], lw=1.5, ls="--",
                   label=f"Capital Needed  \u20ac\u202f{capital_needed_r/1e3:.0f}k")
        ax.axhline(fire_r, color=kw["AMBER"], lw=1.2, ls=":",
                   label=f"FIRE Number  \u20ac\u202f{fire_r/1e3:.0f}k")
        xticks = list(range(0, len(_port_curve), max(1, len(_port_curve)//8)))
        ax.set_xticks(xticks)
        ax.set_xticklabels([str(_port_years[i]) for i in xticks],
                           rotation=30, ha="right", fontsize=6.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x/1e3:.0f}k")
        ax.legend(fontsize=7, framealpha=0.9)
        ax.set_title("Portfolio Growth to Retirement", fontsize=9,
                     fontweight="bold", color="#1e293b", pad=6)

    story += embed(_draw_grow,
                   "Blue = projected portfolio, red dashed = capital needed, amber dotted = FIRE number.")

    # CHART B: income waterfall (bar chart)
    _bar_labels = ["AOW (state)", "Occ. Pension", "Private Capital (SWR)", "Target"]
    _bar_values = [ret_aow_r, ret_pension_r,
                   proj_cap_ret * ret_swr_r / 12, ret_target]
    _bar_colors_m = [TEAL.hexval(), BLUE.hexval(), GREEN.hexval(), RED.hexval()]

    def _draw_waterfall(fig, ax, **kw):
        bars = ax.bar(_bar_labels, _bar_values,
                      color=[kw["TEAL"], kw["BLUE"], kw["GREEN"], kw["RED"]],
                      width=0.55, zorder=3)
        for bar, val in zip(bars, _bar_values):
            ax.text(bar.get_x() + bar.get_width()/2,
                    bar.get_height() + max(_bar_values)*0.02,
                    f"\u20ac\u202f{val:,.0f}", ha="center", va="bottom",
                    fontsize=7, color="#1e293b", fontweight="bold")
        ax.set_ylabel("\u20ac / month", fontsize=7)
        ax.set_title("Monthly Retirement Income Sources vs Target",
                     fontsize=9, fontweight="bold", color="#1e293b", pad=6)
        ax.set_ylim(0, max(_bar_values) * 1.2)
        for tick in ax.get_xticklabels():
            tick.set_fontsize(7)

    story += embed(_draw_waterfall,
                   "Teal = AOW, blue = occupational pension, green = private capital withdrawal, red = target.")

    # CHART C: portfolio depletion
    _dep_ages = [ret_age_r + y for y in range(len(_dep_curve_r))]

    def _draw_depletion(fig, ax, **kw):
        ax.fill_between(range(len(_dep_curve_r)), _dep_curve_r,
                        alpha=0.1, color=kw["GREEN"])
        ax.plot(range(len(_dep_curve_r)), _dep_curve_r,
                color=kw["GREEN"], lw=2.5, label="Remaining Capital")
        ax.axhline(0, color=kw["RED"], lw=1, ls="-")
        xticks = list(range(0, len(_dep_curve_r), max(1, len(_dep_curve_r)//8)))
        ax.set_xticks(xticks)
        ax.set_xticklabels([str(_dep_ages[i]) for i in xticks],
                           rotation=30, ha="right", fontsize=6.5)
        ax.yaxis.set_major_formatter(lambda x, _: f"\u20ac\u202f{x/1e3:.0f}k")
        ax.legend(fontsize=7, framealpha=0.9)
        ax.set_title("Portfolio Depletion in Retirement (by Age)",
                     fontsize=9, fontweight="bold", color="#1e293b", pad=6)

    story += embed(_draw_depletion,
                   "Shows how long your projected capital sustains the pension gap withdrawal.")

    # Sensitivity table
    story.append(Paragraph("Capital Needed \u2014 Sensitivity (Retirement Age \u00d7 Target Income)", sH2))
    _ages_s   = [55, 60, 62, 65, 67, 70]
    _incomes_s= [2000, 2500, 3000, 3500, 4000, 5000]
    _stbl     = []
    for _age in _ages_s:
        _row = [f"Age {_age}"]
        for _inc in _incomes_s:
            _gap = max(_inc - pillar12_r, 0)
            _cap = _gap * 12 / ret_swr_r if ret_swr_r > 0 else 0
            _ok  = proj_cap_ret >= _cap
            _cell = f"\u20ac\u202f{_cap/1e6:.2f}M" if _cap >= 1e6 else f"\u20ac\u202f{_cap:,.0f}"
            _row.append(("\u2713 " if _ok else "! ") + _cell)
        _stbl.append(_row)
    _s_hdrs = [""] + [f"\u20ac\u202f{i:,}/mo" for i in _incomes_s]
    _s_cw   = [W*0.14] + [W*0.143]*6
    story.append(dtbl(_s_hdrs, _stbl, _s_cw))
    story.append(Paragraph(
        "\u2713 = your projected capital covers this combination.  "
        "! = shortfall. Assumes current SWR and AOW + occupational pension as configured.", sCap))
    story.append(PageBreak())

    # ════════════════════════════════════════════════════════════════
    # SETUP SUMMARY
    # ════════════════════════════════════════════════════════════════
    story.append(Paragraph(f"{_sec_n}  \u2014  Setup Summary", sH1))
    story.append(HR(1.0, BLUE))
    setup_rows = [
        ["Your gross income",   f"\u20ac\u202f{p['inc_s']:,.0f}/yr"],
        ["Partner income",      f"\u20ac\u202f{p['inc_p']:,.0f}/yr" if p["partner"] else "\u2014"],
        ["30% Ruling (You)",    f"{'Yes' if p.get('ruling_s') else 'No'} \u2014 "
                                f"{p.get('rs_s',p['rs'])}\u2013{p.get('re_s',p['re'])}"],
        ["Salary growth",       f"{p.get('sal_growth',0)*100:.1f}%/yr"],
        ["Current rent",        f"\u20ac\u202f{p['rent']:,.0f}/mo"],
        ["House price",         f"\u20ac\u202f{p['house_price']:,.0f}"],
        ["Down payment",        f"{p['dp']*100:.0f}%  (\u20ac\u202f{p['house_price']*p['dp']:,.0f})"],
        ["Mortgage rate",       f"{p['mort_rate']*100:.2f}%"],
        ["Mortgage type",       p.get("mort_type","Annuity")],
        ["Purchase date",       f"{p['by']}-{p['bm']:02d}"],
        ["Starting savings",    f"\u20ac\u202f{p.get('savings',0):,.0f}"],
        ["House appreciation",  f"{p.get('ha',0.03)*100:.1f}%/yr"],
        ["Investment return",   f"{p.get('ir',0.05)*100:.1f}%/yr"],
        ["Projection horizon",  f"{p.get('n_years',5)} years"],
        ["Current age",         str(ret_current_age)],
        ["Retirement age",      str(ret_age_r)],
        ["Target ret. income",  f"\u20ac\u202f{ret_target:,.0f}/mo"],
        ["AOW expected",        f"\u20ac\u202f{ret_aow_r:,.0f}/mo"],
        ["Occ. pension",        f"\u20ac\u202f{ret_pension_r:,.0f}/mo"],
        ["Safe withdrawal rate",f"{ret_swr_r*100:.1f}%/yr"],
        ["Pre-ret. return",     f"{ret_ret_pre*100:.1f}%/yr"],
        ["Post-ret. return",    f"{ret_ret_post*100:.1f}%/yr"],
    ]
    story.append(dtbl(["Parameter","Value"], setup_rows, [W*0.52,W*0.48]))
    story.append(Spacer(1,0.6*cm))
    story.append(HR(0.3, RULE))
    story.append(Paragraph(
        "Generated by the Dutch Financial Dashboard (Pro Plan). "
        "All figures are approximations. "
        "This document does not constitute financial or tax advice. "
        "Consult a belastingadviseur or certified financieel planner.",
        sCap))

    doc.build(story, onFirstPage=_on_page, onLaterPages=_on_page)
    return buf.getvalue()

# ════════════════════════════════════════════════════════════════════════════════
# TIER SYSTEM — driven by sidebar toggle
# ════════════════════════════════════════════════════════════════════════════════
# IS_PAID is set from the 'dark_mode' toggle in the sidebar.
# dark_mode ON  (default) → Free tier  (IS_PAID = False)
# dark_mode OFF           → Pro tier   (IS_PAID = True)

# Initialise session state so IS_PAID is available before the sidebar renders.
if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True   # default ON = Free

IS_PAID: bool = not st.session_state["dark_mode"]

def _pro_chart_overlay(section_label: str = "Pro Charts") -> None:
    """Render a styled upgrade banner below greyed-out chart sections (free tier)."""
    st.markdown(
        f"<div style=\"background:linear-gradient(135deg,rgba(26,26,46,0.96),rgba(22,33,62,0.98));"
        f"border:2px solid #f1c40f88;border-radius:12px;"
        f"padding:24px 32px;margin:14px 0;text-align:center;"
        f"box-shadow:0 4px 28px rgba(0,0,0,0.55);\">"
        f"<div style=\"font-size:30px;margin-bottom:8px\">🔒</div>"
        f"<div style=\"font-size:18px;font-weight:700;color:#f1c40f;margin-bottom:8px\">"
        f"Upgrade to Pro to unlock {section_label}</div>"
        f"<div style=\"color:#ccc;font-size:13px;line-height:1.8;margin-bottom:16px\">"
        f"The charts above are a <b>preview</b> of what you'll unlock with a "
        f"<b style=\"color:#f1c40f\">Pro</b> plan. Get full projections, scenario comparison, "
        f"actuals tracking, mortgage analysis, data export, and more."
        f"</div>"
        f"<span style=\"background:#f1c40f;color:#000;font-weight:700;"
        f"padding:9px 26px;border-radius:8px;font-size:14px\">⭐ Upgrade to Pro</span>"
        f"</div>",
        unsafe_allow_html=True
    )


def _paid_gate(label: str = "Pro feature", icon: str = "🔒", compact: bool = False) -> None:
    """Render a locked-feature callout for free-tier users."""
    if compact:
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);"
            f"border:1px solid #f1c40f44;border-radius:8px;"
            f"padding:10px 14px;margin:4px 0;opacity:0.92'>"
            f"<span style='font-size:15px'>{icon}</span> "
            f"<b style='color:#f1c40f'>{label}</b> "
            f"<span style='color:#aaa;font-size:12px'>— <b>Pro</b> plan only</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"<div style='background:linear-gradient(135deg,#1a1a2e,#16213e);"
            f"border:1.5px solid #f1c40f88;border-radius:10px;"
            f"padding:18px 22px;margin:10px 0'>"
            f"<div style='font-size:22px;margin-bottom:6px'>{icon} "
            f"<b style='color:#f1c40f'>{label}</b></div>"
            f"<div style='color:#ccc;font-size:14px;line-height:1.7'>"
            f"This feature is included in the <b style='color:#f1c40f'>Pro plan</b>. "
            f"Upgrade to unlock full projections, actuals tracking, scenario comparison, "
            f"future expense planning, childcare subsidy calculator, and data export."
            f"</div>"
            f"<div style='margin-top:12px'>"
            f"<span style='background:#f1c40f;color:#000;font-weight:700;"
            f"padding:6px 16px;border-radius:6px;font-size:13px'>⭐ Upgrade to Pro</span>"
            f"</div></div>",
            unsafe_allow_html=True
        )


# ── No server-side file storage — all persistence is via download/upload ─────────
# Each browser session is independent; multiple users can run simultaneously.

DEFAULTS = dict(
    # Income
    inc_s=60000, inc_s_incl_vg=False, use_net_input=True, net_mo_input=3500,
    use_net_input_p=True, net_mo_input_p=3500,
    partner=False, inc_p=60000, sal_growth=0.02,
    sal_growth_p=0.02,
    ab_mode=False,
    # 30% ruling
    rs=2023, re=2028,
    rs_s_start=2023, rs_p_start=2023,
    ruling_s=True, rs_s=2023, re_s=2028,
    ruling_p=False,  rs_p=2023, re_p=2028,
    # Housing
    rent=1500, by=2027, bm=1,
    house_price=400000, dp=0.00, mort_rate=0.040, mort_type="Annuity (annuïteit)",
    # Expenses
    hi=150, cf=80, ci=80, gr=350, ot=250,
    utilities=150, phone=40, subscriptions=40, gym=30, dog=0,
    # Projection
    savings=50000, n_years=10, ha=0.03, ir=0.05,
    global_inflation=0.0,
    # House sale
    sell_house=True, sy=2032, sm=1,
    already_owns=False, current_home_value=400000,
    # Childcare
    n_kdv=0, n_bso=0, kdv_hrs=None, bso_hrs=None,
    kdv_rate=None, bso_rate=None,
    kot_start_ym="2027-01", kot_end_ym="",
    # Future expenses & notes
    future_expenses=[],
    exp_notes={},
    exp_growth={},
    # Actuals date range
    hist_start="2026-01", hist_end="2026-12",
    # Net worth
    scenario_label="Current Situation",
    # Retirement
    ret_age=67, ret_target_income=3500, ret_aow=1450,
    ret_pension=500, ret_return_pre=0.07, ret_return_post=0.04,
    ret_inflation=0.025, ret_swr=0.035,
    ret_current_age=32,
)

# ── Settings serialisation helpers ───────────────────────────────────────────────

def _enc(v):
    """Encode a settings value for CSV storage."""
    if v is None:
        return json.dumps(None)
    if isinstance(v, (bool, list, dict)):
        return json.dumps(v)
    return v

def _parse_settings_df(df):
    """Parse a settings DataFrame (index=keys, columns A/B) into two dicts."""
    def parse_row(col):
        d = DEFAULTS.copy()
        if col not in df.columns:
            return d
        for k, v in df[col].items():
            try:
                parsed = json.loads(v)
            except Exception:
                parsed = v
            if k == "future_expenses":
                d[k] = parsed if isinstance(parsed, list) else []
            elif k in ("exp_notes", "exp_growth"):
                d[k] = parsed if isinstance(parsed, dict) else {}
            elif k in d:
                default_val = d[k]
                if isinstance(default_val, bool):
                    d[k] = bool(int(parsed))
                elif default_val is None:
                    if parsed is None or parsed in ("", "None"):
                        d[k] = None
                    else:
                        try:
                            d[k] = float(parsed)
                        except (ValueError, TypeError):
                            d[k] = None
                else:
                    try:
                        d[k] = type(default_val)(parsed)
                    except (ValueError, TypeError):
                        d[k] = default_val
        return d
    return parse_row("A"), parse_row("B")

def settings_to_csv_bytes(pa, pb) -> bytes:
    """Serialise scenario A & B dicts to CSV bytes for download."""
    rows = {k: {"A": _enc(v), "B": _enc(pb.get(k, DEFAULTS.get(k)))}
            for k, v in pa.items()}
    return pd.DataFrame(rows).T.to_csv().encode()

def settings_from_uploaded_file(uploaded_file) -> tuple:
    """Parse an uploaded settings CSV back into (dict_A, dict_B)."""
    try:
        df = pd.read_csv(uploaded_file, index_col=0)
        return _parse_settings_df(df)
    except Exception:
        return DEFAULTS.copy(), DEFAULTS.copy()

def load_settings():
    """Return settings from session state (populated by upload or defaults)."""
    sa = st.session_state.get("saved_A")
    sb = st.session_state.get("saved_B")
    if sa is None:
        sa = DEFAULTS.copy()
        st.session_state["saved_A"] = sa
    if sb is None:
        sb = DEFAULTS.copy()
        st.session_state["saved_B"] = sb
    return sa, sb

_ACTUALS_COLS = ["month", "inc_s_actual", "inc_p_actual", "savings_actual", "note"]

def load_actuals() -> pd.DataFrame:
    """Return the actuals DataFrame stored in session state."""
    df = st.session_state.get("actuals_df")
    if df is None or df.empty:
        return pd.DataFrame(columns=_ACTUALS_COLS)
    return df.copy()

def save_actuals(df: pd.DataFrame) -> None:
    """Persist actuals DataFrame to session state."""
    st.session_state["actuals_df"] = df.copy()

def actuals_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """Serialise actuals DataFrame to CSV bytes for download."""
    return df.to_csv(index=False).encode()

def actuals_from_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Parse an uploaded actuals CSV back into a DataFrame."""
    empty = pd.DataFrame(columns=_ACTUALS_COLS)
    try:
        df = pd.read_csv(uploaded_file)
        for col in _ACTUALS_COLS:
            if col not in df.columns:
                df[col] = None
        extra = [c for c in df.columns if c not in _ACTUALS_COLS]
        return df[_ACTUALS_COLS + extra]
    except Exception:
        return empty

def parse_bank_statement(uploaded_file):
    """Parse an ING bank statement CSV (semicolon-delimited).

    Columns expected:
        Date ; Name / Description ; Account ; Counterparty ; Code ;
        Debit/credit ; Amount (EUR) ; Transaction type ; Notifications

    Returns DataFrame with columns: month (YYYY-MM), amount (float).
    Only Credit rows are included.
    """
    try:
        df = pd.read_csv(uploaded_file, sep=";", dtype=str)
    except Exception:
        uploaded_file.seek(0)
        df = pd.read_csv(uploaded_file, sep=";", dtype=str, header=0)

    df.columns = [c.strip() for c in df.columns]

    credit_col = "Debit/credit"
    if credit_col not in df.columns:
        raise ValueError(f"Column '{credit_col}' not found. Available: {list(df.columns)}")
    df = df[df[credit_col].str.strip().str.lower() == "credit"].copy()

    amount_col = "Amount (EUR)"
    if amount_col not in df.columns:
        raise ValueError(f"Column '{amount_col}' not found.")
    df["amount_parsed"] = (
        df[amount_col].str.strip()
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )

    date_col = "Date"
    if date_col not in df.columns:
        raise ValueError(f"Column '{date_col}' not found.")
    df["month"] = pd.to_datetime(df[date_col].str.strip(), format="%Y%m%d").dt.strftime("%Y-%m")

    monthly = (
        df.groupby("month", as_index=False)["amount_parsed"]
        .sum()
        .rename(columns={"amount_parsed": "amount"})
    )
    monthly["amount"] = monthly["amount"].round(2)
    return monthly.sort_values("month").reset_index(drop=True)

st.set_page_config(
    page_title="🇳🇱 Dutch Financial Dashboard",
    layout="wide",
    page_icon="🇳🇱",
    initial_sidebar_state="expanded",
)

# ── Mobile CSS injection ─────────────────────────────────────────────────────────
def _inject_mobile_css(narrow: bool) -> None:
    """Inject CSS that adapts layout to narrow/mobile screens."""
    # Always inject base styles
    st.markdown("""
<style>
.js-plotly-plot { max-width: 100% !important; }
[data-testid="stDataFrame"] { overflow-x: auto; }
</style>
""", unsafe_allow_html=True)

    if not narrow:
        return

    st.markdown("""
<style>
/* ── Narrow / mobile layout ─────────────────────────────────────── */
.block-container {
    max-width: 100% !important;
    padding-left: 0.4rem !important;
    padding-right: 0.4rem !important;
    padding-top: 0.5rem !important;
}

/* Base font — readable on small screens */
.main .block-container { font-size: 15px !important; }
p, li { font-size: 15px !important; line-height: 1.6 !important; }
h1 { font-size: 20px !important; }
h2 { font-size: 17px !important; }
h3 { font-size: 15px !important; }
label { font-size: 14px !important; line-height: 1.5 !important; }

/* Metric tiles — readable values, compact labels */
[data-testid="stMetricLabel"]  { font-size: 11px !important; line-height: 1.3 !important; }
[data-testid="stMetricValue"]  { font-size: 19px !important; font-weight: 700 !important; }
[data-testid="stMetricDelta"]  { font-size: 11px !important; }

/* Tab bar — touch-friendly, text legible */
button[data-baseweb="tab"] {
    padding: 8px 4px !important;
    font-size: 10px !important;
    min-height: 48px !important;
    line-height: 1.2 !important;
}

/* All buttons — 48px minimum tap target */
.stButton > button,
button[kind="primary"],
button[kind="secondary"] {
    min-height: 48px !important;
    font-size: 15px !important;
    border-radius: 10px !important;
    padding: 10px 14px !important;
    width: 100% !important;
}

/* Number inputs — large enough to tap without zooming */
[data-testid="stNumberInput"] input {
    font-size: 16px !important;
    min-height: 48px !important;
    padding: 8px 10px !important;
    -webkit-appearance: none;
}
[data-testid="stNumberInput"] button {
    min-width: 40px !important;
    min-height: 48px !important;
    font-size: 18px !important;
}

/* Text inputs */
[data-testid="stTextInput"] input {
    font-size: 16px !important;
    min-height: 48px !important;
    padding: 8px 10px !important;
}

/* Select boxes */
[data-testid="stSelectbox"] > div > div {
    font-size: 15px !important;
    min-height: 48px !important;
}

/* Sliders — bigger thumb, more padding for finger */
[data-testid="stSlider"] {
    padding-top: 6px !important;
    padding-bottom: 10px !important;
}
[data-testid="stSlider"] [role="slider"] {
    width: 28px !important;
    height: 28px !important;
}
[data-testid="stSlider"] [data-testid="stTickBarMin"],
[data-testid="stSlider"] [data-testid="stTickBarMax"] {
    font-size: 12px !important;
}

/* Expander headers — big tap targets */
[data-testid="stExpander"] summary {
    font-size: 14px !important;
    padding: 12px 8px !important;
    min-height: 52px !important;
    line-height: 1.4 !important;
}

/* Checkbox + radio — bigger hit areas */
[data-testid="stCheckbox"] label {
    font-size: 15px !important;
    min-height: 44px !important;
    padding: 6px 0 !important;
    display: flex !important;
    align-items: center !important;
}
[data-testid="stRadio"] label {
    font-size: 15px !important;
    min-height: 44px !important;
    padding: 6px 0 !important;
}
[data-testid="stCheckbox"] input[type="checkbox"],
[data-testid="stRadio"]    input[type="radio"] {
    width: 22px !important;
    height: 22px !important;
    margin-right: 8px !important;
}

/* Toggle */
[data-testid="stToggle"] label {
    font-size: 15px !important;
    min-height: 44px !important;
}
[data-testid="stToggle"] [role="switch"] {
    width: 52px !important;
    height: 28px !important;
}

/* Caption and small text */
.stCaption, small { font-size: 13px !important; line-height: 1.5 !important; }

/* Download / upload buttons */
[data-testid="stDownloadButton"] > button {
    min-height: 52px !important;
    font-size: 15px !important;
    width: 100% !important;
}
[data-testid="stFileUploader"] {
    font-size: 14px !important;
}

/* Info / warning / success boxes */
[data-testid="stAlert"] { font-size: 14px !important; padding: 10px !important; }

/* Dividers */
hr { margin: 0.5rem 0 !important; }

/* Plotly charts — never overflow */
.js-plotly-plot .plotly { overflow: hidden !important; }
</style>
""", unsafe_allow_html=True)

# ── Theme ────────────────────────────────────────────────────────────────────────
DARK = dict(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117", font=dict(color="#e0e0e0"))

def chart_layout(title, yaxis_title="€", height=400, xaxis_title="", **kw):
    """Return a Plotly layout dict, adapted for narrow/mobile when needed."""
    _is_narrow = st.session_state.get("narrow_mode", False)
    _height    = 240 if _is_narrow else height
    _title_sz  = 11  if _is_narrow else 15
    _legend    = dict(
        orientation="h",
        y=-0.32 if _is_narrow else -0.20,
        x=0, xanchor="left",
        font=dict(size=10 if _is_narrow else 11),
        bgcolor="rgba(0,0,0,0)",
        itemclick="toggleothers",
        itemsizing="constant",
    )
    return dict(
        title=dict(text=title, font=dict(size=_title_sz)),
        xaxis_title=xaxis_title,
        yaxis_title="" if _is_narrow else yaxis_title,
        xaxis=dict(tickfont=dict(size=10 if _is_narrow else 12)),
        yaxis=dict(tickfont=dict(size=10 if _is_narrow else 12)),
        legend=_legend,
        hovermode="x unified",
        height=_height,
        margin=dict(l=30, r=8, t=32, b=110) if _is_narrow else dict(t=50, b=80),
        **DARK, **kw
    )

# ════════════════════════════════════════════════════════════════════════════════
# TAX ENGINE
# ════════════════════════════════════════════════════════════════════════════════

BOX1 = {
    2026: dict(limit=38441, r1=0.3697, r2=0.4950),
    2027: dict(limit=39500, r1=0.3693, r2=0.4950),
    2028: dict(limit=40600, r1=0.3690, r2=0.4950),
    2029: dict(limit=41700, r1=0.3693, r2=0.4950),
    2030: dict(limit=42900, r1=0.3693, r2=0.4950),
}
CREDITS = {
    2026: dict(ahk_max=3362, ahk_s=24812, ahk_e=75518, ak_max=5052, ak_s=38098, ak_e=124935),
    2027: dict(ahk_max=3450, ahk_s=25200, ahk_e=76500, ak_max=5150, ak_s=39000, ak_e=127000),
    2028: dict(ahk_max=3500, ahk_s=25800, ahk_e=77500, ak_max=5200, ak_s=39900, ak_e=129000),
    2029: dict(ahk_max=3560, ahk_s=26400, ahk_e=78500, ak_max=5300, ak_s=40800, ak_e=131000),
    2030: dict(ahk_max=3620, ahk_s=27000, ahk_e=79500, ak_max=5400, ak_s=41700, ak_e=133000),
}
ZVW_RATE, ZVW_MAX = 0.0565, 71628
MRI_RATE           = 0.3697
BOX3_THRESHOLD     = 57000
BOX3_RATE_SAVE     = 0.0154
BOX3_TAX_RATE      = 0.3600

def _po(val, lo, hi):
    if val <= lo: return 1.0
    if val >= hi: return 0.0
    return (hi - val) / (hi - lo)

def ruling_rate(start_year):
    """Return the tax-exempt fraction under the 30% ruling based on the year the ruling first started.
    
    Rules (based on official Dutch legislation as of 2025):
    - Started <= 2023: full 30% for entire 5-year duration (grandfathered).
    - Started 2024-2026: 30% in 2024-2026, then 27% from 2027 onward.
    - Started >= 2027: flat 27% for entire duration.
    Returns a dict mapping calendar_year -> exempt_fraction (e.g. 0.30 or 0.27).
    """
    rates = {}
    end_year = start_year + 5   # ruling is 5 years; end_year is first year NOT covered
    for yr in range(start_year, end_year):
        if start_year <= 2023:
            rates[yr] = 0.30
        elif start_year <= 2026:   # 2024 / 2025 / 2026 starters
            rates[yr] = 0.30 if yr <= 2026 else 0.27
        else:                       # 2027+ starters
            rates[yr] = 0.27
    return rates

def income_tax(gross, year, a30=False, ruling_exempt=0.30):
    taxable = gross * (1 - ruling_exempt) if a30 else gross
    b = BOX1.get(year, BOX1[2030])
    if taxable <= b["limit"]: return taxable * b["r1"]
    return b["limit"] * b["r1"] + (taxable - b["limit"]) * b["r2"]

def ahk(gross, year):
    c = CREDITS.get(year, CREDITS[2030])
    return c["ahk_max"] * _po(gross, c["ahk_s"], c["ahk_e"])

def ak(gross, year):
    c = CREDITS.get(year, CREDITS[2030])
    if gross <= 10000: credit = gross * 0.08
    elif gross <= c["ak_s"]: credit = c["ak_max"]
    else: credit = c["ak_max"] * _po(gross, c["ak_s"], c["ak_e"])
    return max(credit, 0)

def zvw(gross, a30=False, ruling_exempt=0.30):
    return min(gross * (1 - ruling_exempt) if a30 else gross, ZVW_MAX) * ZVW_RATE

def net_annual_calc(gross, year, a30=False, ruling_exempt=0.30):
    tax = income_tax(gross, year, a30, ruling_exempt)
    return gross - max(tax - ahk(gross, year) - ak(gross, year), 0) - zvw(gross, a30, ruling_exempt)

def net_monthly_calc(gross, year, a30=False, ruling_exempt=0.30):
    return net_annual_calc(gross, year, a30, ruling_exempt) / 12

def zorgtoeslag(gross_combined, has_partner):
    if has_partner:
        return max(290 * max(0, 1 - (gross_combined / 47000) ** 2), 0)
    return max(160 * max(0, 1 - (gross_combined / 38000) ** 2), 0)

# ── Kinderopvangtoeslag (childcare benefit) ─────────────────────────────────
# Source: Besluit kinderopvangtoeslag 2026 (Rijksoverheid, definitief besluit).
# Max hourly rates indexed +4.84% from 2025 (official 2026 figure).
# Subsidy %: 96% for toetsingsinkomen up to ~€56,413; tapers to 36.5% at €235,689+.
KDV_HOURLY_MAX  = 11.23     # max hourly rate dagopvang/PSZ 2026 (€), indexed ~4%/yr after
BSO_HOURLY_MAX  =  9.98     # max hourly rate BSO 2026
GAO_HOURLY_MAX  =  8.49     # max hourly rate gastouderopvang 2026
KDV_HRS_MO      = 230       # max compensated hrs/mo per child
BSO_HRS_MO      = 140       # max compensated hrs/mo per child (BSO)

def kdv_subsidy_pct(toetsingsinkomen):
    """Subsidy % for dagopvang (1st child) vs household toetsingsinkomen.
    Based on official 2026 table: 96% max up to €56,413; 36.5% floor above €235,689.
    Piecewise linear interpolation between official breakpoints."""
    y = toetsingsinkomen
    if y <= 24149:   return 0.96          # max band (all incomes per 2025 step)
    if y <= 56413:   return 0.96          # 2026 step: extended max band
    if y <= 90000:   return 0.96 - 0.18 * (y - 56413) / (90000 - 56413)
    if y <= 150000:  return 0.78 - 0.28 * (y - 90000) / (150000 - 90000)
    if y <= 235689:  return 0.50 - 0.135 * (y - 150000) / (235689 - 150000)
    return 0.365

def kinderopvangtoeslag(gross_combined, n_children_kdv=0, n_children_bso=0,
                        kdv_hrs_mo=None, bso_hrs_mo=None,
                        actual_kdv_rate=None, actual_bso_rate=None, yr=2026):
    """Monthly kinderopvangtoeslag subsidy.
    gross_combined: household toetsingsinkomen (approx gross income)
    n_children_kdv: number of children in dagopvang
    n_children_bso: number of children in BSO (after-school care)
    kdv_hrs_mo / bso_hrs_mo: actual monthly hours used (defaults to max)
    actual_kdv_rate / actual_bso_rate: actual hourly rate paid (defaults to max)
    yr: calendar year (for indexing)
    """
    if n_children_kdv == 0 and n_children_bso == 0:
        return 0.0
    idx = (1.025) ** (yr - 2026)   # index hourly caps 2.5%/yr
    kdv_cap = KDV_HOURLY_MAX * idx
    bso_cap = BSO_HOURLY_MAX * idx
    pct = kdv_subsidy_pct(gross_combined)
    # First child gets full pct; subsequent children get min(pct, 0.94) per rules
    def _child_pct(rank, base_pct):
        return base_pct if rank == 1 else min(base_pct, 0.94)
    subsidy = 0.0
    for rank in range(1, n_children_kdv + 1):
        hrs  = kdv_hrs_mo if kdv_hrs_mo is not None else KDV_HRS_MO
        rate = min(actual_kdv_rate, kdv_cap) if actual_kdv_rate else kdv_cap
        subsidy += _child_pct(rank, pct) * rate * hrs
    for rank in range(1, n_children_bso + 1):
        hrs  = bso_hrs_mo if bso_hrs_mo is not None else BSO_HRS_MO
        rate = min(actual_bso_rate, bso_cap) if actual_bso_rate else bso_cap
        subsidy += _child_pct(rank, pct) * rate * hrs
    return round(subsidy, 2)

def box3_annual(savings, n_persons):
    thresh = BOX3_THRESHOLD * n_persons
    if savings <= thresh: return 0
    return (savings - thresh) * BOX3_RATE_SAVE * BOX3_TAX_RATE

def mort_payment(price, dp, rate, yrs=30):
    """Annuity monthly payment (fixed)."""
    loan = price * (1 - dp)
    mr   = rate / 12
    n    = yrs * 12
    if mr == 0: return loan / n
    return loan * (mr * (1 + mr)**n) / ((1 + mr)**n - 1)

def linear_principal(price, dp, yrs=30):
    """Linear mortgage: fixed principal repayment per month."""
    loan = price * (1 - dp)
    return loan / (yrs * 12)

def amortisation_schedule(price, dp, rate, mort_type="Annuity (annuïteit)", yrs=30):
    """
    Build full month-by-month amortisation table for annuity or linear mortgage.
    Returns list of dicts with: month, balance, interest, principal, payment, mri_benefit, net_payment
    """
    loan      = price * (1 - dp)
    mr        = rate / 12
    n         = yrs * 12
    annuity_p = mort_payment(price, dp, rate, yrs)
    lin_prin  = linear_principal(price, dp, yrs)
    rows = []
    balance = loan
    for i in range(1, n + 1):
        interest = balance * mr
        if "Linear" in mort_type:
            principal = lin_prin
            payment   = principal + interest
        else:
            payment   = annuity_p
            principal = payment - interest
        balance   = max(balance - principal, 0)
        mri_ben   = interest * MRI_RATE          # monthly tax benefit
        net_pay   = payment - mri_ben            # effective net cost after deduction
        yr        = 2026 + (i - 1) // 12
        mo        = ((i - 1) % 12) + 1
        rows.append(dict(
            Month=i, Year=yr, MonthNo=mo,
            Date=pd.Timestamp(year=yr, month=mo, day=1),
            Balance=round(balance),
            Interest=round(interest),
            Principal=round(principal),
            Payment=round(payment),
            MRI_Benefit=round(mri_ben),
            Net_Payment=round(net_pay),
        ))
    return pd.DataFrame(rows)

# ════════════════════════════════════════════════════════════════════════════════
# SIMULATION
# ════════════════════════════════════════════════════════════════════════════════

def run_sim(p):
    n_months = p.get("n_years", 5) * 12
    months   = pd.date_range(start="2026-01-01", periods=n_months, freq="MS")
    already_owns  = p.get("already_owns", False)
    if already_owns:
        # Owner: start with current home value and approximate remaining mortgage
        # house_price = original purchase price; current_home_value = today's value
        _chv  = p.get("current_home_value", p["house_price"])
        mp    = mort_payment(p["house_price"], p["dp"], p["mort_rate"])
        loan  = p["house_price"] * (1 - p["dp"])
        costs = 0   # buying costs already paid
        # Approximate remaining balance (assume owned since by/bm)
        _months_owned = max(0, (2026 - p.get("by", 2024)) * 12
                             + (1  - p.get("bm", 1)))
        _df_amort = amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"],
                                           p.get("mort_type", "Annuity (annuïteit)"), 30)
        mb    = _df_amort.iloc[min(_months_owned, len(_df_amort)-1)]["Balance"]
        # Start with current home value as equity base; savings remain as cash
        buy_cash  = p["savings"]
        rent_cash = p["savings"]
        hv        = _chv
        purchase_done = True   # already purchased
        mo_owned  = _months_owned + 1
    else:
        mp       = mort_payment(p["house_price"], p["dp"], p["mort_rate"])
        loan     = p["house_price"] * (1 - p["dp"])
        costs    = p["house_price"] * 0.02 + 3500
        mb        = loan
        buy_cash  = p["savings"]
        rent_cash = p["savings"]
        hv        = 0
        mo_owned  = 0
        purchase_done = False
    house_sold   = False
    main, buy_r, rent_r = [], [], []

    for dt in months:
        yr = dt.year; mo = dt.month
        a30_s = p.get("ruling_s", True)  and p.get("rs_s", p["rs"]) <= yr < p.get("re_s", p["re"])
        a30_p = p.get("ruling_p", False) and p.get("rs_p", p["rs"]) <= yr < p.get("re_p", p["re"])
        a30 = a30_s  # kept for 30% Ruling column in df ("any ruling active")
        # Per-year exempt fraction based on ruling start year
        _rates_s = ruling_rate(p.get("rs_s_start", p.get("rs_s", p["rs"])))
        _rates_p = ruling_rate(p.get("rs_p_start", p.get("rs_p", p["rs"])))
        re_s_yr = _rates_s.get(yr, 0.30) if a30_s else 0.30
        re_p_yr = _rates_p.get(yr, 0.30) if a30_p else 0.30
        n_p = 2 if p["partner"] else 1
        sg   = p.get("sal_growth", 0.0)
        sg_p = p.get("sal_growth_p", sg)   # partner growth; falls back to shared rate
        yrs_e = yr - 2026
        inc_s_adj = p["inc_s"] * (1 + sg)   ** yrs_e
        inc_p_adj = p["inc_p"] * (1 + sg_p) ** yrs_e

        nm_s = net_monthly_calc(inc_s_adj, yr, a30_s, re_s_yr)
        nm_p = net_monthly_calc(inc_p_adj, yr, a30_p, re_p_yr) if p["partner"] else 0
        total_net  = nm_s + nm_p
        gross_comb = inc_s_adj + (inc_p_adj if p["partner"] else 0)
        zts   = zorgtoeslag(gross_comb, p["partner"])
        dt_ym = f"{yr}-{mo:02d}"
        # Gate KOT on start/end YYYY-MM window
        _kot_start = p.get("kot_start_ym", "")
        _kot_end   = p.get("kot_end_ym",   "")
        _kot_active = (not _kot_start or dt_ym >= _kot_start) and \
                      (not _kot_end   or dt_ym <= _kot_end)
        kot   = kinderopvangtoeslag(gross_comb,
                    n_children_kdv=p.get("n_kdv", 0) if _kot_active else 0,
                    n_children_bso=p.get("n_bso", 0) if _kot_active else 0,
                    kdv_hrs_mo=p.get("kdv_hrs", None),
                    bso_hrs_mo=p.get("bso_hrs", None),
                    actual_kdv_rate=p.get("kdv_rate", None),
                    actual_bso_rate=p.get("bso_rate", None), yr=yr)
        # Apply annual growth rates to each expense category
        # global_inflation acts as a floor for all per-category rates
        _eg = p.get("exp_growth", {})
        _ginfl = p.get("global_inflation", 0.0)
        def _eg_val(key, base, _yrs=yrs_e, _eg=_eg, _gi=_ginfl):
            return base * (1 + max(_eg.get(key, 0.0), _gi)) ** _yrs
        fixed = (_eg_val("hi", p["hi"]) + _eg_val("cf", p["cf"])
                 + _eg_val("ci", p["ci"]) + _eg_val("gr", p["gr"])
                 + _eg_val("ot", p["ot"]) + _eg_val("utilities", p.get("utilities",0))
                 + _eg_val("phone", p.get("phone",0)) + _eg_val("subscriptions", p.get("subscriptions",0))
                 + _eg_val("gym", p.get("gym",0)) + _eg_val("dog", p.get("dog",0)))
        for _fe in p.get("future_expenses", []):
            _fe_end = _fe.get("end_ym", "")
            if dt_ym >= _fe.get("start_ym", "9999-99") and (not _fe_end or dt_ym <= _fe_end):
                _fe_start_yr = int(_fe["start_ym"][:4])
                _fe_start_mo = int(_fe["start_ym"][5:7])
                _fe_yrs = (yr - _fe_start_yr) + (mo - _fe_start_mo) / 12
                fixed += _fe["amount"] * (1 + _fe.get("growth", 0.0)) ** max(_fe_yrs, 0)

        mort_is_linear = "Linear" in p.get("mort_type", "Annuity")
        owns = ((yr > p["by"]) or (yr == p["by"] and mo >= p["bm"])) and not house_sold

        # ── Deduct down payment + buying costs in the purchase month ────────
        if owns and not purchase_done:
            buy_cash      -= p["house_price"] * p["dp"] + costs
            purchase_done  = True

        if owns:
            mr_m   = p["mort_rate"] / 12
            int_p  = mb * mr_m
            if mort_is_linear:
                lin_prin_mo = linear_principal(p["house_price"], p["dp"])
                prin_p = lin_prin_mo
                mp_mo  = prin_p + int_p   # variable for linear
            else:
                prin_p = mp - int_p
                mp_mo  = mp
            mb     = max(mb - prin_p, 0)
            mo_owned += 1
            hv     = p["house_price"] * (1 + p["ha"]) ** (mo_owned / 12)
            equity = hv - mb
            mri    = int_p * MRI_RATE     # tax benefit on interest paid
            h_cost = mp_mo
        else:
            hv = equity = mri = int_p = 0
            h_cost = p["rent"]
            mp_mo  = 0

        # ── Sell house event ────────────────────────────────────────────
        sell_event      = False
        sell_hv         = 0.0   # house value at moment of sale (for recording)
        sell_mb         = 0.0   # mortgage balance at moment of sale
        sell_costs_rec  = 0.0   # selling costs
        sell_proceeds   = 0.0   # net cash after mortgage payoff and costs
        if p.get("sell_house", False) and owns:
            _sy = p.get("sy", 9999); _sm = p.get("sm", 1)
            if yr == _sy and mo == _sm:
                sell_hv        = hv
                sell_mb        = mb                           # outstanding mortgage
                sell_costs_rec = hv * 0.015 + 2500           # ~1.5% makelaar + vaste kosten
                sell_proceeds  = hv - sell_mb - sell_costs_rec  # equity minus costs
                buy_cash      += sell_proceeds                # add proceeds to cash
                mb             = 0                           # mortgage fully paid off
                equity         = 0                           # no more equity
                hv             = 0
                mo_owned       = 0
                house_sold     = True                        # latch: prevents house reappearing
                h_cost         = p["rent"]                   # switch back to rent this month
                mri            = 0                           # no more MRI benefit
                sell_event     = True

        b3_mo = box3_annual(max(buy_cash, 0), n_p) / 12 if mo == 12 else 0

        total_exp = h_cost + fixed - mri - zts - kot
        net_sav   = total_net - total_exp

        buy_cash  = buy_cash  * (1 + p["ir"] / 12) + net_sav - b3_mo
        w_buy     = buy_cash + equity

        rent_sav  = total_net - (p["rent"] + fixed - zts - kot)
        rent_cash = rent_cash * (1 + p["ir"] / 12) + rent_sav - b3_mo
        w_rent    = rent_cash

        main.append({"Date":dt,"Year":yr,"Month":mo,"30% Ruling":a30,
                     "Net Self":round(nm_s),"Net Partner":round(nm_p),
                     "Total Net":round(total_net),"Zorgtoeslag":round(zts),"Kinderopvangtoeslag":round(kot),
                     "Housing Cost":round(h_cost),"Interest Paid":round(int_p),
                     "MRI Benefit":round(mri),
                     "Fixed Expenses":round(fixed),"Total Expenses":round(total_exp),
                     "Net Saving":round(net_sav),"Mortgage Balance":round(mb)})
        buy_r.append({"Date":dt,"Year":yr,"Cash (Buy)":round(buy_cash),
                      "Home Equity":round(equity),"House Value":round(hv),
                      "Mortgage Balance":round(mb),"Total Wealth (Buy)":round(w_buy),
                      "Cashflow (Buy)":round(net_sav),
                      "Sell Event":sell_event,
                      "Sale Price":round(sell_hv),
                      "Mortgage Payoff":round(sell_mb),
                      "Selling Costs":round(sell_costs_rec),
                      "Sale Net Proceeds":round(sell_proceeds)})
        rent_r.append({"Date":dt,"Year":yr,"Cash (Rent)":round(rent_cash),
                       "Total Wealth (Rent)":round(w_rent),"Cashflow (Rent)":round(rent_sav)})

    df_m = pd.DataFrame(main)
    df_b = pd.DataFrame(buy_r)
    df_r = pd.DataFrame(rent_r)
    df_w = df_b.merge(df_r[["Date","Cash (Rent)","Total Wealth (Rent)","Cashflow (Rent)"]], on="Date")
    df_w["Wealth Delta"] = df_w["Total Wealth (Buy)"] - df_w["Total Wealth (Rent)"]
    return df_m, df_w

# ── Helper: find sell event row from df_w ────────────────────────────────────
def get_sell_summary(dw):
    """Return dict with sell event details, or None if no sell event."""
    sell_rows = dw[dw["Sell Event"] == True]
    if sell_rows.empty:
        return None
    r = sell_rows.iloc[0]
    return {
        "date":       r["Date"],
        "hv":         r["Sale Price"],
        "mb":         r["Mortgage Payoff"],
        "costs":      r["Selling Costs"],
        "proceeds":   r["Sale Net Proceeds"],
    }

# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def add_events(fig, p, label="", buy_y=0.88, sell_y=0.75, buy_color="#8e44ad", sell_color="#e74c3c"):
    """Add buy-date and sell-date markers.  label="" for single-scenario, "A"/"B" for A/B charts."""
    _is_narrow = st.session_state.get("narrow_mode", False)
    n_months = p.get("n_years", 5) * 12
    months   = pd.date_range(start="2026-01-01", periods=n_months, freq="MS")
    # 30% ruling band — only draw once (when label is "" or "A")
    if label in ("", "A"):
        rm = [d for d in months
             if p.get("ruling_s", True) and p.get("rs_s", p["rs"]) <= d.year < p.get("re_s", p["re"])]
        if rm:
            fig.add_shape(type="rect",
                          x0=rm[0].strftime("%Y-%m-%d"), x1=rm[-1].strftime("%Y-%m-%d"),
                          y0=0, y1=1, xref="x", yref="paper",
                          fillcolor="rgba(241,196,15,0.08)", line_width=0)
            if not _is_narrow:
                fig.add_annotation(x=rm[0].strftime("%Y-%m-%d"), y=0.97, xref="x", yref="paper",
                                   text="30% ruling", showarrow=False, xanchor="left",
                                   font=dict(color="#d4a017", size=10))
    prefix = f" {label}" if label else ""
    buy_str = pd.Timestamp(year=p["by"], month=p["bm"], day=1).strftime("%Y-%m-%d")
    fig.add_shape(type="line", x0=buy_str, x1=buy_str, y0=0, y1=1,
                  xref="x", yref="paper", line=dict(dash="dash", color=buy_color, width=1.5))
    if not _is_narrow:
        fig.add_annotation(x=buy_str, y=buy_y, xref="x", yref="paper",
                           text=f"🏠{prefix}", showarrow=False, xanchor="left",
                           font=dict(color=buy_color, size=12))
    if p.get("sell_house", False):
        sell_str = pd.Timestamp(year=p.get("sy",2031), month=p.get("sm",1), day=1).strftime("%Y-%m-%d")
        fig.add_shape(type="line", x0=sell_str, x1=sell_str, y0=0, y1=1,
                      xref="x", yref="paper", line=dict(dash="dot", color=sell_color, width=1.5))
        if not _is_narrow:
            fig.add_annotation(x=sell_str, y=sell_y, xref="x", yref="paper",
                               text=f"🏷️ Sell{prefix}", showarrow=False, xanchor="left",
                               font=dict(color=sell_color, size=10))

def kpi(col, label, val, delta=None):
    col.metric(label, f"€{val:,.0f}", delta=delta)

def to_excel_bytes(df1, df2):
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df1.to_excel(w, sheet_name="Monthly P&L", index=False)
        df2.to_excel(w, sheet_name="Wealth Accumulation", index=False)
    return buf.getvalue()

def section(label):
    """Render a styled section header inside the setup tab."""
    st.markdown(f"<p style='font-size:13px;font-weight:600;color:#aaa;letter-spacing:1px;"
                f"text-transform:uppercase;margin-bottom:4px;margin-top:16px'>{label}</p>",
                unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# HEADER & SIDEBAR (global only)
# ════════════════════════════════════════════════════════════════════════════════

st.title("🇳🇱 Dutch Financial Dashboard")
st.caption("5-year projection · Box 1 & Box 3 · ZVW · Zorgtoeslag · Hypotheekrenteaftrek · 30% ruling")

# ── Sidebar ──────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🇳🇱 Dutch Dashboard")
    st.divider()

    # ── Tier badge ────────────────────────────────────────────────────────────
    if IS_PAID:
        st.markdown(
            "<div style='background:#1d4ed8;border-radius:10px;"
            "padding:12px 14px;margin-bottom:2px'>"
            "<div style='color:#fbbf24;font-weight:800;font-size:14px;"
            "margin-bottom:6px'>⭐ Pro Plan</div>"
            "<div style='color:#e0e7ff;font-size:11.5px;line-height:1.75'>"
            "✓ Full income &amp; tax projections<br>"
            "✓ Buy vs Rent wealth model<br>"
            "✓ Mortgage analysis (annuity/linear)<br>"
            "✓ Scenario A/B comparison<br>"
            "✓ Actuals vs forecast tracking<br>"
            "✓ Excel &amp; PDF export<br>"
            "✓ Retirement planning &amp; FIRE analysis<br>"
            "✓ Settings save &amp; restore"
            "</div></div>",
            unsafe_allow_html=True)
    else:
        st.markdown(
            "<div style='background:#1e293b;border:1px solid #334155;"
            "border-radius:10px;padding:12px 14px'>"
            "<div style='color:#f1c40f;font-weight:700;font-size:13px;"
            "margin-bottom:6px'>Free Plan</div>"
            "<div style='color:#64748b;font-size:11px;line-height:1.75'>"
            "✓ Income &amp; Tax (preview)<br>"
            "✓ Buy vs Rent (preview)<br>"
            "🔒 Mortgage Analysis<br>"
            "🔒 Scenario A/B<br>"
            "🔒 Actuals Tracking<br>"
            "🔒 Excel &amp; PDF Export<br>"
            "🔒 Settings Save &amp; Restore"
            "</div>"
            "<div style='margin-top:10px'>"
            "<span style='background:#f1c40f;color:#000;font-weight:700;"
            "padding:5px 14px;border-radius:5px;font-size:11px'>⭐ Upgrade to Pro</span>"
            "</div></div>",
            unsafe_allow_html=True)
    st.divider()

    # ── Mobile / narrow display toggle ───────────────────────────────────────
    st.markdown("### 📱 Display")
    st.toggle(
        "Dark Mode",
        value=st.session_state.get("dark_mode", True),
        key="dark_mode",
        help="Toggle display mode.",
    )
    # Re-derive IS_PAID from the current toggle value
    IS_PAID = not st.session_state["dark_mode"]
    _narrow = st.toggle(
        "Narrow layout (mobile)",
        value=st.session_state.get("narrow_mode", False),
        key="narrow_mode",
        help="Enable this on phones or narrow windows. "
             "Collapses multi-column layouts to a single column and scales fonts down.",
    )
    if _narrow:
        st.caption("📱 Narrow mode on — content stacked for small screens.")
    else:
        st.caption("🖥️ Wide mode — full desktop layout.")

    st.divider()
    st.markdown("### 🗂️ Navigation")
    st.caption(
        "Use the **tabs** across the top to switch sections:\n\n"
        "⚙️ **Setup** — incomes, housing, expenses\n\n"
        "📊 **Income & Tax** — monthly net income forecast\n\n"
        "🏠 **Buy vs Rent** — wealth accumulation comparison\n\n"
        "🏦 **Mortgage** — annuity vs linear analysis\n\n"
        "🔀 **Scenario A/B** — compare two scenarios\n\n"
        "📝 **Actuals** — enter real income & savings\n\n"
        "📋 **Data & Export** — raw tables & Excel download\n\n"
        "🏖️ **Retirement** — pension gap, FIRE number & capital planning"
    )
    st.divider()
    st.markdown("### 💾 Your data")
    st.caption(
        "Settings and actuals are stored **only in your browser session**. "
        "Use the **⬇️ Download** buttons in the ⚙️ Setup and 📝 Actuals tabs "
        "to save your data as CSV files, and **⬆️ Upload** to restore them next time."
    )
    st.divider()
    st.caption(
        "⚠️ Approximations of Dutch tax law 2026–2030. "
        "Always consult a *belastingadviseur*."
    )

_narrow = st.session_state.get("narrow_mode", False)
_inject_mobile_css(_narrow)

# Helper: return column widths that collapse to 1 col on narrow ──────────────────
def _cols(weights: list, narrow_override: bool = False):
    """Return st.columns with given weights, or a single column in narrow mode."""
    if _narrow or narrow_override:
        return st.columns(1) * len(weights)  # repeat single col reference
    return st.columns(weights)

def _cols2(narrow_override: bool = False):
    if _narrow or narrow_override:
        return st.columns(1) * 2
    return st.columns(2)

# ════════════════════════════════════════════════════════════════════════════════
# TABS
# ════════════════════════════════════════════════════════════════════════════════

saved_A, saved_B = load_settings()

tabs = st.tabs(["⚙️ Setup", "📊 Income & Tax", "🏠 Buy vs Rent",
                "🏦 Mortgage", "🔀 Scenario A/B",
                "📝 Actuals", "📋 Data & Export", "🏖️ Retirement"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 — SETUP
# ════════════════════════════════════════════════════════════════════════════════

with tabs[0]:
    st.subheader("⚙️ Scenario Setup")
    if IS_PAID:
        ab_mode = st.toggle("🔀 Enable Scenario B — compare two scenarios side-by-side",
                            value=bool(saved_A.get("ab_mode", False)), key="ab_mode_toggle")
    else:
        ab_mode = False
        _paid_gate("Scenario A/B Comparison", icon="🔀", compact=True)

    # ── Live Quick Summary (reads from session_state — updates on every widget change) ──
    def _live_summary(lbl, sv_):
        """Compute a full snapshot dict from live session_state values."""
        ss = st.session_state
        # Income
        _use_net   = ss.get(f"use_net_input_{lbl}",   sv_.get("use_net_input",  False))
        _ruling_s  = ss.get(f"ruling_s_{lbl}",         sv_.get("ruling_s",       True))
        _ruling_p  = ss.get(f"ruling_p_{lbl}",         sv_.get("ruling_p",       False))
        _rs_s      = ss.get(f"rs_s_start_{lbl}",       sv_.get("rs_s_start",     2023))
        _re_s      = _rs_s + 5
        _rs_p      = ss.get(f"rs_p_start_{lbl}",       sv_.get("rs_p_start",     2023))
        _re_p      = _rs_p + 5
        _partner   = ss.get(f"pt_{lbl}",               sv_.get("partner",        False))
        _use_net_p = ss.get(f"use_net_input_p_{lbl}",  sv_.get("use_net_input_p",False))
        _a30_s     = _ruling_s and _rs_s <= 2026 < _re_s
        _a30_p     = _ruling_p and _rs_p <= 2026 < _re_p

        if _use_net:
            _nm  = ss.get(f"net_mo_input_{lbl}", sv_.get("net_mo_input", 3500))
            _lo, _hi = 1000.0, 500000.0
            for _ in range(40):
                _m = (_lo + _hi) / 2
                if net_annual_calc(_m, 2026, _a30_s) < _nm * 12:
                    _lo = _m
                else:
                    _hi = _m
            _inc_s = round(_lo)
            _net_s = net_monthly_calc(_inc_s, 2026, _a30_s)
        else:
            _inc_s = ss.get(f"inc_s_{lbl}", sv_.get("inc_s", 72000))
            _net_s = net_monthly_calc(_inc_s, 2026, _a30_s)

        if _partner:
            if _use_net_p:
                _nm_p = ss.get(f"net_mo_input_p_{lbl}", sv_.get("net_mo_input_p", 3500))
                _lo_p, _hi_p = 1000.0, 500000.0
                for _ in range(40):
                    _mp2 = (_lo_p + _hi_p) / 2
                    if net_annual_calc(_mp2, 2026, _a30_p) < _nm_p * 12:
                        _lo_p = _mp2
                    else:
                        _hi_p = _mp2
                _inc_p = round(_lo_p)
                _net_p = net_monthly_calc(_inc_p, 2026, _a30_p)
            else:
                _inc_p = ss.get(f"inc_p_{lbl}", sv_.get("inc_p", 92000))
                _net_p = net_monthly_calc(_inc_p, 2026, _a30_p)
        else:
            _net_p = 0

        # Housing
        _owns = ss.get(f"already_owns_{lbl}", sv_.get("already_owns", False))
        _chv  = ss.get(f"chv_{lbl}",  sv_.get("current_home_value", 400000))
        _hp   = ss.get(f"hp_{lbl}",  sv_.get("house_price", 400000))
        _dp   = ss.get(f"dp_{lbl}",  int(sv_.get("dp", 0.0) * 100)) / 100
        _mr   = ss.get(f"mr_{lbl}",  sv_.get("mort_rate", 0.040) * 100) / 100
        _rent = ss.get(f"rent_{lbl}",sv_.get("rent", 1500))
        _mp   = mort_payment(_hp, _dp, _mr)
        try:
            _mri = amortisation_schedule(_hp, _dp, _mr)["MRI_Benefit"].iloc[0]
        except Exception:
            _mri = 0
        _loan = _hp * (1 - _dp)

        # Expenses
        _fixed = sum(ss.get(f"{k}_{lbl}", sv_.get(k, d)) for k, d in [
            ("hi",150),("cf",80),("ci",80),("gr",350),("ot",250),
            ("utilities",150),("phone",40),("subscriptions",40),("gym",30),("dog",0)])

        # Projection
        _sav  = ss.get(f"sv_{lbl}",  sv_.get("savings", 50000))
        _ny   = ss.get(f"ny_{lbl}",  sv_.get("n_years", 10))
        _ha   = ss.get(f"ha_{lbl}",  sv_.get("ha", 0.03) * 100) / 100
        _ir   = ss.get(f"ir_{lbl}",  sv_.get("ir", 0.05) * 100)
        _dp_amt = _hp * _dp
        _buy_cost = _hp * 0.02 + 3500

        # Derived
        _total_net   = _net_s + _net_p
        _surplus     = _total_net - _fixed - _rent
        _surplus_buy = _total_net - _fixed - (_mp - _mri)
        _ruling_on   = _a30_s or _a30_p
        _ruling_exp  = min(x for x in [_re_s if _ruling_s else 9999,
                                        _re_p if _ruling_p else 9999] if x < 9999) if _ruling_on else None

        # 30% ruling benefit
        _net_s_off = net_monthly_calc(_inc_s if not _use_net else ss.get(f"net_mo_input_{lbl}", 3500)*12/1, 2026, False)
        _ruling_ben = (_net_s - net_monthly_calc(_inc_s, 2026, False)) if _a30_s else 0

        return dict(
            net_s=_net_s, net_p=_net_p, total_net=_total_net,
            inc_s=_inc_s, partner=_partner,
            fixed=_fixed, rent=_rent, mp=_mp, mri=_mri, loan=_loan,
            hp=_hp, dp=_dp, dp_amt=_dp_amt, buy_cost=_buy_cost, mr=_mr,
            surplus_rent=_surplus, surplus_buy=_surplus_buy,
            savings=_sav, ny=_ny, ha=_ha, ir=_ir,
            ruling_on=_ruling_on, ruling_exp=_ruling_exp, ruling_ben=_ruling_ben,
            a30_s=_a30_s, a30_p=_a30_p,
            already_owns=_owns, current_home_value=_chv,
        )

    st.divider()
    _sum_labels = ["A", "B"] if ab_mode else ["A"]
    _sum_svs    = [saved_A, saved_B] if ab_mode else [saved_A]
    _sum_cols   = st.columns(2) if ab_mode else st.columns(1)

    for _si, (_slbl, _ssv) in enumerate(zip(_sum_labels, _sum_svs)):
        _d = _live_summary(_slbl, _ssv)
        _color  = "#2ecc71" if _slbl == "A" else "#3498db"
        _sname  = st.session_state.get(f"scen_label_{_slbl}", _ssv.get("scenario_label","")) or "Current Situation"
        with _sum_cols[_si]:
            st.markdown(
                f"<div style='font-weight:700;font-size:15px;color:{_color};"
                f"margin-bottom:6px;border-bottom:2px solid {_color};padding-bottom:4px'>"
                f"📌 {_sname}</div>",
                unsafe_allow_html=True
            )
            # ── 5 core metrics ────────────────────────────────────────────
            _owns = _d["already_owns"]
            _housing_cost = (_d["mp"] - _d["mri"]) if _owns else _d["rent"]
            _housing_label = "Mortgage (net)" if _owns else "Monthly Rental"
            _housing_help  = (f"Net mortgage after MRI benefit on €{_d['loan']:,.0f} loan at {_d['mr']*100:.2f}%.")\
                             if _owns else "Monthly rent as configured in Setup."
            _total_exp = _d["fixed"] + _housing_cost
            _fcf       = _d["total_net"] - _total_exp

            _mc1, _mc2, _mc3, _mc4, _mc5 = st.columns(5)
            _mc1.metric("Total Income",
                f"€{_d['total_net']:,.0f}",
                help="Combined household net income after Box 1, ZVW, AHK and arbeidskorting.")
            _mc2.metric("Total Expenses",
                f"€{_total_exp:,.0f}",
                help=f"Fixed expenses €{_d['fixed']:,.0f} + {_housing_label.lower()} €{_housing_cost:,.0f}.")
            _mc3.metric(_housing_label,
                f"€{_housing_cost:,.0f}",
                help=_housing_help)
            _mc4.metric("30% Ruling Expiring",
                f"Jan {_d['ruling_exp']}" if _d["ruling_on"] else "—",
                help=(
                    f"Ruling expires Jan {_d['ruling_exp']} — monthly net drops €{_d['ruling_ben']:,.0f} at expiry."
                    if _d["ruling_on"] else "No 30% ruling active."
                ))
            _fcf_color = "normal" if _fcf >= 0 else "inverse"
            _mc5.metric("Free Cash Flow",
                f"€{_fcf:,.0f}",
                delta="surplus ✅" if _fcf >= 0 else "deficit ⚠️",
                delta_color=_fcf_color,
                help=f"Income €{_d['total_net']:,.0f} minus total expenses €{_total_exp:,.0f}. "
                     f"Positive = money left to save or invest each month.")

            # ── Context card: owns vs renting ─────────────────────────────
            if _owns:
                _chv = _d["current_home_value"]
                st.caption(
                    f"🏠 **Homeowner** — current estimated value **€{_chv:,}** · "
                    f"mortgage net/mo **€{_d['mp']-_d['mri']:,.0f}** (gross €{_d['mp']:,.0f} − MRI €{_d['mri']:,.0f}) · "
                    f"Appreciation at {_d['ha']*100:.1f}%/yr over {_d['ny']} yr → "
                    f"estimated value **€{_chv * (1 + _d['ha']) ** _d['ny']:,.0f}**"
                )
            else:
                st.caption(
                    f"🏘️ **Renting** — €{_d['rent']:,.0f}/mo · "
                    f"Buying at €{_d['hp']:,} requires €{_d['dp_amt']+_d['buy_cost']:,.0f} upfront · "
                    f"mortgage net **€{_d['mp']-_d['mri']:,.0f}/mo** after MRI · "
                    f"projection: {_d['ny']} yr at {_d['ha']*100:.1f}%/yr appreciation"
                )

    st.divider()

    with st.expander("ℹ️ How do these inputs flow through the dashboard?", expanded=False):
        st.markdown("""
Configure all inputs for your financial scenarios here. Every value you set flows through to **all other tabs**:

- **Income & Tax tab** uses your gross salaries, 30% ruling dates, and partner status to compute net take-home pay, ZVW, and tax credits
- **Buy vs Rent tab** uses house price, down payment, mortgage rate, buy date, rent, expenses, savings, appreciation and investment return to project wealth
- **Mortgage tab** uses house price, down payment and mortgage rate to compare annuity vs linear repayment and the monthly tax benefit (hypotheekrenteaftrek)
- **Scenario A/B tab** compares both scenarios side-by-side — configure Scenario B here when A/B mode is enabled
- **Data & Export tab** shows the raw monthly numbers and lets you download as Excel

💡 Click **Save Settings** at the bottom to persist all inputs — they reload automatically next run.
        """)

    # ── How many columns to show ─────────────────────────────────────────────
    scen_cols = st.columns(2) if ab_mode else [st.container()]
    labels    = ["A", "B"] if ab_mode else ["A"]

    params = {}

    for idx, lbl in enumerate(labels):
        col = scen_cols[idx]

        with col:
            color = "#2ecc71" if lbl == "A" else "#3498db"
            _saved_slabel = (saved_A if lbl=="A" else saved_B).get("scenario_label", "")
            if IS_PAID:
                scenario_label = st.text_input(
                    "Scenario name", value=_saved_slabel if _saved_slabel else "Current Situation",
                    key=f"scen_label_{lbl}",
                    placeholder="e.g. 'Buy 2026' or 'Current Situation'",
                    help="Name for this scenario — shown as the tab heading and on all charts."
                )
            else:
                scenario_label = _saved_slabel if _saved_slabel else "Current Situation"
            _scen_display = scenario_label if scenario_label.strip() else ("Scenario B" if lbl=="B" else "Current Situation")
            st.markdown(
                f"<h3 style='color:{color};margin-bottom:4px;margin-top:0'>{_scen_display}</h3>",
                unsafe_allow_html=True
            )


            sv = saved_A if lbl == "A" else saved_B

            # ── Live collapsed-label summaries (read from session_state widget keys) ────
            # Session state is populated the moment a widget renders, so these values
            # update immediately when the user changes any input — no save required.
            ss = st.session_state   # shorthand

            # Income: prefer net-input toggle → use stored net directly; else calc from gross
            _live_use_net   = ss.get(f"use_net_input_{lbl}", sv.get("use_net_input", False))
            _live_ruling_s  = ss.get(f"ruling_s_{lbl}",     sv.get("ruling_s", True))
            _live_ruling_p  = ss.get(f"ruling_p_{lbl}",     sv.get("ruling_p", False))
            _live_rs_s      = ss.get(f"rs_s_start_{lbl}",   sv.get("rs_s_start", 2023))
            _live_re_s      = _live_rs_s + 5
            _live_rs_p      = ss.get(f"rs_p_start_{lbl}",   sv.get("rs_p_start", 2023))
            _live_re_p      = _live_rs_p + 5
            _live_partner   = ss.get(f"pt_{lbl}",           sv.get("partner", False))
            _live_use_net_p = ss.get(f"use_net_input_p_{lbl}", sv.get("use_net_input_p", False))

            if _live_use_net:
                # Net mode: reverse-calc gross to get correct net
                _lv_net_mo   = ss.get(f"net_mo_input_{lbl}", sv.get("net_mo_input", 3500))
                _lv_a30_s    = _live_ruling_s and _live_rs_s <= 2026 < _live_re_s
                _lv_lo, _lv_hi = 1000.0, 500000.0
                for _ in range(50):
                    _lv_mid = (_lv_lo + _lv_hi) / 2
                    if net_annual_calc(_lv_mid, 2026, _lv_a30_s) < _lv_net_mo * 12:
                        _lv_lo = _lv_mid
                    else:
                        _lv_hi = _lv_mid
                _lv_inc_s = round(_lv_lo)
                _lv_net_s = net_monthly_calc(_lv_inc_s, 2026, _lv_a30_s)
            else:
                _lv_inc_s  = ss.get(f"inc_s_{lbl}",  sv.get("inc_s", 72000))
                _lv_a30_s  = _live_ruling_s and _live_rs_s <= 2026 < _live_re_s
                _lv_net_s  = net_monthly_calc(_lv_inc_s, 2026, _lv_a30_s)

            if _live_partner:
                if _live_use_net_p:
                    _lv_net_mo_p  = ss.get(f"net_mo_input_p_{lbl}", sv.get("net_mo_input_p", 3500))
                    _lv_a30_p     = _live_ruling_p and _live_rs_p <= 2026 < _live_re_p
                    _lv_lo_p, _lv_hi_p = 1000.0, 500000.0
                    for _ in range(50):
                        _lv_mid_p = (_lv_lo_p + _lv_hi_p) / 2
                        if net_annual_calc(_lv_mid_p, 2026, _lv_a30_p) < _lv_net_mo_p * 12:
                            _lv_lo_p = _lv_mid_p
                        else:
                            _lv_hi_p = _lv_mid_p
                    _lv_inc_p = round(_lv_lo_p)
                    _lv_net_p = net_monthly_calc(_lv_inc_p, 2026, _lv_a30_p)
                else:
                    _lv_inc_p = ss.get(f"inc_p_{lbl}", sv.get("inc_p", 92000))
                    _lv_a30_p = _live_ruling_p and _live_rs_p <= 2026 < _live_re_p
                    _lv_net_p = net_monthly_calc(_lv_inc_p, 2026, _lv_a30_p)
            else:
                _lv_net_p = 0

            _lv_hp   = ss.get(f"hp_{lbl}",  sv.get("house_price", 550000))
            _lv_dp   = ss.get(f"dp_{lbl}",  int(sv.get("dp",0.10)*100)) / 100
            _lv_mr   = ss.get(f"mr_{lbl}",  sv.get("mort_rate",0.045)*100) / 100
            _lv_mort = mort_payment(_lv_hp, _lv_dp, _lv_mr)
            try:
                _lv_mri = amortisation_schedule(_lv_hp, _lv_dp, _lv_mr)["MRI_Benefit"].iloc[0]
            except Exception:
                _lv_mri = 0

            _lv_hi   = ss.get(f"hi_{lbl}",  sv.get("hi",  150))
            _lv_cf   = ss.get(f"cf_{lbl}",  sv.get("cf",   80))
            _lv_ci   = ss.get(f"ci_{lbl}",  sv.get("ci",   80))
            _lv_gr   = ss.get(f"gr_{lbl}",  sv.get("gr",  350))
            _lv_ot   = ss.get(f"ot_{lbl}",  sv.get("ot",  250))
            _lv_ut   = ss.get(f"utilities_{lbl}", sv.get("utilities", 150))
            _lv_ph   = ss.get(f"phone_{lbl}",     sv.get("phone",      40))
            _lv_sub  = ss.get(f"subscriptions_{lbl}", sv.get("subscriptions", 40))
            _lv_gym  = ss.get(f"gym_{lbl}",  sv.get("gym",  30))
            _lv_dog  = ss.get(f"dog_{lbl}",  sv.get("dog",   0))
            _lv_fixed = _lv_hi+_lv_cf+_lv_ci+_lv_gr+_lv_ot+_lv_ut+_lv_ph+_lv_sub+_lv_gym+_lv_dog

            _lv_ny   = ss.get(f"ny_{lbl}",  sv.get("n_years", 10))
            _lv_ha   = ss.get(f"ha_{lbl}",  sv.get("ha", 0.03)*100) / 100
            _lv_ir   = ss.get(f"ir_{lbl}",  sv.get("ir", 0.05)*100)
            _lv_fe   = ss.get(f"future_exp_list_{lbl}", sv.get("future_expenses", []))
            _lv_fe_total = sum(fe.get("amount",0) for fe in _lv_fe)
            _lv_hs   = ss.get(f"hs_yr_{lbl}",  sv.get("hist_start","2026-01")[:4] if sv.get("hist_start") else "2026")
            _lv_hs_mo = ss.get(f"hs_mo_{lbl}", "Jan")
            _lv_hist_start = f"{_lv_hs}-{str(_lv_hs_mo).zfill(2) if str(_lv_hs_mo).isdigit() else _lv_hs_mo}"

            _lbl_income   = f"👤 People & Income — €{_lv_net_s + _lv_net_p:,.0f}/mo net"
            _lbl_housing  = (f"🏠 Housing & Mortgage — €{_lv_hp:,} · "
                             f"€{_lv_mort:,.0f}/mo gross · "
                             f"€{_lv_mri:,.0f}/mo MRI · "
                             f"{_lv_mr*100:.1f}% rate")
            _lbl_expenses = f"🧾 Monthly Expenses — €{_lv_fixed:,.0f}/mo total"
            _lbl_proj     = f"📈 Projection — {_lv_ny}yr · {_lv_ha*100:.1f}% apprec. · {_lv_ir:.1f}% return"
            _lbl_future   = f"🍼 Future Expenses — {len(_lv_fe)} item(s), €{_lv_fe_total:,.0f}/mo at start"
            _lbl_hist     = f"📅 Historic Data Range — {sv.get('hist_start','2026-01')} → {sv.get('hist_end','2026-03')}"

            # ════════════════════════════════════════════════════════════════
            # 1 — PEOPLE & INCOME
            # ════════════════════════════════════════════════════════════════
            with st.expander("👤 People & Income", expanded=False):
                st.caption(_lbl_income.replace("👤 People & Income — ", "📊 "))
                # ── Income entry mode toggle ──────────────────────────────────
                _use_net_input = st.toggle(
                    "Enter monthly net income (what arrives in your bank)",
                    value=sv.get("use_net_input", True),
                    key=f"use_net_input_{lbl}",
                    help=(
                        "Tick this if you prefer to enter the monthly net amount you actually "
                        "receive in your bank account rather than your annual gross salary.\n\n"
                        "The dashboard will reverse-calculate your gross salary from the net "
                        "amount using the Dutch tax rules (Box 1, ZVW, AHK, AK) — so all "
                        "projections remain tax-accurate.\n\n"
                        "Note: if you have the 30% ruling active, tick that first so the "
                        "reverse-calculation uses the correct taxable base."
                    )
                )

                c1, c2 = st.columns(2)
                if _use_net_input:
                    _net_mo_input = c1.number_input("Your monthly net income (€/mo)",
                        value=int(sv.get("net_mo_input", 3500)), step=50,
                        min_value=500, max_value=30000,
                        key=f"net_mo_input_{lbl}",
                        help="The amount deposited in your bank account each month after all taxes. "
                             "The dashboard works backwards to find your gross salary.")
                    inc_s_raw = sv.get("inc_s", 72000)   # placeholder; replaced after ruling
                else:
                    inc_s_raw = c1.number_input("Your gross income (€/yr)",
                        value=sv.get("inc_s", 72000), step=1000, key=f"inc_s_{lbl}",
                        help="Your annual gross salary before tax. Used to calculate Box 1 tax, ZVW, and all tax credits.")
                    _net_mo_input = 0   # unused when entering gross
                sal_growth = c2.slider("Annual salary growth (%)",
                    0.0, 10.0, sv.get("sal_growth", 0.0) * 100, 0.5, key=f"sg_{lbl}",
                    help="Compound annual salary growth from 2026. 2–3% tracks Dutch inflation and CAO agreements.") / 100

                # ── Vakantiegeld (holiday allowance) — hidden when using net input
                if not _use_net_input:
                    inc_s_incl_vg = st.checkbox(
                        "Income includes vakantiegeld (8% holiday allowance)",
                        value=sv.get("inc_s_incl_vg", False),
                        key=f"inc_s_incl_vg_{lbl}",
                        help=(
                            "In the Netherlands, most employees receive 8% vakantiegeld (holiday allowance) "
                            "on top of their base salary, typically paid in May.\n\n"
                            "**If ticked:** your input already includes the 8% — the dashboard divides by 1.08 "
                            "to derive the base salary used for monthly income calculations.\n\n"
                            "**If unticked:** your input is the base salary."
                        )
                    )
                    if inc_s_incl_vg:
                        inc_s = inc_s_raw / 1.08
                        _vg_amount = inc_s_raw - inc_s
                        st.caption(
                            f"Base salary (ex vakantiegeld): **€{inc_s:,.0f}/yr** · "
                            f"Vakantiegeld (May bonus): **€{_vg_amount:,.0f}** · "
                            f"Monthly base: **€{inc_s/12:,.0f}**"
                        )
                    else:
                        inc_s = inc_s_raw
                else:
                    inc_s_incl_vg = False   # net input already accounts for taxes
                    inc_s = inc_s_raw

                # ── Your 30% ruling ──────────────────────────────────────────
                st.markdown("**30% Ruling — You**")
                _RULING_HELP = """
**30% ruling / expat scheme** — lets eligible foreign employees receive part of their salary tax-free.
The rate and duration depend on **when your ruling first started**:

| First applied | Tax-free % | Duration | Notes |
|---|---|---|---|
| ≤ 2023 | **30%** full term | 5 years | Fully grandfathered — no change |
| 2024 – 2026 | **30%** until end 2026, then **27%** | 5 years | Rate drops Jan 2027 |
| 2027+ | **27%** flat | 5 years | Higher salary threshold (€50,436) |

The ruling reduces your **Box 1 taxable income** and **ZVW** base. Only 70% (or 73% from 2027) of gross is taxable.
Salary cap (Balkenende-norm): max €246,000 taxable salary qualifies (2025 figure, indexed annually).
The dashboard automatically applies the correct rate for each year based on your start year.
"""
                ruling_s = st.checkbox("Do you have the 30% ruling?",
                    value=sv.get("ruling_s", True), key=f"ruling_s_{lbl}",
                    help=_RULING_HELP)
                rs_s  = sv.get("rs_s",       sv.get("rs", 2026))
                re_s  = sv.get("re_s",       sv.get("re", 2029))
                rs_s_start = sv.get("rs_s_start", rs_s)   # first year ruling was applied
                rs, re = rs_s, re_s   # legacy aliases
                if ruling_s:
                    _ry1, _ry2 = st.columns(2)
                    _start_opts = list(range(2020, 2030))
                    rs_s_start = _ry1.selectbox("First year ruling applied — You",
                        _start_opts,
                        index=_start_opts.index(rs_s_start) if rs_s_start in _start_opts else 4,
                        key=f"rs_s_start_{lbl}",
                        help="The calendar year your 30% ruling was first applied in payroll. This determines whether you get 30% or 27% in later years.")
                    rs_s = rs_s_start          # ruling starts in the first year applied
                    re_s = rs_s_start + 5      # always exactly 5 years duration
                    # Derive rate schedule for display
                    _rates_s_ui = ruling_rate(rs_s_start)
                    _rate_label_s = "30% → 27% from 2027" if rs_s_start in (2024, 2025, 2026) else ("27% flat" if rs_s_start >= 2027 else "30% (grandfathered)")
                    _ry2.markdown(
                        f"**Ruling period:** {rs_s} – {re_s-1}\n\n"
                        f"**Rate schedule:** {_rate_label_s}\n\n"
                        f"**Expires:** Jan {re_s}",
                        help="Auto-computed from your start year. Duration is always 5 years per Dutch law.")
                    rs, re = rs_s, re_s

                # ── Reverse-calculate gross from net now that ruling state is known ──
                if _use_net_input:
                    _a30_for_rev = ruling_s and rs_s <= 2026 < re_s
                    _target_net_annual = _net_mo_input * 12
                    _lo, _hi = 1000.0, 500000.0
                    for _ in range(50):
                        _mid = (_lo + _hi) / 2
                        if net_annual_calc(_mid, 2026, _a30_for_rev) < _target_net_annual:
                            _lo = _mid
                        else:
                            _hi = _mid
                    inc_s_raw = round(_lo)
                    _implied_net = net_annual_calc(inc_s_raw, 2026, _a30_for_rev) / 12
                    st.caption(
                        f"Implied gross: **€{inc_s_raw:,.0f}/yr** · "
                        f"Net check: **€{_implied_net:,.0f}/mo** (target: €{_net_mo_input:,.0f}/mo) · "
                        f"30% ruling: **{"on ✓" if _a30_for_rev else "off"}** · "
                        f"{"With ruling: lower gross needed to reach same net." if _a30_for_rev else "Without ruling: higher gross needed to reach same net."}"
                    )

                partner = st.checkbox("Include partner income",
                    value=sv.get("partner", True), key=f"pt_{lbl}")
                inc_p = 0
                sal_growth_p = 0.0   # default when no partner
                ruling_p, rs_p, re_p, rs_p_start = False, sv.get("rs_p", 2026), sv.get("re_p", 2029), sv.get("rs_p_start", 2026)
                _use_net_input_p = False   # default; overridden below when partner=True
                if partner:
                    # ── Partner income entry mode ─────────────────────────────
                    _use_net_input_p = st.toggle(
                        "Enter partner's monthly net income (what arrives in their bank)",
                        value=sv.get("use_net_input_p", True),
                        key=f"use_net_input_p_{lbl}",
                        help=(
                            "Tick this to enter your partner's monthly net take-home pay instead of "
                            "their annual gross salary. The dashboard reverse-calculates the gross "
                            "using Dutch tax rules so projections remain tax-accurate."
                        )
                    )
                    _pi1, _pi2 = st.columns(2)
                    if _use_net_input_p:
                        _net_mo_input_p = _pi1.number_input("Partner monthly net income (€/mo)",
                            value=int(sv.get("net_mo_input_p", 3500)), step=50,
                            min_value=500, max_value=30000,
                            key=f"net_mo_input_p_{lbl}",
                            help="Monthly amount deposited in your partner's bank account after all taxes.")
                        inc_p = sv.get("inc_p", 92000)   # placeholder; replaced after ruling
                    else:
                        _net_mo_input_p = 0   # unused
                        inc_p = _pi1.number_input("Partner gross income (€/yr)",
                            value=sv.get("inc_p", 92000), step=1000, key=f"inc_p_{lbl}",
                            help="Partner's annual gross salary. Taxed independently — each person has their own brackets and credits.")
                    sal_growth_p = _pi2.slider("Partner salary growth (%)",
                        0.0, 10.0, sv.get("sal_growth_p", 0.0) * 100, 0.5, key=f"sg_p_{lbl}",
                        help="Compound annual salary growth for your partner from 2026. Can differ from yours if on a different career trajectory or CAO.") / 100

                    # ── Partner 30% ruling ───────────────────────────────────
                    st.markdown("**30% Ruling — Partner**")
                    ruling_p = st.checkbox("Does your partner have the 30% ruling?",
                        value=sv.get("ruling_p", False), key=f"ruling_p_{lbl}",
                        help=_RULING_HELP)
                    rs_p_start = sv.get("rs_p_start", sv.get("rs_p", 2026))
                    if ruling_p:
                        _rp1, _rp2 = st.columns(2)
                        _start_opts_p = list(range(2020, 2030))
                        rs_p_start = _rp1.selectbox("First year ruling applied — Partner",
                            _start_opts_p,
                            index=_start_opts_p.index(rs_p_start) if rs_p_start in _start_opts_p else 4,
                            key=f"rs_p_start_{lbl}",
                            help="The year the partner's 30% ruling was first applied in payroll.")
                        rs_p = rs_p_start
                        re_p = rs_p_start + 5
                        _rates_p_ui = ruling_rate(rs_p_start)
                        _rate_label_p = "30% → 27% from 2027" if rs_p_start in (2024, 2025, 2026) else ("27% flat" if rs_p_start >= 2027 else "30% (grandfathered)")
                        _rp2.markdown(
                            f"**Ruling period:** {rs_p} – {re_p-1}\n\n"
                            f"**Rate schedule:** {_rate_label_p}\n\n"
                            f"**Expires:** Jan {re_p}",
                            help="Auto-computed from partner's start year.")
                    else:
                        rs_p_start = sv.get("rs_p_start", 2026)

                    # ── Reverse-calculate partner gross now that ruling state is known ──
                    if _use_net_input_p:
                        _a30_for_rev_p = ruling_p and rs_p <= 2026 < re_p
                        _target_net_p  = _net_mo_input_p * 12
                        _lo_p, _hi_p   = 1000.0, 500000.0
                        for _ in range(50):
                            _mid_p = (_lo_p + _hi_p) / 2
                            if net_annual_calc(_mid_p, 2026, _a30_for_rev_p) < _target_net_p:
                                _lo_p = _mid_p
                            else:
                                _hi_p = _mid_p
                        inc_p = round(_lo_p)
                        _implied_net_p = net_annual_calc(inc_p, 2026, _a30_for_rev_p) / 12
                        st.caption(
                            f"Partner implied gross: **€{inc_p:,.0f}/yr** · "
                            f"Net check: **€{_implied_net_p:,.0f}/mo** "
                            f"(target: €{_net_mo_input_p:,.0f}/mo) · "
                            f"30% ruling: **{"on" if _a30_for_rev_p else "off"}**"
                        )

                # KOT defaults — inputs moved to Monthly Expenses section
                n_kdv        = sv.get("n_kdv",        0)
                n_bso        = sv.get("n_bso",        0)
                kdv_hrs      = sv.get("kdv_hrs",      None)
                bso_hrs      = sv.get("bso_hrs",      None)
                kdv_rate     = sv.get("kdv_rate",     None)
                bso_rate     = sv.get("bso_rate",     None)
                kot_start_ym = sv.get("kot_start_ym", "2027-01")
                kot_end_ym   = sv.get("kot_end_ym",   "")

            # ════════════════════════════════════════════════════════════════
            # 3 — HOUSING & MORTGAGE
            # ════════════════════════════════════════════════════════════════
            with st.expander("🏠 Housing & Mortgage", expanded=False):
                st.caption(_lbl_housing.replace("🏠 Housing & Mortgage — ", "📊 "))

                already_owns = st.checkbox(
                    "I currently own a home",
                    value=sv.get("already_owns", False),
                    key=f"already_owns_{lbl}",
                    help=(
                        "Tick if you already own and live in a property. This changes the projections: "
                        "instead of showing a future purchase, the dashboard uses your current home value "
                        "and existing mortgage. You can still model selling the property."
                    )
                )

                if already_owns:
                    st.markdown("**🏡 Your Current Property**")
                    _ow1, _ow2 = st.columns(2)
                    current_home_value = _ow1.number_input(
                        "Current estimated home value (€)",
                        value=sv.get("current_home_value", sv.get("house_price", 400000)),
                        step=5000, min_value=0, key=f"chv_{lbl}",
                        help="Your best estimate of what your home is worth today. "
                             "Used for equity calculations, sell proceeds and appreciation projections. "
                             "Check Funda or a recent WOZ-beschikking for a reference value."
                    )
                    house_price = _ow2.number_input(
                        "Original purchase price (€)",
                        value=sv.get("house_price", 400000), step=5000, key=f"hp_{lbl}",
                        help="The price you originally paid. Used to calculate appreciation and buying costs already incurred."
                    )
                    rent = 0   # no rent when owning
                else:
                    current_home_value = sv.get("current_home_value", sv.get("house_price", 400000))
                    rent = st.number_input("Current rent (€/mo)",
                        value=sv.get("rent", 1500), step=50, min_value=0, key=f"rent_{lbl}",
                        help="Monthly rent before buying, and the ongoing cost in the Rent scenario throughout. Include service costs.")

                if not already_owns:
                    st.markdown("**📆 Purchase date**")
                h1, h2 = st.columns(2)
                by_options = [2026, 2027, 2028]
                by = h1.selectbox("Purchase year", by_options,
                    index=by_options.index(sv.get("by", 2026)), key=f"by_{lbl}",
                    help="Year you plan to buy. Down payment and buying costs are deducted from savings in this month.")
                bm_options = list(range(1, 13))
                bm = h2.selectbox("Purchase month", bm_options,
                    index=bm_options.index(sv.get("bm", 7)), key=f"bm_{lbl}",
                    help="Month of purchase. Mortgage starts from this month.")

                if not already_owns:
                    st.markdown("**🏡 Target Property**")
                    house_price = st.number_input("Target house price (€)",
                        value=sv.get("house_price", 400000), step=5000, key=f"hp_{lbl}",
                        help="The price of the house you plan to buy. Buying costs (2% overdrachtsbelasting + ~€3,500 notaris) are added automatically.")

                st.markdown("**💳 Mortgage**")
                m1, m2 = st.columns(2)
                dp = m1.slider("Down payment (%)", 0, 30, int(sv.get("dp", 0.10) * 100), key=f"dp_{lbl}",
                    help="% of house price paid upfront from savings. Dutch banks typically require 5–10%.") / 100
                mr = m2.slider("Mortgage rate (%)", 2.0, 8.0, sv.get("mort_rate", 0.045) * 100, 0.1,
                    key=f"mr_{lbl}",
                    help="Annual fixed interest rate. 10-year fixed rates in NL were ~3.5–4.5% in 2025.") / 100
                mt_options = ["Annuity (annuïteit)", "Linear (lineair)"]
                mort_type = st.radio("Mortgage type", mt_options,
                    index=mt_options.index(sv.get("mort_type", "Annuity (annuïteit)")),
                    horizontal=True, key=f"mt_{lbl}",
                    help="Annuity: fixed payment, interest-heavy early on. Linear: fixed principal, lower total cost but higher early payments.")

                st.markdown("**🏷️ Sell house** *(optional)*")
                sell_house = st.checkbox("Model a house sale",
                    value=sv.get("sell_house", False), key=f"sh_{lbl}",
                    help="Sell the house on a set date. Net proceeds (equity minus ~1.5% makelaar + €2,500) are added to investable cash.")
                sy, sm = sv.get("sy", 2031), sv.get("sm", 1)
                if sell_house:
                    sy_options = list(range(2026, 2041))
                    sm_options = list(range(1, 13))
                    sh1, sh2 = st.columns(2)
                    sy = sh1.selectbox("Sell year", sy_options,
                        index=sy_options.index(min(sy, 2040)), key=f"sy_{lbl}",
                        help="Year of sale. Appreciation is applied up to this month, then equity is realised.")
                    sm = sh2.selectbox("Sell month", sm_options,
                        index=sm_options.index(sm), key=f"sm_{lbl}",
                        help="Month of sale. Selling costs (~1.5% of value + €2,500) are deducted automatically.")

            # ════════════════════════════════════════════════════════════════
            # 4 — MONTHLY EXPENSES
            # ════════════════════════════════════════════════════════════════
            with st.expander("🧾 Monthly Expenses", expanded=False):
                st.caption(_lbl_expenses.replace("🧾 Monthly Expenses — ", "📊 "))
                eg    = sv.get("exp_growth", {})
                en    = sv.get("exp_notes",  {})   # per-category free-text notes
                def _eg_get(key, default=0.02):
                    return float(eg.get(key, default)) if isinstance(eg, dict) else default
                def _en_get(key):
                    return str(en.get(key, "")) if isinstance(en, dict) else ""

                # ── Column header + expense rows — desktop 4-col, mobile stacked ──
                _COLS = [2.6, 0.85, 0.85, 2.3]

                if not _narrow:
                    # Desktop: single aligned header row above all inputs
                    _hc = st.columns(_COLS)
                    _hc[0].markdown("**Category**")
                    _hc[1].markdown("**€ /mo**")
                    _hc[2].markdown("**% /yr**")
                    _hc[3].markdown("**Note**")

                def _exp_row(label, key, val, step, growth_default, growth_help, note_placeholder=""):
                    """Render one expense row. Desktop: 4-col aligned. Mobile: labelled block."""
                    if _narrow:
                        # Mobile: category name as section label, then 3 inputs in a row
                        st.markdown(
                            f"<div style='font-size:13px;font-weight:600;color:#ccc;"
                            f"margin-top:10px;margin-bottom:2px;border-bottom:1px solid #333;"
                            f"padding-bottom:3px'>{label}</div>",
                            unsafe_allow_html=True
                        )
                        mc1, mc2, mc3 = st.columns([1.2, 1, 1.8])
                        mc1.markdown("<div style='font-size:11px;color:#888;margin-bottom:2px'>€ /mo</div>", unsafe_allow_html=True)
                        amount = mc1.number_input("€", value=float(val), step=float(step),
                            min_value=0.0, key=f"{key}_{lbl}", label_visibility="collapsed")
                        mc2.markdown("<div style='font-size:11px;color:#888;margin-bottom:2px'>% /yr</div>", unsafe_allow_html=True)
                        growth = mc2.number_input("%", value=round(_eg_get(key, growth_default)*100, 1),
                            step=0.5, key=f"{key}_g_{lbl}",
                            help=growth_help, label_visibility="collapsed") / 100
                        mc3.markdown("<div style='font-size:11px;color:#888;margin-bottom:2px'>Note</div>", unsafe_allow_html=True)
                        note = mc3.text_input("n", value=_en_get(key),
                            key=f"{key}_note_{lbl}", placeholder=note_placeholder,
                            label_visibility="collapsed")
                    else:
                        # Desktop: 4-column row aligned under the headers
                        rc = st.columns(_COLS)
                        rc[0].markdown(f"<div style='padding-top:8px'>{label}</div>", unsafe_allow_html=True)
                        amount = rc[1].number_input("€", value=float(val), step=float(step),
                            min_value=0.0, key=f"{key}_{lbl}", label_visibility="collapsed")
                        growth = rc[2].number_input("%", value=round(_eg_get(key, growth_default)*100, 1),
                            step=0.5, key=f"{key}_g_{lbl}",
                            help=growth_help, label_visibility="collapsed") / 100
                        note = rc[3].text_input("n", value=_en_get(key),
                            key=f"{key}_note_{lbl}", placeholder=note_placeholder,
                            label_visibility="collapsed")
                    return amount, growth, note

                st.markdown("*💊 Health & Wellbeing*")
                hi,    hi_g,    hi_note    = _exp_row("Health insurance", "hi",    sv.get("hi",420),    10,  0.045,
                    "💡 Dutch health premiums rise ~4–6%/yr. 4.5% is a solid base.", "e.g. CZ / Zilveren Kruis")
                gym,   gym_g,   gym_note   = _exp_row("Gym",              "gym",   sv.get("gym",40),      5,  0.025,
                    "💡 Gym prices ~2–3%/yr with general inflation.", "e.g. Basic-Fit, contract ends…")

                st.markdown("*🚗 Transport*")
                cf,    cf_g,    cf_note    = _exp_row("Car fuel",         "cf",    sv.get("cf",100),    10,  0.020,
                    "💡 Fuel ~2%/yr long-run. Use 0% if switching to EV.", "e.g. lease / own car")
                ci,    ci_g,    ci_note    = _exp_row("Car insurance",    "ci",    sv.get("ci",100),    10,  0.030,
                    "💡 NL car insurance +3–5%/yr due to repair inflation.", "e.g. Centraal Beheer all-risk")

                st.markdown("*🛒 Household*")
                gr,    gr_g,    gr_note    = _exp_row("Groceries",        "gr",    sv.get("gr",400),    25,  0.030,
                    "💡 Dutch food CPI ~3–5%/yr; 3% is a medium-term estimate.", "e.g. Albert Heijn / Jumbo")
                utilities, ut_g, ut_note   = _exp_row("Utilities",        "utilities", sv.get("utilities",200), 10, 0.030,
                    "💡 Energy transition costs push ~3–5%/yr. 3% is cautious.", "e.g. Vattenfall, smart meter")
                dog,   dog_g,   dog_note   = _exp_row("Dog",              "dog",   sv.get("dog",150),   10,  0.030,
                    "💡 Vet +4–6%/yr; food tracks grocery inflation. 3–4% blended.", "e.g. food + Agila insurance")

                st.markdown("*📱 Digital & Subscriptions*")
                phone, phone_g, phone_note = _exp_row("Phone",            "phone", sv.get("phone",50),   5,  0.010,
                    "💡 NL telecom stable. 1% conservative; 0% on fixed contract.", "e.g. KPN, contract ends…")
                subscriptions, sub_g, sub_note = _exp_row("Subscriptions","subscriptions", sv.get("subscriptions",50), 5, 0.050,
                    "💡 Netflix/Spotify raising fast. 5% blended is realistic.", "e.g. Netflix, Spotify, Adobe")

                st.markdown("*📦 Other*")
                ot,    ot_g,    ot_note    = _exp_row("Other",            "ot",    sv.get("ot",300),    25,  0.025,
                    "💡 Long-run Dutch CPI ~2–3%/yr. 2.5% is a solid middle ground.", "e.g. dining, clothing, gifts")

                exp_growth = {
                    "hi": hi_g, "cf": cf_g, "ci": ci_g, "gr": gr_g,
                    "utilities": ut_g, "phone": phone_g, "subscriptions": sub_g,
                    "gym": gym_g, "dog": dog_g, "ot": ot_g,
                }
                exp_notes = {
                    "hi": hi_note, "cf": cf_note, "ci": ci_note, "gr": gr_note,
                    "utilities": ut_note, "phone": phone_note, "subscriptions": sub_note,
                    "gym": gym_note, "dog": dog_note, "ot": ot_note,
                }

                # ── Kinderopvangtoeslag (Childcare) ───────────────────────
                _WEEKS_PM = 4.33
                _KOT_HELP = "Kinderopvangtoeslag is a Dutch government subsidy covering part of your childcare costs.\n\nTwo types:\n- Dagopvang (nursery) — children 0-4 yr. Drop-off at a kinderdagverblijf (KDV) while you work.\n- BSO (after-school care) — children 4-12 yr. Care before/after school and during holidays.\n\nThe subsidy % depends on household income (96% at low income, ~36% at high income), capped at government max hourly rates. Enter hours per week — the dashboard converts to monthly."
                st.markdown("*🧒 Childcare (Kinderopvangtoeslag)*")
                _kc1, _kc2 = st.columns(2)
                n_kdv = _kc1.number_input("Children in dagopvang (nursery, 0-4 yr)",
                    value=sv.get("n_kdv", 0), min_value=0, max_value=5, step=1, key=f"n_kdv_{lbl}",
                    help=_KOT_HELP)
                n_bso = _kc2.number_input("Children in BSO (after-school, 4-12 yr)",
                    value=sv.get("n_bso", 0), min_value=0, max_value=5, step=1, key=f"n_bso_{lbl}",
                    help=_KOT_HELP)
                kdv_hrs  = sv.get("kdv_hrs",  None)
                bso_hrs  = sv.get("bso_hrs",  None)
                kdv_rate = sv.get("kdv_rate", None)
                bso_rate = sv.get("bso_rate", None)
                kot_start_ym = sv.get("kot_start_ym", "2027-01")
                kot_end_ym   = sv.get("kot_end_ym",   "")
                if n_kdv > 0 or n_bso > 0:
                    if n_kdv > 0:
                        _kr1, _kr2 = st.columns(2)
                        _h_wk = _kr1.number_input("Dagopvang - hours/week",
                            value=round(float(sv.get("kdv_hrs") or 37.0) / _WEEKS_PM, 1),
                            min_value=0.0, max_value=53.0, step=0.5, key=f"kdv_hrs_wk_{lbl}",
                            help="Hours per week child attends nursery. E.g. 3 full days ~30 hrs/wk. Max subsidised ~53 hrs/wk.")
                        _r = _kr2.number_input("Dagopvang - rate (EUR/hr)",
                            value=float(sv.get("kdv_rate") or 11.23),
                            min_value=0.0, max_value=20.0, step=0.25, key=f"kdv_rate_{lbl}",
                            help="Hourly rate your nursery charges. Subsidy capped at EUR 11.23/hr (2026). You pay any excess.")
                        kdv_hrs = round(_h_wk * _WEEKS_PM, 1); kdv_rate = _r
                    if n_bso > 0:
                        _kr3, _kr4 = st.columns(2)
                        _h2_wk = _kr3.number_input("BSO - hours/week",
                            value=round(float(sv.get("bso_hrs") or 18.5) / _WEEKS_PM, 1),
                            min_value=0.0, max_value=32.0, step=0.5, key=f"bso_hrs_wk_{lbl}",
                            help="Hours per week in after-school care. E.g. 5 days x 3 hrs ~15 hrs/wk. Max subsidised ~32 hrs/wk.")
                        _r2 = _kr4.number_input("BSO - rate (EUR/hr)",
                            value=float(sv.get("bso_rate") or 9.98),
                            min_value=0.0, max_value=15.0, step=0.25, key=f"bso_rate_{lbl}",
                            help="Hourly rate your BSO charges. Subsidy capped at EUR 9.98/hr (2026).")
                        bso_hrs = round(_h2_wk * _WEEKS_PM, 1); bso_rate = _r2
                    _ks1, _ks2 = st.columns(2)
                    kot_start_ym = _ks1.text_input("Childcare starts (YYYY-MM)",
                        value=sv.get("kot_start_ym", "2027-01"), key=f"kot_start_{lbl}",
                        help="Month childcare begins. Subsidy applied from this month.")
                    kot_end_ym = _ks2.text_input("Childcare ends (YYYY-MM, blank = ongoing)",
                        value=sv.get("kot_end_ym", ""), key=f"kot_end_{lbl}",
                        help="Last month of childcare. Leave blank if ongoing. Typical: child turns 12.")
                    _gross_preview = sv.get("inc_s", 72000) + (sv.get("inc_p", 0) if sv.get("partner", False) else 0)
                    _kot_preview   = kinderopvangtoeslag(_gross_preview, n_kdv, n_bso, kdv_hrs, bso_hrs, kdv_rate, bso_rate)
                    _kdv_gross_mo  = round((kdv_hrs or 0) * (kdv_rate or 0)) if n_kdv > 0 else 0
                    _bso_gross_mo  = round((bso_hrs or 0) * (bso_rate or 0)) if n_bso > 0 else 0
                    _total_gross   = _kdv_gross_mo + _bso_gross_mo
                    _net_cost      = max(_total_gross - _kot_preview, 0)
                    _krow1, _krow2, _krow3 = st.columns(3)
                    _krow1.metric("Gross childcare/mo", f"EUR {_total_gross:,.0f}",
                        help="Total monthly childcare bill before any subsidy.")
                    _krow2.metric("KOT benefit/mo", f"EUR {_kot_preview:,.0f}",
                        help=f"Estimated government subsidy ({kdv_subsidy_pct(_gross_preview)*100:.0f}% of capped costs).")
                    _krow3.metric("Net cost/mo", f"EUR {_net_cost:,.0f}",
                        delta=f"-EUR {_kot_preview:,.0f} subsidy", delta_color="normal",
                        help="Out-of-pocket childcare cost after government subsidy.")

            # ════════════════════════════════════════════════════════════════
            # 5 — PROJECTION ASSUMPTIONS
            # ════════════════════════════════════════════════════════════════
            with st.expander("📈 Projection Assumptions", expanded=False):
                st.caption(_lbl_proj.replace("📈 Projection — ", "📊 "))
                w1, w2 = st.columns(2)
                savings = w1.number_input("Starting savings (€)",
                    value=sv.get("savings", 80000), step=5000, key=f"sv_{lbl}",
                    help="Total liquid savings at January 2026. Down payment and buying costs are deducted on the purchase date.")
                n_years = w2.slider("Projection years", 3, 15, sv.get("n_years", 5), key=f"ny_{lbl}",
                    help="How many years to project from January 2026. The Mortgage tab always shows the full 30-year schedule. "
                         "If a house sale date is set beyond this window, the projection is automatically extended to include it.")
                # Auto-extend: warn if sell date is beyond projection
                if sv.get("sell_house", False):
                    _sell_yr_chk = sv.get("sy", 2031)
                    _proj_end_chk = 2026 + n_years
                    if _sell_yr_chk > _proj_end_chk:
                        st.info(
                            f"ℹ️ House sale ({_sell_yr_chk}) is beyond the projection window "
                            f"(ends {_proj_end_chk}). The projection will be automatically extended to "
                            f"{_sell_yr_chk + 1} to include the sale.",
                            icon="📅"
                        )
                w3, w4 = st.columns(2)
                ha = w3.slider("House appreciation (%/yr)", 0.0, 8.0, sv.get("ha", 0.03) * 100, 0.5,
                    key=f"ha_{lbl}",
                    help="Annual house price growth. Long-run Dutch average ~2–4%; recent years 5–8%.") / 100
                ir = w4.number_input("Investment return (%/yr)", value=round(sv.get("ir", 0.05) * 100, 1),
                    min_value=0.0, max_value=25.0, step=0.5,
                    key=f"ir_{lbl}",
                    help="Annual return on savings/investments. Global index ETF historically ~7–9%/yr pre-tax.") / 100
                global_inflation = st.slider("Global inflation floor (%/yr)", 0.0, 5.0,
                    sv.get("global_inflation", 0.0) * 100, 0.25,
                    key=f"gi_{lbl}",
                    help="Sets a minimum annual growth rate for ALL expense categories. Any category with a lower per-item rate will be raised to this floor. "
                         "0% = use per-category rates only. 2.5% = Dutch CPI baseline.") / 100
                net_worth_start = 0

            # ════════════════════════════════════════════════════════════════
            # 6 — FUTURE RECURRING EXPENSES  (paid)
            # ════════════════════════════════════════════════════════════════
            with st.expander("🍼 Future Recurring Expenses" + (" 🔒" if not IS_PAID else ""), expanded=False):
                st.caption(_lbl_future.replace("🍼 Future Recurring Expenses — ", "📊 "))
                if not IS_PAID:
                    _paid_gate("Future Recurring Expenses", icon="🍼")
                    st.caption(
                        "Plan upcoming costs like childcare, school fees, or a second car. "
                        "Each is added to your monthly expenses from its start date, compounding at its own growth rate."
                    )
                    future_expenses = sv.get("future_expenses", [])
                else:
                    fe_key = f"future_exp_list_{lbl}"
                    if fe_key not in st.session_state:
                        st.session_state[fe_key] = [
                            dict(name=x["name"], amount=x["amount"],
                                 start_ym=x["start_ym"], growth=x.get("growth", 0.02),
                                 end_ym=x.get("end_ym", ""))
                            for x in sv.get("future_expenses", [])
                        ]
                    fe_list = st.session_state[fe_key]

                    to_delete = None
                    if fe_list:
                        fh1, fh2, fh3, fh4, fh5, fh6 = st.columns([2.4, 1.2, 1.4, 1.4, 1.2, 0.6])
                        fh1.markdown("**Name**"); fh2.markdown("**€/mo**")
                        fh3.markdown("**Starts**"); fh4.markdown("**%/yr**")
                        fh5.markdown("**Ends**"); fh6.markdown("**Del**")
                        for i, fe in enumerate(fe_list):
                            fc1, fc2, fc3, fc4, fc5, fc6 = st.columns([2.4, 1.2, 1.4, 1.4, 1.2, 0.6])
                            new_name   = fc1.text_input("_", value=fe["name"], key=f"fe_name_{lbl}_{i}", label_visibility="collapsed")
                            new_amt    = fc2.number_input("_", value=float(fe["amount"]), step=25.0, min_value=0.0, key=f"fe_amt_{lbl}_{i}", label_visibility="collapsed")
                            new_ym     = fc3.text_input("_", value=fe["start_ym"], key=f"fe_ym_{lbl}_{i}", placeholder="2027-06", label_visibility="collapsed", help="Start month — format: YYYY-MM")
                            new_gr     = fc4.number_input("_", value=round(fe.get("growth", 0.02)*100, 1), step=0.5, min_value=0.0, max_value=20.0, key=f"fe_gr_{lbl}_{i}", label_visibility="collapsed",
                                help="💡 Baby/childcare: 3–5%/yr. School fees: 3–6%/yr. General inflation: 2–3%/yr.") / 100
                            new_end_ym = fc5.text_input("_", value=fe.get("end_ym", ""), key=f"fe_end_{lbl}_{i}", placeholder="2032-06 or blank", label_visibility="collapsed",
                                help="End month (inclusive) — leave blank to run indefinitely. Format: YYYY-MM")
                            if fc6.button("✕", key=f"fe_del_{lbl}_{i}", help="Remove"):
                                to_delete = i
                            fe_list[i] = dict(name=new_name, amount=new_amt, start_ym=new_ym, growth=new_gr, end_ym=new_end_ym)

                    if to_delete is not None:
                        fe_list.pop(to_delete)
                        st.rerun()

                    if st.button("➕ Add future expense", key=f"fe_add_{lbl}"):
                        _ny = sv.get("n_years", 5)
                        fe_list.append(dict(
                            name="New expense", amount=200.0,
                            start_ym=f"{2026 + max(1, _ny // 2)}-01", growth=0.02, end_ym="",
                        ))
                        st.rerun()

                    if fe_list:
                        with st.expander("📊 Preview: monthly impact over time", expanded=False):
                            _proj_months = pd.date_range(start="2026-01-01", periods=sv.get("n_years", 5) * 12, freq="MS")
                            _fe_preview = []
                            for _dt in _proj_months:
                                _total = 0.0
                                _dt_ym = f"{_dt.year}-{_dt.month:02d}"
                                for _fe in fe_list:
                                    _fe_end_p = _fe.get("end_ym", "")
                                    if _dt_ym >= _fe.get("start_ym", "9999-99") and (not _fe_end_p or _dt_ym <= _fe_end_p):
                                        _sy = int(_fe["start_ym"][:4]); _sm_fe = int(_fe["start_ym"][5:7])
                                        _yf = (_dt.year - _sy) + (_dt.month - _sm_fe) / 12
                                        _total += _fe["amount"] * (1 + _fe.get("growth", 0.0)) ** max(_yf, 0)
                                _fe_preview.append({"Month": _dt_ym, "Total future expenses (€)": round(_total)})
                            _fe_df = pd.DataFrame(_fe_preview)
                            if _fe_df["Total future expenses (€)"].gt(0).any():
                                _fig_fe = go.Figure()
                                _fig_fe.add_trace(go.Scatter(
                                    x=pd.to_datetime(_fe_df["Month"] + "-01"),
                                    y=_fe_df["Total future expenses (€)"],
                                    fill="tozeroy", fillcolor="rgba(231,76,60,0.15)",
                                    line=dict(color="#e74c3c", width=2), name="Future expenses/mo"
                                ))
                                seen_yms = set()
                                for _fe in fe_list:
                                    if _fe["start_ym"] not in seen_yms:
                                        seen_yms.add(_fe["start_ym"])
                                        _xs = pd.Timestamp(_fe["start_ym"] + "-01").strftime("%Y-%m-%d")
                                        _fig_fe.add_shape(type="line", x0=_xs, x1=_xs, y0=0, y1=1,
                                            xref="x", yref="paper", line=dict(dash="dash", color="#f1c40f", width=1.5))
                                        if not _narrow:
                                            _fig_fe.add_annotation(x=_xs, y=0.95, xref="x", yref="paper",
                                                text=_fe["name"], showarrow=False, xanchor="left",
                                                font=dict(color="#f1c40f", size=10))
                                    # End marker (red dashed) if end_ym is set
                                    _fe_end_ym = _fe.get("end_ym", "")
                                    if _fe_end_ym:
                                        try:
                                            _xe = pd.Timestamp(_fe_end_ym + "-01").strftime("%Y-%m-%d")
                                            _fig_fe.add_shape(type="line", x0=_xe, x1=_xe, y0=0, y1=1,
                                                xref="x", yref="paper", line=dict(dash="dot", color="#e74c3c", width=1.5))
                                            if not _narrow:
                                                _fig_fe.add_annotation(x=_xe, y=0.80, xref="x", yref="paper",
                                                    text=f"ends {_fe['name']}", showarrow=False, xanchor="right",
                                                    font=dict(color="#e74c3c", size=9))
                                        except Exception:
                                            pass
                                _fig_fe.update_layout(**chart_layout("Combined future recurring expenses", height=260))
                                st.plotly_chart(_fig_fe, use_container_width=True, key=f"fig_fe_{lbl}")
                            else:
                                st.caption("No future expenses active within the projection window yet.")

                    future_expenses = fe_list

            # ════════════════════════════════════════════════════════════════
            # 7 — HISTORIC DATA RANGE  (paid)
            # ════════════════════════════════════════════════════════════════
            with st.expander("📅 Historic Data Range" + (" 🔒" if not IS_PAID else ""), expanded=False):
                st.caption(_lbl_hist.replace("📅 Historic Data Range — ", "📊 "))
                if not IS_PAID:
                    _paid_gate("Actuals Tracking — Historic Date Range", icon="📅")
                    st.caption("Configure the date range for tracking your real income and savings in the Actuals tab.")
                    hist_start = sv.get("hist_start", DEFAULTS["hist_start"])
                    hist_end   = sv.get("hist_end",   DEFAULTS["hist_end"])
                else:
                    st.caption(
                        "The period for which you have real income and expense data. "
                        "The **Actuals tab** shows every month in this range ready to fill in."
                    )
                    import datetime as _dt_setup
                    _today = _dt_setup.date.today()
                    # Build flat list of YYYY-MM strings from Jan 2023 to end of projection + 2 yrs
                    _proj_end_yr = 2026 + n_years
                    _ym_options = [f"{_y}-{_m:02d}" for _y in range(2023, _proj_end_yr + 3) for _m in range(1, 13)]
                    _default_hist_start = sv.get("hist_start", "2026-01")
                    _default_hist_end   = sv.get("hist_end",   _today.strftime("%Y-%m"))
                    _hs_idx = _ym_options.index(_default_hist_start) if _default_hist_start in _ym_options else 0
                    _he_idx = _ym_options.index(_default_hist_end)   if _default_hist_end   in _ym_options else len(_ym_options) - 1
                    _yr_range  = list(range(2023, _proj_end_yr + 3))
                    _mo_names  = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
                    # Parse saved start value
                    _hs_yr = int(_default_hist_start[:4]); _hs_mo = int(_default_hist_start[5:])
                    hd1, hd2 = st.columns(2)
                    _hs_yr_sel = hd1.selectbox("From — year",  _yr_range,
                        index=_yr_range.index(_hs_yr) if _hs_yr in _yr_range else 0,
                        key=f"hs_yr_{lbl}")
                    _hs_mo_sel = hd2.selectbox("From — month", _mo_names,
                        index=_hs_mo - 1, key=f"hs_mo_{lbl}")
                    hist_start = f"{_hs_yr_sel}-{(_mo_names.index(_hs_mo_sel)+1):02d}"
                    # End is always locked to the projection end date for consistency
                    _proj_end_ym = f"{_proj_end_yr}-12"
                    hist_end = _proj_end_ym
                    st.info(f"📅 **From:** {hist_start}  →  **To:** {hist_end} *(locked to projection end)*", icon="🔒")

            params[lbl] = dict(
                inc_s=inc_s, inc_s_incl_vg=inc_s_incl_vg,
                use_net_input=_use_net_input,
                net_mo_input=sv.get('net_mo_input', 3500),
                use_net_input_p=_use_net_input_p if partner else False,
                net_mo_input_p=sv.get('net_mo_input_p', 3500),
                partner=partner, inc_p=inc_p,
                n_kdv=n_kdv, n_bso=n_bso, kdv_hrs=kdv_hrs, bso_hrs=bso_hrs,
                kdv_rate=kdv_rate, bso_rate=bso_rate,
                sal_growth=sal_growth, sal_growth_p=sal_growth_p,
                rs=rs, re=re,
                ruling_s=ruling_s, rs_s=rs_s, re_s=re_s, rs_s_start=rs_s_start,
                ruling_p=ruling_p, rs_p=rs_p, re_p=re_p, rs_p_start=rs_p_start,
                rent=rent, by=by, bm=bm,
                house_price=house_price, dp=dp, mort_rate=mr,
                mort_type=mort_type,
                already_owns=already_owns, current_home_value=current_home_value,
                sell_house=sell_house, sy=sy, sm=sm,
                hi=hi, cf=cf, ci=ci, gr=gr, ot=ot,
                utilities=utilities, phone=phone,
                subscriptions=subscriptions, gym=gym, dog=dog,
                savings=savings, n_years=n_years, ha=ha, ir=ir,
                exp_growth=exp_growth,
                exp_notes=exp_notes,
                hist_start=hist_start, hist_end=hist_end,
                future_expenses=future_expenses,
                ab_mode=ab_mode,
                global_inflation=global_inflation,
                kot_start_ym=kot_start_ym, kot_end_ym=kot_end_ym,
                scenario_label=scenario_label,
            )

    # ── Auto-extend projection to cover sell date ────────────────────────────
    for _lbl_ext in list(params.keys()):
        _p_ext = params[_lbl_ext]
        if _p_ext.get("sell_house", False):
            _sell_end_yr  = _p_ext.get("sy", 2031) + 1   # +1 so post-sale months are visible
            _proj_end_yr  = 2026 + _p_ext.get("n_years", 5)
            if _sell_end_yr > _proj_end_yr:
                _p_ext["n_years"] = _sell_end_yr - 2026

    # ── If B not shown, copy A as placeholder ────────────────────────────────
    if "B" not in params:
        params["B"] = params["A"].copy()




    # ── Navigate to next tab ────────────────────────────────────────────────────
    st.divider()
    st.info(
        "**All inputs set?** Click the **📊 Income & Tax** tab above "
        "to see your monthly net income forecast, 30% ruling impact and expense breakdown.",
        icon="➡️",
    )

    # ── Save / Load Settings  (Pro) ──────────────────────────────────────────
    st.divider()
    st.markdown("### 💾 Save & Load Settings")
    if IS_PAID:
        st.caption(
            "Your settings are **not stored on the server** — download them to your device "
            "and re-upload next time to restore everything instantly."
        )
        _io_c1, _io_c2 = st.columns(2)
        _io_c1.download_button(
            label="⬇️ Download settings (.csv)",
            data=settings_to_csv_bytes(params["A"], params["B"]),
            file_name="dutch_dashboard_settings.csv",
            mime="text/csv",
            use_container_width=True,
            help="Saves all current inputs to a CSV file on your device.",
        )
        _uploaded_settings = _io_c2.file_uploader(
            "⬆️ Upload settings (.csv)",
            type=["csv"],
            key="settings_upload",
            label_visibility="collapsed",
            help="Upload a previously downloaded settings CSV to restore your inputs.",
        )
        _io_c2.caption("⬆️ Upload a previously saved settings CSV to restore your inputs.")
        if _uploaded_settings is not None:
            _sa_new, _sb_new = settings_from_uploaded_file(_uploaded_settings)
            st.session_state["saved_A"] = _sa_new
            st.session_state["saved_B"] = _sb_new
            st.success("✅ Settings loaded — the page will refresh with your saved values.")
            st.rerun()
    else:
        st.markdown(
            "<div style='background:#1e293b;border:1px solid #334155;"
            "border-radius:8px;padding:10px 14px'>"
            "<span style='color:#f1c40f;font-weight:700'>🔒 Pro feature</span>"
            " <span style='color:#94a3b8;font-size:12px'>— Upgrade to save and restore "
            "your settings between sessions.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

    # ── Export PDF Report  (Pro) ─────────────────────────────────────────────
    st.divider()
    st.markdown("### 📄 Export PDF Report")
    if IS_PAID:
        st.markdown(
            "<div style='background:#eff6ff;border:1px solid #bfdbfe;"
            "border-radius:8px;padding:10px 14px;margin-bottom:8px'>"
            "<span style='color:#1e40af;font-weight:700;font-size:13px'>⭐ Pro</span>"
            " <span style='color:#3b82f6;font-size:12px'>— Full A4 PDF with table of contents, "
            "income &amp; tax tables, Buy vs Rent, mortgage analysis and setup summary.</span>"
            "</div>",
            unsafe_allow_html=True,
        )
        _pdf_left, _pdf_right = st.columns([2, 1])
        with _pdf_left:
            if st.button(
                "📥 Generate PDF Report",
                type="primary",
                use_container_width=True,
                key="btn_gen_pdf",
                help="Builds the PDF after clicking — simulations run first.",
            ):
                st.session_state["_pdf_requested"] = True
        with _pdf_right:
            if st.session_state.get("_pdf_ready"):
                st.download_button(
                    label="⬇️ Download PDF",
                    data=st.session_state["_pdf_ready"],
                    file_name=st.session_state.get("_pdf_fname", "dutch_dashboard.pdf"),
                    mime="application/pdf",
                    use_container_width=True,
                    key="btn_dl_pdf",
                )
            else:
                st.caption("Click Generate to build the PDF, then download it here.")
        if st.session_state.get("_pdf_ready"):
            st.success("✅ PDF ready — click Download above.")
    else:
        st.markdown(
            "<div style='background:#1e293b;border:1px solid #334155;"
            "border-radius:8px;padding:10px 14px'>"
            "<span style='color:#f1c40f;font-weight:700'>🔒 Pro feature</span>"
            " <span style='color:#94a3b8;font-size:12px'>— Upgrade to export a professional "
            "PDF report with charts, tables and a table of contents.</span>"
            "</div>",
            unsafe_allow_html=True,
        )

# ════════════════════════════════════════════════════════════════════════════════
# RUN SIMULATIONS (after Setup tab so params are defined)
# ════════════════════════════════════════════════════════════════════════════════

pa = params["A"]
pb = params["B"]

# ── Session-state init ───────────────────────────────────────────────────────
for _k, _v in [("_pdf_ready", None), ("_pdf_requested", False), ("_pdf_fname", "")]:
    if _k not in st.session_state:
        st.session_state[_k] = _v

df_m_a, df_w_a = run_sim(pa)
df_m_b, df_w_b = run_sim(pb)

# ── Lazy PDF generation (triggered by Generate button in Setup) ──────────────
if st.session_state.get("_pdf_requested"):
    st.session_state["_pdf_requested"] = False
    with st.spinner("Building PDF report — this takes a few seconds…"):
        try:
            import datetime as _dtpdf
            # Build retirement params dict from session state
            _ret_p = {
                "ret_current_age":  st.session_state.get("ret_age_now",  32),
                "ret_age":          st.session_state.get("ret_age",       67),
                "ret_target_income":st.session_state.get("ret_target",  3500),
                "ret_aow":          st.session_state.get("ret_aow",     1450),
                "ret_pension":      st.session_state.get("ret_pension",   500),
                "ret_swr":          st.session_state.get("ret_swr",     0.035),
                "ret_return_pre":   st.session_state.get("ret_ret_pre",  0.07),
                "ret_return_post":  st.session_state.get("ret_ret_post", 0.04),
                "ret_inflation":    st.session_state.get("ret_inflation",0.025),
            }
            _pdf_bytes = generate_pdf_report(
                pa, pb, df_m_a, df_w_a, df_m_b, df_w_b,
                ab_mode=ab_mode, ret_params=_ret_p
            )
            st.session_state["_pdf_ready"] = _pdf_bytes
            st.session_state["_pdf_fname"] = (
                f"dutch_dashboard_{_dtpdf.date.today():%Y%m%d}.pdf"
            )
            st.rerun()  # re-render so Download button appears
        except Exception as _pdf_err:
            st.error(f"PDF generation failed: {_pdf_err}")

# ════════════════════════════════════════════════════════════════════════════════
# TAB 1 — INCOME & TAX
# ════════════════════════════════════════════════════════════════════════════════

with tabs[1]:
    df = df_m_a; p = pa
    # ── Negative savings alert ────────────────────────────────────────────
    _neg_sav = df_m_a[df_m_a["Net Saving"] < 0]
    if not _neg_sav.empty:
        _neg_months = _neg_sav["Date"].dt.strftime("%b %Y").tolist()
        _worst      = _neg_sav.loc[_neg_sav["Net Saving"].idxmin()]
        _worst_mo   = _worst["Date"].strftime("%b %Y")
        _worst_val  = _worst["Net Saving"]
        _scen_name  = pa.get("scenario_label") or "Scenario A"
        _mo_list    = ", ".join(_neg_months[:6]) + (f" (+{len(_neg_months)-6} more)" if len(_neg_months) > 6 else "")
        st.error(
            f"🚨 **{_scen_name}: cashflow goes negative in {len(_neg_months)} month(s)** — "
            f"{_mo_list}. "
            f"Worst month: **{_worst_mo}** at **−€{abs(_worst_val):,.0f}**. "
            "Check your expenses, salary growth, or move the house purchase date.",
            icon="⚠️"
        )

    with st.expander("ℹ️ What does this tab show?", expanded=False):
        st.markdown("""
📊 **Monthly net income and expense breakdown for Scenario A**, using your income, 30% ruling dates, and all expense inputs from Setup.

- **Net income** is after Box 1 tax, ZVW, algemene heffingskorting, and arbeidskorting
- The **30% ruling** shaded band shows the period where 70% of gross is taxed
- **Zorgtoeslag** is shown where applicable and subtracted as an income credit from expenses
- See the **"How are these numbers calculated?"** expander at the bottom for full methodology and tax breakdown
        """)
    import datetime as _dt
    _today_ym = _dt.date.today().strftime("%Y-%m")
    _cur_mask = df["Date"].dt.strftime("%Y-%m") == _today_ym
    _cur_row  = df[_cur_mask].iloc[0] if _cur_mask.any() else df.iloc[0]
    cur_net   = _cur_row["Total Net"]
    cur_exp   = _cur_row["Total Expenses"]
    cur_sav   = _cur_row["Net Saving"]
    cur_zts   = _cur_row["Zorgtoeslag"]
    cur_kot   = _cur_row.get("Kinderopvangtoeslag", 0)
    cur_lbl   = _cur_row["Date"].strftime("%b %Y")
    _yr_cur   = _cur_row["Date"].year
    _sg       = p.get("sal_growth", 0.0)
    _ye       = _yr_cur - 2026
    _a30_s_cur = p.get("ruling_s", True)  and p.get("rs_s", p["rs"]) <= _yr_cur < p.get("re_s", p["re"])
    _a30_p_cur = p.get("ruling_p", False) and p.get("rs_p", p["rs"]) <= _yr_cur < p.get("re_p", p["re"])
    _nm_s_on  = net_monthly_calc(p["inc_s"]*(1+_sg)**_ye, _yr_cur, True)
    _nm_p_on  = net_monthly_calc(p["inc_p"]*(1+_sg)**_ye, _yr_cur, True)  if p["partner"] else 0
    _nm_s_off = net_monthly_calc(p["inc_s"]*(1+_sg)**_ye, _yr_cur, False)
    _nm_p_off = net_monthly_calc(p["inc_p"]*(1+_sg)**_ye, _yr_cur, False) if p["partner"] else 0
    # Ruling benefit = difference only for people who actually have it active now
    cur_ruling_ben = ((_nm_s_on - _nm_s_off) if _a30_s_cur else 0) + \
                     ((_nm_p_on - _nm_p_off) if _a30_p_cur else 0)
    r_on  = df[df["30% Ruling"]]["Net Saving"].mean()  if df["30% Ruling"].any()  else cur_sav
    r_off = df[~df["30% Ruling"]]["Net Saving"].mean() if (~df["30% Ruling"]).any() else cur_sav

    # ── 30% ruling impact banner ─────────────────────────────────────────────
    sg = p.get("sal_growth", 0.0)
    _has_ruling_s = p.get("ruling_s", True)
    _has_ruling_p = p.get("ruling_p", False) and p.get("partner", False)
    _re_s = p.get("re_s", p["re"]) if _has_ruling_s else None
    _re_p = p.get("re_p", p["re"]) if _has_ruling_p else None
    # Build per-person impact blocks only for those who have the ruling
    _banner_parts = []
    _table_rows = []
    _combined_drop = 0
    if _has_ruling_s:
        _yr_end = _re_s
        _on  = net_monthly_calc(p["inc_s"]*(1+sg)**(_yr_end-1-2026), _yr_end-1, True)
        _off = net_monthly_calc(p["inc_s"]*(1+sg)**(_yr_end  -2026), _yr_end,   False)
        _drop = _on - _off
        _combined_drop += _drop
        _banner_parts.append(f"**Your** ruling expires {_yr_end}: −€{_drop:,.0f}/mo")
        _table_rows.append(f"| **Your net/mo** | {_yr_end-1} ruling on: €{_on:,.0f} | {_yr_end} ruling off: €{_off:,.0f} | **−€{_drop:,.0f}** |")
    if _has_ruling_p:
        _yr_end_p = _re_p
        _on_p  = net_monthly_calc(p["inc_p"]*(1+sg)**(_yr_end_p-1-2026), _yr_end_p-1, True)
        _off_p = net_monthly_calc(p["inc_p"]*(1+sg)**(_yr_end_p  -2026), _yr_end_p,   False)
        _drop_p = _on_p - _off_p
        _combined_drop += _drop_p
        _banner_parts.append(f"**Partner** ruling expires {_yr_end_p}: −€{_drop_p:,.0f}/mo")
        _table_rows.append(f"| **Partner net/mo** | {_yr_end_p-1} ruling on: €{_on_p:,.0f} | {_yr_end_p} ruling off: €{_off_p:,.0f} | **−€{_drop_p:,.0f}** |")

    if _banner_parts:
        st.warning(
            "⚠️ **30% Ruling expiry impact** — " + "  |  ".join(_banner_parts) +
            f"  |  Combined household drop: **−€{_combined_drop:,.0f}/mo (−€{_combined_drop*12:,.0f}/yr)**.",
            icon="📉"
        )
        # Ruling breakdown moved to bottom "How are these numbers calculated?" expander
    else:
        st.info("ℹ️ Neither person has the 30% ruling enabled — no ruling expiry impact to show.", icon="💡")
    # For KPI calculations below, derive a combined ruling end year (earliest expiry among active rulings)
    _ruling_end_yr = min(x for x in [_re_s, _re_p] if x is not None) if (_has_ruling_s or _has_ruling_p) else None

    # ── Savings dip alert ───────────────────────────────────────────────────
    _neg_months = df[df["Net Saving"] < 0].copy()
    if not _neg_months.empty:
        _neg_list = ", ".join(
            f"{r['Date'].strftime('%b %Y')} (€{r['Net Saving']:,.0f})"
            for _, r in _neg_months.head(5).iterrows()
        )
        _more = f" + {len(_neg_months)-5} more" if len(_neg_months) > 5 else ""
        st.warning(
            f"⚠️ **Savings dip below zero in {len(_neg_months)} month(s):** {_neg_list}{_more}. "
            "Check your expense growth rates, future recurring expenses, or mortgage costs — "
            "you may need to build a larger buffer or reduce spending in those months.",
            icon="💸"
        )

    st.divider()
    st.caption(f"Showing **{cur_lbl}** — current month in projection.")
    _has_kot = pa.get("n_kdv",0) > 0 or pa.get("n_bso",0) > 0

    # Pre-compute net-without-ruling for KPIs and waterfall
    _wf_net_off     = _nm_s_off + (_nm_p_off if p["partner"] else 0)
    _wf_benefit     = cur_net - _wf_net_off
    _wf_exp         = cur_exp
    _wf_surplus_off = _wf_net_off - _wf_exp   # free cashflow WITHOUT ruling
    _wf_surplus_on  = cur_net - _wf_exp        # free cashflow WITH ruling
    _ruling_on_now  = _a30_s_cur or _a30_p_cur

    # ── Cashflow callout at the very top ────────────────────────────────────
    if _wf_surplus_off >= 0:
        st.success(
            f"{'✅ 30% ruling active — ' if _ruling_on_now else ''}"
            f"Without the ruling your income **€{_wf_net_off:,.0f}/mo** still covers "
            f"expenses **€{_wf_exp:,.0f}/mo** — leaving **€{_wf_surplus_off:,.0f}/mo** free cashflow. "
            + (f"The ruling adds **€{_wf_benefit:,.0f}/mo** on top (total free cashflow with ruling: **€{_wf_surplus_on:,.0f}/mo**)."
               if _ruling_on_now else ""),
            icon="💪"
        )
    else:
        st.error(
            f"{'⚠️ 30% ruling active — ' if _ruling_on_now else '⚠️ '}"
            f"Without the ruling your income **€{_wf_net_off:,.0f}/mo** falls "
            f"**€{abs(_wf_surplus_off):,.0f}/mo short** of expenses **€{_wf_exp:,.0f}/mo**. "
            + (f"The ruling currently bridges this gap (free cashflow with ruling: **€{_wf_surplus_on:,.0f}/mo**). "
               f"Plan ahead before Jan {_re_s}." if _ruling_on_now else
               "Consider reducing expenses or increasing income."),
            icon="🔔"
        )

    # ── KPIs: 1 income(with) · 2 ruling benefit · 3 income(without) · 4 expenses · 5 cashflow(without) ──
    _on_icon  = "🟢" if _ruling_on_now else "⚪"  # green = ruling active, grey = off
    _off_icon = "🔴" if _ruling_on_now else "⚪"  # red = ruling will expire / not active
    _n_km = 6 if _has_kot else 5
    _km_cols = st.columns(_n_km)

    _km_cols[0].metric(f"{_on_icon} Income (with 30%)", f"€{cur_net:,.0f}",
        help=f"Combined net income in {cur_lbl} {'with the 30% ruling active' if _ruling_on_now else '(ruling not active)'}.")
    _km_cols[1].metric(f"{'🎯' if _ruling_on_now else '—'} 30% Ruling Benefit", f"€{_wf_benefit:,.0f}",
        help=f"{'Extra income from the ruling — drops to zero at expiry.' if _ruling_on_now else 'No ruling active — benefit is zero.'} €{_nm_s_on:,.0f} (with) vs €{_nm_s_off:,.0f} (without).")
    _km_cols[2].metric(f"{_off_icon} Income (without 30%)", f"€{_wf_net_off:,.0f}",
        help=f"Net income in {cur_lbl} without the ruling — what you will take home after it expires.")
    _km_cols[3].metric("💸 Expenses", f"€{_wf_exp:,.0f}",
        help=f"All fixed expenses in {cur_lbl}: housing, categories from Setup, net of MRI credits.")
    _savings_off_sign = "surplus ✅" if _wf_surplus_off >= 0 else "deficit ⚠️"
    _km_cols[4].metric(f"{_off_icon} Cashflow (without 30%)", f"€{_wf_surplus_off:,.0f}",
        delta=_savings_off_sign,
        delta_color="normal" if _wf_surplus_off >= 0 else "inverse",
        help=f"Income without ruling (€{_wf_net_off:,.0f}) − expenses (€{_wf_exp:,.0f}). Free cashflow after expiry.")
    if _has_kot:
        _km_cols[5].metric("👶 Kinderopvangtoeslag", f"€{cur_kot:,.0f}",
            help="Monthly childcare benefit (dagopvang/BSO), income-tested.")

    # ── 30% Ruling impact waterfall (below KPIs) ────────────────────────────
    st.divider()
    fig_ruling_wf = go.Figure(go.Waterfall(
        orientation="v",
        measure=["absolute", "relative", "relative", "total"],
        x=[
            "Net Income<br>(with 30%)",
            "− 30% Ruling<br>Benefit",
            "− Total<br>Expenses",
            "Free Cashflow<br>(without 30%)",
        ],
        y=[cur_net, -_wf_benefit, -_wf_exp, 0],
        text=[
            f"€{cur_net:,.0f}",
            f"−€{_wf_benefit:,.0f}",
            f"−€{_wf_exp:,.0f}",
            f"€{_wf_surplus_off:,.0f}",
        ],
        textposition="outside",
        connector=dict(line=dict(color="rgba(255,255,255,0.2)")),
        increasing=dict(marker_color="#2ecc71"),
        decreasing=dict(marker_color="#e74c3c"),
        totals=dict(marker_color="#2ecc71" if _wf_surplus_off >= 0 else "#e74c3c"),
    ))
    fig_ruling_wf.add_hline(y=0, line_color="#f1c40f", line_width=1.5, line_dash="dot",
        annotation_text="Break-even", annotation_position="bottom right",
        annotation_font=dict(size=9, color="#f1c40f"))
    fig_ruling_wf.update_layout(**chart_layout(
        f"30% Ruling Impact — Free Cashflow after Expiry ({cur_lbl})",
        "€/month", height=400
    ))
    st.plotly_chart(fig_ruling_wf, use_container_width=True, key="fig_ruling_waterfall")

    st.divider()

    # ── Actuals overlay toggle (paid only) ────────────────────────────────────
    if IS_PAID:
        show_actuals_overlay = st.toggle(
            "📌 Overlay actuals data on chart",
            value=True,
            key="income_tax_actuals_toggle",
            help="Shows actual income and savings from the 📝 Actuals tab on top of the forecast lines. "
                 "Enter data in the Actuals tab first."
        )
    else:
        show_actuals_overlay = False

    # Load actuals for overlay
    _act_overlay = load_actuals()
    _has_overlay_data = (show_actuals_overlay and not _act_overlay.empty
                         and "month" in _act_overlay.columns)

    if show_actuals_overlay and not _has_overlay_data:
        st.caption("ℹ️ No actuals data found — enter data in the 📝 Actuals tab first.")

    _explain = st.toggle(
        "💬 Explain the data",
        value=False,
        key="income_explain_toggle",
        help="Highlight and explain the most significant changes on the forecast chart."
    )

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Total Net"], name="Net Income",
                              line=dict(color="#2ecc71", width=2.5),
                              fill="tozeroy", fillcolor="rgba(46,204,113,0.07)"))
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Total Expenses"], name="Expenses",
                              line=dict(color="#e74c3c", width=2.5),
                              fill="tozeroy", fillcolor="rgba(231,76,60,0.07)"))
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Net Saving"], name="Savings",
                              line=dict(color="#3498db", width=2, dash="dot")))

    if _has_overlay_data:
        # Build actuals series aligned to dates
        _ov = _act_overlay.copy()
        _ov["month_dt"] = pd.to_datetime(_ov["month"] + "-01")
        for _c in ["inc_s_actual","inc_p_actual","savings_actual"]:
            if _c not in _ov.columns:
                _ov[_c] = None
            _ov[_c] = pd.to_numeric(_ov[_c], errors="coerce")
        # Combined actual income (from bank statements / manual entry)
        _ov["inc_combined"] = _ov[["inc_s_actual","inc_p_actual"]].sum(axis=1, min_count=1)
        _ov_inc = _ov.dropna(subset=["inc_combined"])
        _ov_sav = _ov.dropna(subset=["savings_actual"])
        # Plot combined actual income prominently
        if not _ov_inc.empty:
            fig1.add_trace(go.Scatter(
                x=_ov_inc["month_dt"], y=_ov_inc["inc_combined"],
                name="Income (act)",
                mode="lines+markers",
                line=dict(color="#27ae60", width=2.5),
                marker=dict(size=7, symbol="circle"),
            ))
            # If partner: also show individual lines
            if p.get("partner") and _ov["inc_s_actual"].notna().any():
                _ov_s = _ov.dropna(subset=["inc_s_actual"])
                fig1.add_trace(go.Scatter(
                    x=_ov_s["month_dt"], y=_ov_s["inc_s_actual"],
                    name=f"{p.get('name_s','You')} (act)",
                    mode="lines+markers",
                    line=dict(color="#2ecc71", width=1.5, dash="dot"),
                    marker=dict(size=5, symbol="circle-open"),
                ))
            if p.get("partner") and _ov["inc_p_actual"].notna().any():
                _ov_p = _ov.dropna(subset=["inc_p_actual"])
                fig1.add_trace(go.Scatter(
                    x=_ov_p["month_dt"], y=_ov_p["inc_p_actual"],
                    name=f"{p.get('name_p','Partner')} (act)",
                    mode="lines+markers",
                    line=dict(color="#f1c40f", width=1.5, dash="dot"),
                    marker=dict(size=5, symbol="circle-open"),
                ))
        if not _ov_sav.empty:
            fig1.add_trace(go.Scatter(
                x=_ov_sav["month_dt"], y=_ov_sav["savings_actual"],
                name="Savings (act)",
                mode="lines+markers",
                line=dict(color="#2980b9", width=2, dash="dash"),
                marker=dict(size=6, symbol="diamond"),
            ))

    add_events(fig1, p)
    # Add vertical markers for each future recurring expense start date
    _fe_colors = ["#e74c3c","#e67e22","#f1c40f","#9b59b6","#1abc9c","#3498db"]
    for _fi, _fe in enumerate(p.get("future_expenses", [])):
        _fe_xs = pd.Timestamp(_fe["start_ym"] + "-01").strftime("%Y-%m-%d")
        _fe_col = _fe_colors[_fi % len(_fe_colors)]
        fig1.add_shape(type="line", x0=_fe_xs, x1=_fe_xs, y0=0, y1=1,
                       xref="x", yref="paper",
                       line=dict(dash="dot", color=_fe_col, width=1.5))
        if not _narrow:
            fig1.add_annotation(x=_fe_xs, y=0.60 - (_fi * 0.09), xref="x", yref="paper",
                                text=f"💸 {_fe['name']}", showarrow=False,
                                xanchor="left", font=dict(color=_fe_col, size=10))
    # ── Explain-the-data annotations ──────────────────────────────────────
    _events_explained = []
    if _explain:
        _sym_colors = ["#f1c40f","#e67e22","#9b59b6","#1abc9c","#e74c3c","#3498db"]
        _sym_idx = 0
        # 1. 30% ruling expiry
        _re_yr_exp = p.get("re_s", p["re"]) if p.get("ruling_s") else None
        if _re_yr_exp:
            _re_ts = pd.Timestamp(year=_re_yr_exp, month=1, day=1).strftime("%Y-%m-%d")
            _net_before = net_monthly_calc(p["inc_s"]*(1+sg)**(_re_yr_exp-1-2026), _re_yr_exp-1, True)
            _net_after  = net_monthly_calc(p["inc_s"]*(1+sg)**(_re_yr_exp-2026),   _re_yr_exp,   False)
            _drop = _net_before - _net_after
            _col = _sym_colors[_sym_idx % len(_sym_colors)]; _sym_idx += 1
            fig1.add_shape(type="line", x0=_re_ts, x1=_re_ts, y0=0, y1=1,
                           xref="x", yref="paper", line=dict(dash="dash", color=_col, width=2))
            fig1.add_annotation(x=_re_ts, y=0.97, xref="x", yref="paper",
                                text="① Ruling expires", showarrow=False,
                                xanchor="left", font=dict(color=_col, size=10))
            _events_explained.append((
                "①", f"30% Ruling expires (Jan {_re_yr_exp})",
                f"Your 30% ruling ends in January {_re_yr_exp}. Net income drops by "
                f"**€{_drop:,.0f}/mo** (€{_net_before:,.0f} → €{_net_after:,.0f}/mo). "
                f"Build a savings buffer during the ruling period to absorb this reduction.",
                _col
            ))
        # 2. House purchase
        _buy_ts_exp = pd.Timestamp(year=p["by"], month=p["bm"], day=1)
        if _buy_ts_exp >= df["Date"].iloc[0] and _buy_ts_exp <= df["Date"].iloc[-1]:
            _buy_ts_str = _buy_ts_exp.strftime("%Y-%m-%d")
            _mp_net = mort_payment(p["house_price"], p["dp"], p["mort_rate"]) - \
                      amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"])["MRI_Benefit"].iloc[0]
            _col = _sym_colors[_sym_idx % len(_sym_colors)]; _sym_idx += 1
            fig1.add_shape(type="line", x0=_buy_ts_str, x1=_buy_ts_str, y0=0, y1=1,
                           xref="x", yref="paper", line=dict(dash="dash", color=_col, width=2))
            fig1.add_annotation(x=_buy_ts_str, y=0.88, xref="x", yref="paper",
                                text="② House purchase", showarrow=False,
                                xanchor="left", font=dict(color=_col, size=10))
            _buy_cost = p["house_price"] * 0.02 + 3500
            _events_explained.append((
                "②", f"House purchase ({_buy_ts_exp.strftime('%B %Y')})",
                f"Down payment **€{p['house_price']*p['dp']:,.0f}** + buying costs **€{_buy_cost:,.0f}** "
                f"deducted from savings. Rent (€{p['rent']:,.0f}/mo) replaced by net mortgage "
                f"(€{_mp_net:,.0f}/mo after MRI). Expenses change from this month.",
                _col
            ))
        # 3. Future recurring expenses
        _seen_fe = set()
        for _fi2, _fe2 in enumerate(p.get("future_expenses", [])):
            if _fe2["start_ym"] not in _seen_fe:
                _seen_fe.add(_fe2["start_ym"])
                try:
                    _fe_ts2 = pd.Timestamp(_fe2["start_ym"] + "-01")
                    _col = _sym_colors[_sym_idx % len(_sym_colors)]; _sym_idx += 1
                    _sym_num = _sym_idx + 1
                    fig1.add_annotation(x=_fe_ts2.strftime("%Y-%m-%d"), y=0.75 - (_fi2*0.08),
                                        xref="x", yref="paper",
                                        text=f"③ {_fe2['name']}", showarrow=False,
                                        xanchor="left", font=dict(color=_col, size=10))
                    _events_explained.append((
                        "③", f"Future expense starts: {_fe2['name']} ({_fe2['start_ym']})",
                        f"**€{_fe2['amount']:,.0f}/mo** recurring expense begins. "
                        f"Grows at {_fe2.get('growth',0)*100:.1f}%/yr. "
                        + (f"Ends {_fe2['end_ym']}." if _fe2.get('end_ym') else "Ongoing."),
                        _col
                    ))
                except Exception:
                    pass
        # 4. Salary growth steps (show every 2 years if growth > 0)
        if sg > 0:
            _ys = sorted(df["Year"].unique())
            for _yi, _yr_g in enumerate(_ys[2::2]):   # every 2nd year from year 3
                _col = _sym_colors[_sym_idx % len(_sym_colors)]; _sym_idx += 1
                _yr_net = net_monthly_calc(p["inc_s"]*(1+sg)**(_yr_g-2026), _yr_g, 
                    p.get("ruling_s", True) and p.get("rs_s", 2026) <= _yr_g < p.get("re_s", 2031))
                _events_explained.append((
                    f"📈", f"Salary growth by {_yr_g}",
                    f"At {sg*100:.1f}%/yr growth, gross reaches €{p['inc_s']*(1+sg)**(_yr_g-2026):,.0f} "
                    f"by {_yr_g} — net income ≈ €{_yr_net:,.0f}/mo.",
                    _col
                ))
                if _yi >= 1: break   # max 2 salary annotations

    fig1.update_layout(**chart_layout("Monthly Income vs Expenses — Forecast" +
                                      (" + Actuals" if _has_overlay_data else ""), height=420))
    st.plotly_chart(fig1, use_container_width=True, key="fig_income_tax_1")

    # ── Explanation table below chart ────────────────────────────────────────
    if _explain and _events_explained:
        st.markdown("**📋 Key events on the chart:**")
        with st.container():
            for _sym2, _title2, _desc2, _ecol in _events_explained:
                st.markdown(
                    f"<div style='margin-left:24px;display:flex;gap:12px;align-items:flex-start;"
                    f"padding:8px 0;border-bottom:1px solid #2a2a4a'>"
                    f"<span style='font-size:16px;color:{_ecol};min-width:24px'>{_sym2}</span>"
                    f"<div><b style='color:#e0e0e0'>{_title2}</b><br>"
                    f"<span style='color:#aaa;font-size:13px'>{_desc2}</span></div></div>",
                    unsafe_allow_html=True
                )

    cl, cr = st.columns(2)
    n_p = 2 if p["partner"] else 1

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=df["Date"],
                          y=(df["Housing Cost"] - df["MRI Benefit"]).clip(lower=0),
                          name="Housing (net of MRI)", marker_color="#e74c3c"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p["hi"]]*len(df),
                          name="Health Insurance (total)", marker_color="#e67e22"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p["cf"]+p["ci"]]*len(df),
                          name="Car", marker_color="#f1c40f"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p["gr"]]*len(df),
                          name="Groceries", marker_color="#2ecc71"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p.get("utilities",0)]*len(df),
                          name="Utilities", marker_color="#1abc9c"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p.get("phone",0)+p.get("subscriptions",0)]*len(df),
                          name="Phone & Subscriptions", marker_color="#3498db"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p.get("gym",0)]*len(df),
                          name="Gym", marker_color="#8e44ad"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p.get("dog",0)]*len(df),
                          name="Dog", marker_color="#d35400"))
    fig2.add_trace(go.Bar(x=df["Date"], y=[p["ot"]]*len(df),
                          name="Other", marker_color="#95a5a6"))
    fig2.add_trace(go.Scatter(x=df["Date"], y=-df["Zorgtoeslag"], mode="lines",
                               name="Zorgtoeslag credit",
                               line=dict(color="#e74c3c", dash="dot", width=2)))
    fig2.update_layout(barmode="stack", **chart_layout("Monthly Expense Breakdown", height=380))
    cl.plotly_chart(fig2, use_container_width=True, key="fig_income_tax_2")

    years  = sorted(df["Year"].unique())
    sg     = p.get("sal_growth", 0.0)
    nm_on  = [net_monthly_calc(p["inc_s"]*(1+sg)**(y-2026), y, True)  +
              (net_monthly_calc(p["inc_p"]*(1+sg)**(y-2026), y, True)  if p["partner"] else 0) for y in years]
    nm_off = [net_monthly_calc(p["inc_s"]*(1+sg)**(y-2026), y, False) +
              (net_monthly_calc(p["inc_p"]*(1+sg)**(y-2026), y, False) if p["partner"] else 0) for y in years]
    fig3 = go.Figure()
    fig3.add_trace(go.Bar(x=years, y=nm_on,  name="With 30% ruling",    marker_color="#2ecc71"))
    fig3.add_trace(go.Bar(x=years, y=nm_off, name="Without 30% ruling", marker_color="#e74c3c", opacity=0.6))
    fig3.update_layout(barmode="group",
                       **chart_layout("30% Ruling: Net Monthly Income by Year", height=380))
    cr.plotly_chart(fig3, use_container_width=True, key="fig_income_tax_3")

    # ── How are these numbers calculated? (bottom of tab) ─────────────────────
    st.divider()
    with st.expander("📖 How are these numbers calculated?", expanded=False):
        # ── Tax breakdown table ───────────────────────────────────────────────
        st.markdown("### 🧮 Tax Breakdown — Ruling On vs Off")
        _pb2 = {"You": p["inc_s"]}
        if p["partner"]: _pb2["Partner"] = p["inc_p"]
        _tbl2 = []
        _rf2 = {"You": p.get("ruling_s", True), "Partner": p.get("ruling_p", False)}
        for _name2, _base_gross2 in _pb2.items():
            _has_r2 = _rf2.get(_name2, False)
            _scens2 = [(2026, _has_r2), (min(2029, 2026 + p.get("n_years", 5) - 1), False)] if _has_r2 else [(2026, False)]
            for _yr2, _a30_2 in _scens2:
                _gross2 = _base_gross2 * (1 + sg) ** (_yr2 - 2026)
                _t2   = income_tax(_gross2, _yr2, _a30_2)
                _ah2  = ahk(_gross2, _yr2); _kk2 = ak(_gross2, _yr2); _z2 = zvw(_gross2, _a30_2)
                _net2 = net_annual_calc(_gross2, _yr2, _a30_2)
                _lbl_r2 = "ruling on" if _a30_2 else "ruling off"
                _tbl2.append({"Person / Year": f"{_name2} {_yr2} ({_lbl_r2})",
                    "Gross": f"€{_gross2:,.0f}", "Income Tax": f"€{_t2:,.0f}",
                    "AHK": f"€{_ah2:,.0f}", "Arbeidskorting": f"€{_kk2:,.0f}",
                    "ZVW": f"€{_z2:,.0f}", "Net Annual": f"€{_net2:,.0f}",
                    "Net Monthly": f"€{_net2/12:,.0f}",
                    "Eff. Rate": f"{(_gross2-_net2)/_gross2*100:.1f}%"})
        st.dataframe(pd.DataFrame(_tbl2), use_container_width=True, hide_index=True)

        # ── 30% ruling expiry detail ───────────────────────────────────────────
        if _table_rows:
            st.markdown("### 📉 30% Ruling Expiry Impact")
            _tbl_md2 = "| Person | Last ruling year | First post-ruling year | Monthly change |\n|---|---|---|---|\n"
            _tbl_md2 += "\n".join(_table_rows)
            st.markdown(_tbl_md2)
            st.caption("💡 During the ruling period, save the difference each month to absorb the income drop on expiry.")

        st.markdown("""
### Dutch Income Tax Components (Box 1)

| Component | Description |
|-----------|-------------|
| **Box 1 income tax** | Progressive tax on earned income. Rate 1 is **36.97%** on the first ~€38,441 (2026), rate 2 is **49.50%** above that threshold. Thresholds are indexed annually. |
| **Algemene heffingskorting (AHK)** | General tax credit of up to **€3,362/yr** (2026), phasing out linearly between ~€24,800 and ~€75,500 gross. Reduces your final tax bill directly. |
| **Arbeidskorting (AK)** | Labour tax credit of up to **€5,052/yr** (2026), phasing out between ~€38,100 and ~€124,900 gross. Rewards working over non-working income. |
| **ZVW** | Income-dependent healthcare contribution of **5.65%** on gross (capped at ~€71,628). Paid on top of your health insurance premium. |
| **30% ruling** | Eligible expats pay tax on only **70% of gross** (or 73% from 2027 starters). Affects Box 1, ZVW, and AHK/AK phase-outs. Duration is 5 years. Rate drops from 30% to 27% from 2027 for 2024–2026 starters. |
| **Hypotheekrenteaftrek (MRI)** | Mortgage interest deductible at **36.97%**. Monthly tax saving = monthly interest × 36.97%. Benefit shrinks as the balance falls. |
| **Zorgtoeslag** | Health insurance subsidy, income-tested. Not applicable when combined gross exceeds ~€45,000 (couples) or ~€37,000 (singles). |
| **Kinderopvangtoeslag** | Childcare benefit for dagopvang (0–4 yrs) and BSO (4–12 yrs). Income-tested, up to 96% of the capped hourly rate. |
| **Box 3 wealth tax** | Annual tax on net assets above €57,000/person. Fictitious return taxed at **36%**. |

### How net monthly income is calculated

```
Gross annual salary
  − Box 1 income tax (after AHK and AK credits)
  − ZVW contribution
= Net annual income
÷ 12
= Net monthly income
```

The **30% ruling** reduces taxable income before Box 1 and ZVW are applied, so the benefit compounds across all three.

### Why do the KPI numbers change each year?

Salary growth, ruling expiry, and annual tax bracket indexation all shift the numbers year by year. KPIs always show the **current calendar month** within the projection.
        """)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUY VS RENT
# ════════════════════════════════════════════════════════════════════════════════

with tabs[2]:
    dw = df_w_a; p = pa; fin = dw.iloc[-1]

    # ── Crossover: find when buying overtakes renting ────────────────────────
    crossover_row = dw[dw["Wealth Delta"] > 0].head(1)
    if not crossover_row.empty:
        cx_date      = crossover_row["Date"].iloc[0]
        buy_date_ts  = pd.Timestamp(year=p["by"], month=p["bm"], day=1)
        months_from_purchase = int((cx_date - buy_date_ts).days / 30.44)
        yrs_from_purchase    = months_from_purchase / 12
        _ha = p.get('ha', 0.03)
        _ha_label = "conservative ✅" if _ha <= 0.04 else "above historic average ⚠️"
        st.success(
            f"🏆 **Buying overtakes renting {yrs_from_purchase:.1f} years after purchase** "
            f"(around **{cx_date.strftime('%B %Y')}**). "
            f"Assuming an annual house appreciation of **{_ha*100:.1f}%** "
            f"(Long-run Dutch average ~2–4%; recent years 5–8% — {_ha_label}).",
            icon="🏠"
        )
    else:
        still_neg = dw["Wealth Delta"].iloc[-1] < 0
        if still_neg:
            st.warning(
                f"⚠️ Within the **{p.get('n_years',5)}-year projection**, buying has **not yet** "
                f"overtaken renting in total wealth. Try extending the timeline or adjusting "
                f"house appreciation / investment return in the Setup tab.",
                icon="📉"
            )
        else:
            st.info("ℹ️ Buying leads renting from the start of the projection.")

    sell_summary = get_sell_summary(dw)

    k1, k2, k3, k4, k5 = st.columns(5)
    kpi(k1, "End Wealth — Buy",  fin["Total Wealth (Buy)"])
    kpi(k2, "End Wealth — Rent", fin["Total Wealth (Rent)"])
    delta = fin["Wealth Delta"]
    k3.metric("Buy vs Rent Edge", f"€{abs(delta):,.0f}",
              delta="Buying wins ✅" if delta > 0 else "Renting wins ✅",
              delta_color="normal" if delta > 0 else "inverse")
    kpi(k4, "Home Equity before sell" if sell_summary else "Home Equity (final)", fin["Home Equity"])
    if sell_summary:
        k5.metric("Sale Net Proceeds", f"€{sell_summary['proceeds']:,.0f}",
                  help=f"Sale price minus mortgage payoff and selling costs on {sell_summary['date'].strftime('%b %Y')}")
    else:
        k5.metric("Projection End", dw["Date"].iloc[-1].strftime("%b %Y"))

    # ── Sell event breakdown panel ────────────────────────────────────────────
    if sell_summary:
        _buy_dt_str  = pd.Timestamp(year=p["by"], month=p["bm"], day=1).strftime("%B %Y")
        _sell_dt_str = sell_summary["date"].strftime("%B %Y")
        sell_years   = (sell_summary["date"] - pd.Timestamp(year=p["by"], month=p["bm"], day=1)).days / 365.25
        _loan_orig       = p["house_price"] * (1 - p["dp"])
        _buying_costs_wf = p["house_price"] * 0.02 + 3500
        _appreciation    = sell_summary["hv"] - p["house_price"]      # defined here for KPIs + waterfall

        st.divider()
        st.markdown(
            f"<div style='margin-bottom:6px'>"  
            f"<span style='font-size:17px;font-weight:700'>🏷️ House Sale Breakdown</span>"  
            f"<span style='color:#aaa;font-size:13px'> — Bought {_buy_dt_str} · Sold {_sell_dt_str} · "
            f"Held {sell_years:.1f} years</span></div>",
            unsafe_allow_html=True
        )

        sc1, sc2, sc3, sc4, sc5, sc6 = st.columns(6)
        sc1.metric("Sale Price", f"€{sell_summary['hv']:,.0f}",
                   help="Appreciated house value at time of sale.")
        sc2.metric("Home Equity", f"€{sell_summary['hv'] - sell_summary['mb']:,.0f}",
                   help="Sale price minus the remaining mortgage balance — the equity you realise on the day of sale.")
        sc3.metric("Appreciation", f"€{_appreciation:,.0f}",
                   help=f"Increase in house value from purchase price €{p['house_price']:,.0f} to sale price €{sell_summary['hv']:,.0f} at {p.get('ha',0.03)*100:.1f}%/yr.")
        sc4.metric("Remaining Mortgage", f"−€{sell_summary['mb']:,.0f}",
                   help="Outstanding mortgage balance repaid to the bank at settlement.")
        sc5.metric("Selling Costs", f"−€{sell_summary['costs']:,.0f}",
                   help="~1.5% estate agent fee plus €2,500 fixed costs.")
        sc6.metric("Net Proceeds to You", f"€{sell_summary['proceeds'] - _buying_costs_wf:,.0f}",
                   help="Sale price minus remaining mortgage, selling costs and original buying costs.")

        # Waterfall: Purchase Price → −Buying Costs → +Appreciation → −Remaining Mortgage → −Selling Costs → Net Proceeds
        _purchase_price  = p["house_price"]
        _appreciation    = sell_summary["hv"] - _purchase_price
        fig_sell = go.Figure(go.Waterfall(
            orientation="v",
            measure=["absolute", "relative", "relative", "relative", "relative", "total"],
            x=["Purchase Price", "Buying Costs", "Appreciation",
               "Remaining Mortgage", "Selling Costs", "Net Proceeds"],
            y=[_purchase_price, -_buying_costs_wf,
               _appreciation, -sell_summary["mb"], -sell_summary["costs"], 0],
            text=[
                f"€{_purchase_price:,.0f}",
                f"−€{_buying_costs_wf:,.0f}",
                f"+€{_appreciation:,.0f}",
                f"−€{sell_summary['mb']:,.0f}",
                f"−€{sell_summary['costs']:,.0f}",
                f"€{sell_summary['proceeds'] - _buying_costs_wf:,.0f}",
            ],
            textposition="outside",
            connector=dict(line=dict(color="rgba(255,255,255,0.3)")),
            increasing=dict(marker_color="#2ecc71"),
            decreasing=dict(marker_color="#e74c3c"),
            totals=dict(marker_color="#3498db"),
        ))
        fig_sell.update_layout(**chart_layout(
            f"House Sale Waterfall — Buy {_buy_dt_str} · Sell {_sell_dt_str}",
            yaxis_title="€", height=440))
        st.plotly_chart(fig_sell, use_container_width=True, key="fig_sell_waterfall")

    with st.expander("ℹ️ What does this tab show & how is wealth calculated?", expanded=False):
        _buying_costs_exp = pa["house_price"] * 0.02 + 3500
        _end_buy  = dw["Total Wealth (Buy)"].iloc[-1]
        _end_rent = dw["Total Wealth (Rent)"].iloc[-1]
        _delta    = _end_buy - _end_rent
        _cx_row   = dw[dw["Wealth Delta"] > 0].head(1)
        _cx_str   = _cx_row["Date"].iloc[0].strftime("%B %Y") if not _cx_row.empty else "beyond the projection window"
        _cx_yrs   = ((_cx_row["Date"].iloc[0] - dw["Date"].iloc[0]).days / 365.25) if not _cx_row.empty else None
        _avg_sav  = df_m_a["Net Saving"].mean()
        _ann_net1 = mort_payment(pa["house_price"], pa["dp"], pa["mort_rate"]) - \
                    amortisation_schedule(pa["house_price"], pa["dp"], pa["mort_rate"])["MRI_Benefit"].iloc[0]
        st.markdown(f"""
### 🏠 What does this tab show?

This tab compares **total net worth** over time for two scenarios using your Scenario A inputs:
- **Buying** the house you configured in Setup
- **Renting** indefinitely and investing the difference

---

### 💰 Benefit of Buying vs Renting — Your Numbers

| Metric | Value |
|--------|-------|
| **End wealth (Buy)** | €{_end_buy:,.0f} |
| **End wealth (Rent)** | €{_end_rent:,.0f} |
| **Buy advantage at end of projection** | {"**+€" + f"{_delta:,.0f}** ✅ Buying wins" if _delta > 0 else "**−€" + f"{abs(_delta):,.0f}** — Renting wins at this horizon"} |
| **Buying overtakes renting** | {f"After **{_cx_yrs:.1f} years** ({_cx_str})" if _cx_yrs else "Not within projection window"} |
| **Net mortgage payment / mo** | €{_ann_net1:,.0f} (after MRI tax benefit) |
| **Your average monthly saving** | €{_avg_sav:,.0f} |
| **One-off buying costs** | €{_buying_costs_exp:,.0f} (2% overdrachtsbelasting + €3,500 notaris) |

---

### 📐 How is wealth calculated?

**Buy scenario:** On the purchase date, the down payment (€{pa['house_price']*pa['dp']:,.0f}) converts directly into home equity — wealth is unchanged by the down payment itself. Buying costs (~€{_buying_costs_exp:,.0f}) are a pure loss — this causes the visible dip at the 🏠 marker. After purchase, equity builds each month through principal repayment and house appreciation.

**Rent scenario:** Full savings invested from day 1 at the investment return rate. Rent is paid throughout. Monthly surplus (income minus expenses) also invested. No home equity ever accrues.

**Box 3 tax:** Both scenarios pay the fictitious return tax annually on net assets above €57,000/person — this reduces the compounding advantage of large cash positions.

If a **sell date** is set, net proceeds (sale price minus mortgage payoff and ~1.5% + €2,500 selling costs) are added to the buy scenario cash on that date.
        """)

    st.divider()

    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Total Wealth (Buy)"],
                              name="Wealth (Buy) ★", line=dict(color="#2ecc71", width=4)))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Total Wealth (Rent)"],
                              name="Wealth (Rent)", line=dict(color="#e74c3c", width=3)))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Home Equity"],
                              name="Equity", line=dict(color="#f1c40f", width=2, dash="dot")))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Cash (Buy)"],
                              name="Cash", line=dict(color="#3498db", width=1.5, dash="dash")))
    add_events(fig5, p)
    if not crossover_row.empty:
        cx_str = cx_date.strftime("%Y-%m-%d")
        fig5.add_shape(type="line", x0=cx_str, x1=cx_str, y0=0, y1=1,
                       xref="x", yref="paper",
                       line=dict(dash="dot", color="#f1c40f", width=2))
        # Buy leads date shown in hover tooltip via vertical line
    if sell_summary:
        sell_str = sell_summary["date"].strftime("%Y-%m-%d")
        fig5.add_shape(type="line", x0=sell_str, x1=sell_str, y0=0, y1=1,
                       xref="x", yref="paper", line=dict(dash="dot", color="#e74c3c", width=2))
        # Sell date shown via vertical line; details in caption below
    if sell_summary:
        st.caption("💡 At the sell date, **Home Equity converts to Cash** — the ★ Total Wealth (Buy) line remains continuous (it only drops by selling costs ~€{:,.0f}). The visible Cash spike is equity being liquidated, not new wealth being created.".format(
            int(sell_summary["costs"])))
    fig5.update_layout(**chart_layout("Total Net Worth: Buy vs Rent (★ = true total)", height=440))
    st.plotly_chart(fig5, use_container_width=True, key="fig_bvr_5")

    cl, cr = st.columns(2)

    dv = dw["Wealth Delta"]
    fig6 = go.Figure()
    fig6.add_trace(go.Scatter(x=dw["Date"], y=dv.clip(lower=0),
                              fill="tozeroy", fillcolor="rgba(46,204,113,0.20)",
                              line=dict(color="#2ecc71", width=1), name="Buy ▲"))
    fig6.add_trace(go.Scatter(x=dw["Date"], y=dv.clip(upper=0),
                              fill="tozeroy", fillcolor="rgba(231,76,60,0.20)",
                              line=dict(color="#e74c3c", width=1), name="Rent ▲"))
    fig6.add_trace(go.Scatter(x=dw["Date"], y=dv,
                              line=dict(color="white", width=1.5), name="Delta", showlegend=False))
    fig6.add_hline(y=0, line_color="gray", line_dash="dot")
    fig6.update_layout(**chart_layout("Wealth Gap (Buy − Rent)", height=360))
    cl.plotly_chart(fig6, use_container_width=True, key="fig_bvr_6")

    daw = dw.groupby("Year").last().reset_index()
    fig7 = go.Figure()
    fig7.add_trace(go.Bar(x=daw["Year"], y=daw["Home Equity"],
                          name="Equity", marker_color="#f1c40f"))
    fig7.add_trace(go.Bar(x=daw["Year"], y=daw["Cash (Buy)"].clip(lower=0),
                          name="Cash Savings", marker_color="#2ecc71"))
    fig7.add_trace(go.Scatter(x=daw["Year"], y=daw["Total Wealth (Rent)"],
                              name="Rent Total", mode="lines+markers",
                              line=dict(color="#e74c3c", width=2, dash="dot")))
    fig7.update_layout(barmode="stack",
                       **chart_layout("Year-End Wealth: Buy vs Rent", height=360))
    cr.plotly_chart(fig7, use_container_width=True, key="fig_bvr_7")

    fig8 = go.Figure()
    fig8.add_trace(go.Scatter(x=dw["Date"], y=dw["Cashflow (Buy)"], name="Cashflow (Buy)",
                              line=dict(color="#2ecc71", width=2),
                              fill="tozeroy", fillcolor="rgba(46,204,113,0.08)"))
    fig8.add_trace(go.Scatter(x=dw["Date"], y=dw["Cashflow (Rent)"], name="Cashflow (Rent)",
                              line=dict(color="#e74c3c", width=2),
                              fill="tozeroy", fillcolor="rgba(231,76,60,0.08)"))
    fig8.add_hline(y=0, line_color="gray", line_dash="dot")
    add_events(fig8, p)
    fig8.update_layout(**chart_layout("Monthly Free Cashflow: Buy vs Rent", height=360))
    st.plotly_chart(fig8, use_container_width=True, key="fig_bvr_8")

    st.subheader("📊 Year-End Wealth Summary")
    tbl = []
    for _, r in daw.iterrows():
        tbl.append({"Year": int(r["Year"]),
                    "House Value":         f"€{r['House Value']:,.0f}",
                    "Mortgage Balance":    f"€{r['Mortgage Balance']:,.0f}",
                    "Home Equity":         f"€{r['Home Equity']:,.0f}",
                    "Cash (Buy)":          f"€{r['Cash (Buy)']:,.0f}",
                    "Total Wealth (Buy)":  f"€{r['Total Wealth (Buy)']:,.0f}",
                    "Total Wealth (Rent)": f"€{r['Total Wealth (Rent)']:,.0f}",
                    "Buy Advantage":       f"€{r['Total Wealth (Buy)']-r['Total Wealth (Rent)']:,.0f}"})
    st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

    # ── Q4: Minimum hold period to not lose money on selling ─────────────────
    st.divider()
    st.subheader("⏱️ How Long Do You Need to Hold to Not Lose Money?")

    # For each month after purchase, compute: if you sold that month,
    # would your total wealth (buy) beat what you'd have had just renting?
    # Also: would net proceeds from sale cover at least your buying costs?
    _buy_ts   = pd.Timestamp(year=p["by"], month=p["bm"], day=1)
    _owned    = dw[dw["Date"] >= _buy_ts].copy()
    _owned    = _owned.reset_index(drop=True)

    # Buying costs paid upfront
    _buying_costs = p["house_price"] * 0.02 + 3500   # overdrachtsbelasting + notaris

    # For each month: simulate selling at that point
    _breakeven_rows = []
    for i, row in _owned.iterrows():
        _hv       = row["House Value"]
        _mb       = row["Mortgage Balance"]
        if _hv == 0:
            continue
        _sell_c   = _hv * 0.015 + 2500          # selling costs
        _proceeds = _hv - _mb - _sell_c         # net cash from sale
        _equity   = row["Home Equity"]
        _net_gain = _proceeds - (p["house_price"] * p["dp"])   # gain vs down payment
        _total_costs = _buying_costs + _sell_c                  # all transaction costs
        # Did house value appreciation cover ALL transaction costs?
        _cost_covered = (_hv - p["house_price"]) >= _total_costs
        _breakeven_rows.append({
            "Date":            row["Date"],
            "House Value":     round(_hv),
            "Mortgage Balance":round(_mb),
            "Selling Costs":   round(_sell_c),
            "Net Proceeds":    round(_proceeds),
            "Home Equity":     round(_equity),
            "Transaction Costs Covered": _cost_covered,
            "Appreciation":    round(_hv - p["house_price"]),
            "Total Tx Costs":  round(_total_costs),
        })

    _be_df = pd.DataFrame(_breakeven_rows)

    # Find first month where appreciation >= total transaction costs
    _breakeven_row = _be_df[_be_df["Transaction Costs Covered"]].head(1)
    # Find first month where wealth (buy) > wealth (rent)
    _wealth_xover = dw[dw["Wealth Delta"] > 0].head(1)

    if not _breakeven_row.empty:
        _be_date   = _breakeven_row["Date"].iloc[0]
        _be_months = int((_be_date - _buy_ts).days / 30.44)
        _be_years  = _be_months / 12
        _be_appr   = _breakeven_row["Appreciation"].iloc[0]
        _be_costs  = _breakeven_row["Total Tx Costs"].iloc[0]
        st.success(
            f"📆 **You need to hold for at least {_be_years:.1f} years** (≈{_be_months} months after purchase, "
            f"around **{_be_date.strftime('%B %Y')}**) before house appreciation covers all "
            f"transaction costs (buying + selling: €{_be_costs:,.0f}). "
            f"Before that point, selling at a loss on transaction costs is likely.",
            icon="🔑"
        )
    else:
        st.warning(
            "⚠️ Within the projection window, house appreciation does not fully cover all transaction "
            "costs (buying + selling). Try increasing house appreciation or extending the projection.",
            icon="📉"
        )

    with st.expander("📐 How is the minimum hold period calculated?", expanded=False):
        st.markdown(f"""
**The question:** If I sell at month X, do I come out ahead of having never bought?

**Transaction costs you pay regardless of when you sell:**
- **Buying costs (one-off):** 2% overdrachtsbelasting + ~€3,500 notaris = **€{_buying_costs:,.0f}**
- **Selling costs (when you sell):** ~1.5% makelaar fee + €2,500 fixed = varies by house value

**Breakeven logic:** Your house must appreciate enough that:
> House value growth ≥ Buying costs + Selling costs

**Example at purchase:**
- Buy at €{p["house_price"]:,.0f}, costs to buy: €{_buying_costs:,.0f}
- Sell immediately: costs ~€{p["house_price"]*0.015+2500:,.0f}
- Total transaction costs to cover: **€{_buying_costs + p["house_price"]*0.015+2500:,.0f}**
- At {p["ha"]*100:.1f}%/yr appreciation, this takes roughly {(_buying_costs + p["house_price"]*0.015+2500)/(p["house_price"]*p["ha"]):.1f} years to recover

Note: this is separate from the **wealth crossover** (when buying beats renting in total net worth),
which also accounts for invested savings, mortgage cashflow, and Box 3 tax.
        """)

    if not _be_df.empty:
        # Chart: appreciation vs total transaction costs over time
        fig_be = go.Figure()
        fig_be.add_trace(go.Scatter(
            x=_be_df["Date"], y=_be_df["Appreciation"],
            name="House Value",
            line=dict(color="#2ecc71", width=2.5),
            fill="tozeroy", fillcolor="rgba(46,204,113,0.08)"
        ))
        fig_be.add_trace(go.Scatter(
            x=_be_df["Date"], y=_be_df["Total Tx Costs"],
            name="Transaction Costs",
            line=dict(color="#e74c3c", width=2, dash="dash")
        ))
        if not _breakeven_row.empty:
            _be_str = _be_date.strftime("%Y-%m-%d")
            fig_be.add_shape(type="line", x0=_be_str, x1=_be_str, y0=0, y1=1,
                             xref="x", yref="paper",
                             line=dict(color="#f1c40f", dash="dot", width=2))
            # Breakeven date marked by vertical line; readable in hover
        fig_be.update_layout(**chart_layout(
            "House Appreciation vs Total Transaction Costs — Breakeven Hold Period",
            yaxis_title="€", height=380))
        st.plotly_chart(fig_be, use_container_width=True, key="fig_bvr_be")

    # ── How are these numbers calculated? (bottom of tab) ─────────────────────
    st.divider()
    with st.expander("📖 How are these numbers calculated?", expanded=False):
        _bc = pa["house_price"] * 0.02 + 3500
        st.markdown(f"""
### Buy vs Rent Wealth Model

**Total Wealth (Buy)** = Cash savings + Home equity
**Total Wealth (Rent)** = Cash savings only (invested throughout)

#### Buy scenario — month by month
1. **At purchase:** Down payment (€{pa['house_price']*pa['dp']:,.0f}) leaves your cash and becomes home equity. Buying costs (2% overdrachtsbelasting + €3,500 notaris ≈ **€{_bc:,.0f}**) are a one-off loss — this causes the visible dip on the chart.
2. **Each month:** Mortgage payment splits into interest and principal. Principal repayment increases home equity. Interest is partially recovered via hypotheekrenteaftrek (36.97% of interest paid back as tax).
3. **House appreciation:** Applied annually at your Setup rate to the house value, increasing equity each year.
4. **Monthly surplus** (income − all expenses) is added to your cash savings and compounds at the investment return rate.

#### Rent scenario — month by month
1. Your starting savings are invested immediately and compound at the investment return rate.
2. Rent is paid each month. The difference between rent and what the mortgage would have cost (positive or negative) is added or subtracted from invested savings.
3. No buying or selling costs ever apply.

#### Box 3 wealth tax
Both scenarios pay Box 3 annually on net assets above **€57,000/person**. The fictitious return rate on savings is ~1.54%; the tax rate is 36%. This reduces the compounding effect of large cash positions.

#### Wealth crossover
The "Buy leads" date is when **Total Wealth (Buy) > Total Wealth (Rent)**. This typically takes several years because buying costs and higher monthly outgoings early on suppress the buy scenario before appreciation and principal repayment tip the balance.

#### Minimum hold period
The breakeven hold calculation asks: has house appreciation covered **all transaction costs** (buying + selling)?
- Buying costs: **€{_bc:,.0f}** (one-off at purchase)
- Selling costs: ~1.5% makelaar + €2,500 fixed (paid at sale)
- Hold until: house value growth ≥ buying costs + selling costs
        """)

# ════════════════════════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════════════════════════
# TAB 3 — MORTGAGE: ANNUITY vs LINEAR
# ════════════════════════════════════════════════════════════════════════════════

with tabs[3]:
    # ── Pro gate with gold lock header ───────────────────────────────────
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px'>"
        "<span style='font-size:22px;font-weight:700'>🏦 Mortgage Analysis</span>"
        + ("" if IS_PAID else
        "<span style='background:linear-gradient(135deg,#d97706,#f59e0b);"
        "color:#000;font-weight:700;font-size:11px;padding:3px 10px;"
        "border-radius:20px;letter-spacing:0.3px'>🔒 PRO</span>")
        + "</div>",
        unsafe_allow_html=True
    )
    if not IS_PAID:
        # ── Greyed example charts ─────────────────────────────────────────
        st.caption("Upgrade to Pro to unlock full mortgage analysis — annuity vs linear, MRI tax benefit, balance chart and 30-year cost comparison.")
        _mort_demo_ann = amortisation_schedule(400000, 0.10, 0.040, "Annuity (annuïteit)", 30)
        _mort_demo_lin = amortisation_schedule(400000, 0.10, 0.040, "Linear (lineair)", 30)
        _mort_demo_proj = _mort_demo_ann.head(60)
        _mort_demo_lin_proj = _mort_demo_lin.head(60)
        st.markdown(
            "<div style='opacity:0.25;pointer-events:none;filter:blur(2px);"
            "border-radius:8px;overflow:hidden;margin-bottom:4px'>",
            unsafe_allow_html=True
        )
        _fig_demo1 = go.Figure()
        _fig_demo1.add_trace(go.Scatter(x=_mort_demo_proj["Date"], y=_mort_demo_proj["Payment"],
            name="Annuity Gross", line=dict(color="#3498db", width=2)))
        _fig_demo1.add_trace(go.Scatter(x=_mort_demo_proj["Date"], y=_mort_demo_proj["Net_Payment"],
            name="Annuity Net", line=dict(color="#2ecc71", width=2)))
        _fig_demo1.add_trace(go.Scatter(x=_mort_demo_lin_proj["Date"], y=_mort_demo_lin_proj["Payment"],
            name="Linear Gross", line=dict(color="#e67e22", width=2, dash="dash")))
        _fig_demo1.update_layout(**chart_layout("Monthly Mortgage Payment: Gross vs Net", height=320))
        st.plotly_chart(_fig_demo1, use_container_width=True, key="fig_mort_demo1")
        _dmc1, _dmc2 = st.columns(2)
        _fig_demo2 = go.Figure()
        _fig_demo2.add_trace(go.Scatter(x=_mort_demo_proj["Date"], y=_mort_demo_proj["MRI_Benefit"],
            name="MRI Benefit", fill="tozeroy", fillcolor="rgba(52,152,219,0.15)",
            line=dict(color="#3498db", width=2)))
        _fig_demo2.update_layout(**chart_layout("Monthly Tax Benefit (MRI)", height=280))
        _dmc1.plotly_chart(_fig_demo2, use_container_width=True, key="fig_mort_demo2")
        _fig_demo3 = go.Figure()
        _fig_demo3.add_trace(go.Scatter(x=_mort_demo_ann["Date"], y=_mort_demo_ann["Balance"],
            name="Balance Annuity", line=dict(color="#3498db", width=2)))
        _fig_demo3.add_trace(go.Scatter(x=_mort_demo_lin["Date"], y=_mort_demo_lin["Balance"],
            name="Balance Linear", line=dict(color="#e67e22", width=2, dash="dash")))
        _fig_demo3.update_layout(**chart_layout("Outstanding Mortgage Balance (30yr)", height=280))
        _dmc2.plotly_chart(_fig_demo3, use_container_width=True, key="fig_mort_demo3")
        st.markdown("</div>", unsafe_allow_html=True)
        _paid_gate("Full Mortgage Analysis", icon="🏦")
    else:
        p = pa

        loan_amount = p["house_price"] * (1 - p["dp"])
        mort_yrs    = 30

        df_ann = amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"],
                                       "Annuity (annuïteit)", mort_yrs)
        df_lin = amortisation_schedule(p["house_price"], p["dp"], p["mort_rate"],
                                       "Linear (lineair)", mort_yrs)

        # ── Plain-language summary (Q2 + Q3) ─────────────────────────────────────
        ann_mri_mo1 = df_ann["MRI_Benefit"].iloc[0]
        lin_mri_mo1 = df_lin["MRI_Benefit"].iloc[0]
        ann_net_mo1 = df_ann["Net_Payment"].iloc[0]
        lin_net_mo1 = df_lin["Net_Payment"].iloc[0]
        _chosen_is_linear = "Linear" in p.get("mort_type", "Annuity")
        _chosen_gross = df_lin["Payment"].iloc[0] if _chosen_is_linear else df_ann["Payment"].iloc[0]
        _chosen_mri   = lin_mri_mo1 if _chosen_is_linear else ann_mri_mo1
        _chosen_net   = lin_net_mo1 if _chosen_is_linear else ann_net_mo1
        _chosen_label = "Linear" if _chosen_is_linear else "Annuity"

        st.info(
            f"🏠 Based on your Setup inputs, your **{_chosen_label} mortgage** payment is "
            f"**€{_chosen_gross:,.0f} gross/month** in month 1. "
            f"The hypotheekrenteaftrek (mortgage interest tax deduction) gives you back "
            f"**€{_chosen_mri:,.0f}/month** in tax savings, making your **effective net payment "
            f"€{_chosen_net:,.0f}/month**. "
            f"This tax benefit gradually decreases as your mortgage balance falls over time.",
            icon="💰"
        )
        with st.expander("📐 How is the tax benefit calculated?", expanded=False):
            _int_mo1 = df_ann["Interest"].iloc[0] if not _chosen_is_linear else df_lin["Interest"].iloc[0]
            st.markdown(f"""
    **Hypotheekrenteaftrek (MRI)** — mortgage interest deduction in Box 1:

    1. Each month you pay interest on the outstanding mortgage balance
    2. That interest amount is deductible from your taxable income at **36.97%** (2026 rate)
    3. The tax saving = monthly interest × 36.97%

    **Month 1 example ({_chosen_label}):**
    - Monthly interest paid: €{_int_mo1:,.0f}
    - Tax saving: €{_int_mo1:,.0f} × 36.97% = **€{_chosen_mri:,.0f}**
    - Gross mortgage payment: €{_chosen_gross:,.0f}
    - **Net effective payment: €{_chosen_gross:,.0f} − €{_chosen_mri:,.0f} = €{_chosen_net:,.0f}**

    The benefit is highest in early years when interest is large, and shrinks as you repay principal.
    For an annuity, the gross payment stays constant but the net payment rises over time as MRI falls.
    For a linear mortgage, both gross and net payments fall steadily.
            """)

        # ── KPI row ──────────────────────────────────────────────────────────────
        # Month-1 tax benefits (already computed above)

        k1, k2, k3, k4, k5, k6, k7, k8 = st.columns(8)
        k1.metric("Loan Amount",               f"€{loan_amount:,.0f}")
        k2.metric("Annuity — Gross/mo",        f"€{df_ann['Payment'].iloc[0]:,.0f}")
        k3.metric("Annuity — MRI Benefit/mo",  f"€{ann_mri_mo1:,.0f}",
                  help="Monthly tax saving on interest in month 1 (36.97% of interest paid)")
        k4.metric("Annuity — Net/mo",          f"€{ann_net_mo1:,.0f}",
                  help="Gross payment minus monthly MRI tax benefit")
        k5.metric("Linear — Gross/mo (mo 1)",  f"€{df_lin['Payment'].iloc[0]:,.0f}")
        k6.metric("Linear — MRI Benefit/mo",   f"€{lin_mri_mo1:,.0f}",
                  help="Monthly tax saving on interest in month 1 (36.97% of interest paid)")
        k7.metric("Linear — Net/mo (mo 1)",    f"€{lin_net_mo1:,.0f}",
                  help="Gross payment minus monthly MRI tax benefit")
        k8.metric("Linear — Net/mo (mo 360)",  f"€{df_lin['Net_Payment'].iloc[-1]:,.0f}",
                  help="Net payment in final month — interest is near zero so MRI benefit is minimal")

        st.divider()



        n_proj      = p.get("n_years", 5) * 12
        df_ann_proj = df_ann.head(n_proj)
        df_lin_proj = df_lin.head(n_proj)

        # ── Chart 1: Monthly payment gross vs net ───────────────────────────────
        fig_m1 = go.Figure()
        fig_m1.add_trace(go.Scatter(x=df_ann_proj["Date"], y=df_ann_proj["Payment"],
                                    name="Annuity Gross", line=dict(color="#3498db", width=2)))
        fig_m1.add_trace(go.Scatter(x=df_ann_proj["Date"], y=df_ann_proj["Net_Payment"],
                                    name="Annuity Net", line=dict(color="#2ecc71", width=2)))
        fig_m1.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["Payment"],
                                    name="Linear Gross", line=dict(color="#e67e22", width=2, dash="dash")))
        fig_m1.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["Net_Payment"],
                                    name="Linear Net", line=dict(color="#f1c40f", width=2, dash="dash")))
        fig_m1.update_layout(**chart_layout(
            "Monthly Mortgage Payment: Gross vs Net (after Hypotheekrenteaftrek)", height=420))
        st.plotly_chart(fig_m1, use_container_width=True, key="fig_mort_1")

        cl, cr = st.columns(2)

        # ── Chart 2: Monthly MRI tax benefit ────────────────────────────────────
        fig_m2 = go.Figure()
        fig_m2.add_trace(go.Scatter(x=df_ann_proj["Date"], y=df_ann_proj["MRI_Benefit"],
                                    name="MRI (Annuity)",
                                    fill="tozeroy", fillcolor="rgba(52,152,219,0.15)",
                                    line=dict(color="#3498db", width=2)))
        fig_m2.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["MRI_Benefit"],
                                    name="MRI (Linear)",
                                    fill="tozeroy", fillcolor="rgba(230,126,34,0.15)",
                                    line=dict(color="#e67e22", width=2, dash="dash")))
        fig_m2.update_layout(**chart_layout(
            "Monthly Tax Benefit (Hypotheekrenteaftrek @ 36.97%)", height=360))
        cl.plotly_chart(fig_m2, use_container_width=True, key="fig_mort_2")

        # ── Chart 3: Interest vs Principal (annuity) ────────────────────────────
        fig_m3 = go.Figure()
        fig_m3.add_trace(go.Bar(x=df_ann_proj["Date"], y=df_ann_proj["Interest"],
                                name="Interest (Annuity)", marker_color="#e74c3c"))
        fig_m3.add_trace(go.Bar(x=df_ann_proj["Date"], y=df_ann_proj["Principal"],
                                name="Principal (Annuity)", marker_color="#3498db"))
        fig_m3.update_layout(barmode="stack",
                             **chart_layout("Annuity: Interest vs Principal Split", height=360))
        cr.plotly_chart(fig_m3, use_container_width=True, key="fig_mort_3")

        cl2, cr2 = st.columns(2)

        # ── Chart 4: Mortgage balance full term ─────────────────────────────────
        fig_m4 = go.Figure()
        fig_m4.add_trace(go.Scatter(x=df_ann["Date"], y=df_ann["Balance"],
                                    name="Balance Annuity", line=dict(color="#3498db", width=2)))
        fig_m4.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["Balance"],
                                    name="Balance Linear", line=dict(color="#e67e22", width=2, dash="dash")))
        proj_end = df_ann_proj["Date"].iloc[-1].strftime("%Y-%m-%d")
        fig_m4.add_shape(type="rect",
                         x0=df_ann["Date"].iloc[0].strftime("%Y-%m-%d"), x1=proj_end,
                         y0=0, y1=loan_amount, xref="x", yref="y",
                         fillcolor="rgba(255,255,255,0.03)", line_width=0)
        if not st.session_state.get("narrow_mode"):
            fig_m4.add_annotation(x=proj_end, y=loan_amount * 0.95, xref="x", yref="y",
                                   text="← projection window", showarrow=False,
                                   xanchor="right", font=dict(color="#aaa", size=10))
        fig_m4.update_layout(**chart_layout(
            "Outstanding Mortgage Balance (30yr full term)", height=360))
        cl2.plotly_chart(fig_m4, use_container_width=True, key="fig_mort_4")

        # ── Chart 5: Cumulative MRI vs interest ─────────────────────────────────
        fig_m5 = go.Figure()
        fig_m5.add_trace(go.Scatter(x=df_ann["Date"], y=df_ann["MRI_Benefit"].cumsum(),
                                    name="Cumul. MRI Ann.", line=dict(color="#2ecc71", width=2)))
        fig_m5.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["MRI_Benefit"].cumsum(),
                                    name="Cumul. MRI Lin.",
                                    line=dict(color="#f1c40f", width=2, dash="dash")))
        fig_m5.add_trace(go.Scatter(x=df_ann["Date"], y=df_ann["Interest"].cumsum(),
                                    name="Cumul. Int. Ann.",
                                    line=dict(color="#e74c3c", width=1.5, dash="dot")))
        fig_m5.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["Interest"].cumsum(),
                                    name="Cumul. Int. Lin.",
                                    line=dict(color="#e67e22", width=1.5, dash="dot")))
        fig_m5.update_layout(**chart_layout(
            "Cumulative Interest Paid vs MRI Tax Benefit (30yr)", height=360))
        cr2.plotly_chart(fig_m5, use_container_width=True, key="fig_mort_5")

        # ── Year-end summary table ────────────────────────────────────────────────
        with st.expander("📊 Year-End Mortgage Summary (Annuity vs Linear)", expanded=False):
            df_ann_yr = df_ann.groupby("Year").agg(
                Ann_Pay=("Payment","sum"), Ann_Int=("Interest","sum"),
                Ann_Prin=("Principal","sum"), Ann_MRI=("MRI_Benefit","sum"),
                Ann_Bal=("Balance","last")).reset_index()
            df_lin_yr = df_lin.groupby("Year").agg(
                Lin_Pay=("Payment","sum"), Lin_Int=("Interest","sum"),
                Lin_Prin=("Principal","sum"), Lin_MRI=("MRI_Benefit","sum"),
                Lin_Bal=("Balance","last")).reset_index()
            df_yr = df_ann_yr.merge(df_lin_yr, on="Year")
            tbl_m = []
            for _, r in df_yr.iterrows():
                tbl_m.append({
                    "Year": int(r["Year"]),
                    "Ann. Payment/yr":     f"EUR {r['Ann_Pay']:,.0f}",
                    "Ann. Interest/yr":    f"EUR {r['Ann_Int']:,.0f}",
                    "Ann. MRI Benefit/yr": f"EUR {r['Ann_MRI']:,.0f}",
                    "Ann. Balance (EOY)":  f"EUR {r['Ann_Bal']:,.0f}",
                    "Lin. Payment/yr":     f"EUR {r['Lin_Pay']:,.0f}",
                    "Lin. Interest/yr":    f"EUR {r['Lin_Int']:,.0f}",
                    "Lin. MRI Benefit/yr": f"EUR {r['Lin_MRI']:,.0f}",
                    "Lin. Balance (EOY)":  f"EUR {r['Lin_Bal']:,.0f}",
                })
            st.dataframe(pd.DataFrame(tbl_m), use_container_width=True, hide_index=True)

        # ── 30-year total cost comparison ────────────────────────────────────────
        st.divider()
        with st.expander("💡 30-Year Total Cost Comparison", expanded=False):
            ann_net = df_ann["Payment"].sum() - df_ann["MRI_Benefit"].sum()
            lin_net = df_lin["Payment"].sum() - df_lin["MRI_Benefit"].sum()
            saving  = ann_net - lin_net
            tc1, tc2, tc3 = st.columns(3)
            tc1.metric("Annuity - Net Total Cost", f"EUR {ann_net:,.0f}",
                       help="Total payments minus 30yr MRI tax benefit")
            tc2.metric("Linear - Net Total Cost",  f"EUR {lin_net:,.0f}",
                       help="Total payments minus 30yr MRI tax benefit")
            tc3.metric("Saving with Linear", f"EUR {saving:,.0f}",
                       delta="Linear cheaper" if saving > 0 else "Annuity cheaper",
                       delta_color="normal" if saving > 0 else "inverse")

        # ── House Price Sensitivity ────────────────────────────────────────────────────────────────────────────
        st.divider()
        st.subheader("🏷️ Monthly Payment vs House Price")
        st.caption(
            "See how your gross monthly repayment and MRI tax benefit change across a range of house prices, "
            "using your current down payment % and mortgage rate from Setup."
        )

        _sens_col1, _sens_col2, _sens_col3 = st.columns(3)
        _price_min = int(_sens_col1.number_input(
            "Price range — from (€)", value=int(max(100_000, p["house_price"] - 300_000)),
            step=25_000, key="sens_min",
            help="Lowest house price to show on the chart."))
        _price_max = int(_sens_col2.number_input(
            "Price range — to (€)", value=int(p["house_price"] + 300_000),
            step=25_000, key="sens_max",
            help="Highest house price to show on the chart."))
        _price_step = int(_sens_col3.selectbox(
            "Step size (€)", [10_000, 25_000, 50_000, 100_000], index=1, key="sens_step",
            help="Interval between price points on the x-axis."))

        if _price_min >= _price_max:
            st.warning("Price range 'from' must be less than 'to'.")
        else:
            _prices = list(range(_price_min, _price_max + _price_step, _price_step))
            _dp     = p["dp"]
            _rate   = p["mort_rate"]
            _is_lin = "Linear" in p.get("mort_type", "Annuity")

            _gross_pay, _mri_ben, _net_pay = [], [], []
            for _hp in _prices:
                _loan = _hp * (1 - _dp)
                _int_mo1 = _loan * (_rate / 12)
                if _is_lin:
                    _g = (_loan / (30 * 12)) + _int_mo1
                else:
                    _g = mort_payment(_hp, _dp, _rate)
                _m = _int_mo1 * MRI_RATE
                _gross_pay.append(round(_g))
                _mri_ben.append(round(_m))
                _net_pay.append(round(_g - _m))

            _price_labels = [f"€{p_//1000:.0f}k" for p_ in _prices]
            _cur_idx = min(range(len(_prices)), key=lambda i: abs(_prices[i] - p["house_price"]))

            _fig_sens = go.Figure()
            # MRI benefit as bottom stack (yellow)
            _fig_sens.add_trace(go.Bar(
                x=_price_labels, y=_mri_ben,
                name="MRI Tax Benefit",
                marker_color="rgba(241,196,15,0.80)",
                hovertemplate="€%{y:,.0f}/mo<extra>MRI benefit</extra>",
            ))
            # Net payment stacked on top (blue)
            _fig_sens.add_trace(go.Bar(
                x=_price_labels, y=[g - m for g, m in zip(_gross_pay, _mri_ben)],
                name="Net Payment (after MRI)",
                marker_color="rgba(52,152,219,0.80)",
                hovertemplate="€%{y:,.0f}/mo<extra>Net payment</extra>",
            ))
            # Gross repayment line (red)
            _fig_sens.add_trace(go.Scatter(
                x=_price_labels, y=_gross_pay,
                name="Gross Monthly Payment",
                mode="lines+markers",
                line=dict(color="#e74c3c", width=2.5),
                marker=dict(size=5),
                hovertemplate="€%{y:,.0f}/mo<extra>Gross payment</extra>",
            ))
            # Vertical marker for current house price
            _fig_sens.add_shape(type="line",
                x0=_price_labels[_cur_idx], x1=_price_labels[_cur_idx],
                y0=0, y1=1, xref="x", yref="paper",
                line=dict(color="#2ecc71", width=2, dash="dash"))
            if not st.session_state.get("narrow_mode"):
                _fig_sens.add_annotation(
                    x=_price_labels[_cur_idx], y=0.96, xref="x", yref="paper",
                    text=f"Your price<br>€{p['house_price']//1000:.0f}k",
                    showarrow=False, xanchor="left", font=dict(color="#2ecc71", size=10))

            _fig_sens.update_layout(
                barmode="stack",
                **chart_layout(
                    f"Monthly Repayment vs House Price — {_chosen_label}, "
                    f"{_dp*100:.0f}% down, {_rate*100:.1f}% rate",
                    yaxis_title="€/month", height=440))
            st.plotly_chart(_fig_sens, use_container_width=True, key="fig_mort_sens")

            # Key callout metrics for the currently selected house price
            _mc1, _mc2, _mc3, _mc4 = st.columns(4)
            _mc1.metric("Gross payment",   f"€{_gross_pay[_cur_idx]:,.0f}/mo")
            _mc2.metric("MRI tax benefit", f"€{_mri_ben[_cur_idx]:,.0f}/mo",
                help="Hypotheekrenteaftrek — mortgage interest deductible at 36.97%")
            _mc3.metric("Net payment",     f"€{_net_pay[_cur_idx]:,.0f}/mo")
            _mc4.metric("Loan amount",     f"€{int(_prices[_cur_idx]*(1-_dp)):,.0f}",
                help=f"{(1-_dp)*100:.0f}% of purchase price after {_dp*100:.0f}% down payment")

        # ── How are these numbers calculated? (bottom of tab) ─────────────────────
        st.divider()
        with st.expander("📖 How are these numbers calculated?", expanded=False):
            st.markdown(f"""
    ### Annuity vs Linear Mortgage

    Both mortgage types amortise the same loan over 30 years at the same interest rate, but they differ in how payments are structured.

    #### Annuity (*annuïteit*)
    - **Gross payment is constant** every month for 30 years
    - Early payments are mostly interest; late payments are mostly principal
    - The formula: `P = L × [r(1+r)ⁿ] / [(1+r)ⁿ − 1]`  
      where L = loan, r = monthly rate, n = 360 months
    - **Net payment rises over time** because the MRI tax benefit shrinks as your balance falls and you pay less interest each month

    #### Linear (*lineair*)
    - **Principal repayment is constant** every month (loan ÷ 360)
    - Gross payment starts high and falls steadily
    - **Net payment also falls steadily** — you pay less interest and less MRI benefit each month
    - Total interest paid over 30 years is lower than annuity

    #### Hypotheekrenteaftrek (MRI)
    The Dutch government lets you deduct mortgage interest from your Box 1 taxable income:

    ```
    Monthly MRI benefit = Monthly interest paid × 36.97%
    ```

    The 36.97% rate is the bottom Box 1 rate (2026). This is automatically applied as a monthly cash saving on your effective payment. The benefit:
    - Is **highest in year 1** when your balance and interest are largest
    - **Falls every year** as you repay principal
    - Is **equal for both mortgage types in month 1** (same opening balance), but diverges as the balance falls at different speeds

    #### 30-year cost comparison
    Linear mortgages are always cheaper in total interest paid, but the higher initial payments require a stronger cashflow in the early years. Annuity mortgages suit buyers who need predictable fixed monthly costs.

    | | Annuity | Linear |
    |---|---|---|
    | Monthly payment | Fixed | Falling |
    | Total interest (30yr) | Higher | Lower |
    | MRI benefit (30yr) | Higher total | Lower total |
    | Early cashflow stress | Lower | Higher |
            """)

# TAB 4 — SCENARIO A/B  (paid)
# ════════════════════════════════════════════════════════════════════════════════

with tabs[4]:
    if not IS_PAID:
        _paid_gate("Scenario A/B Comparison", icon="🔀")
        st.caption("Configure two scenarios side-by-side — e.g. buy in 2026 vs 2028, with vs without 30% ruling — and compare net worth, cashflow, and savings over time.")
        _paid_gate("Net worth comparison · Cashflow chart · 5-year summary", icon="📊", compact=True)
        _paid_gate("Side-by-side income & tax breakdown", icon="💶", compact=True)
    else:
        if not ab_mode:
            st.info("Enable **🔀 Scenario B** toggle at the top of the **⚙️ Setup** tab, "
                    "then fill in the Scenario B column to compare two scenarios side-by-side.", icon="💡")
        else:
            _sa_name = pa.get("scenario_label") or "Scenario A"
            _sb_name = pb.get("scenario_label") or "Scenario B"
            st.subheader(f"🔀 {_sa_name} vs {_sb_name}")
            with st.expander("ℹ️ How to read this tab", expanded=False):
                st.markdown("""
    Compare two scenarios side-by-side. Configure both in the **⚙️ Setup** tab.

    - **Green (A)** and **Blue (B)** traces on all charts
    - 🏠 markers show each scenario's **house purchase date** (solid dash line)
    - 🏷️ markers show each scenario's **house sell date** (dotted line), if enabled
    - The summary table at the top shows end-state numbers for both scenarios
                """)

            def scenario_summary(dfm, dfw, lbl, p_sc):
                fin = dfw.iloc[-1]
                buy_date = pd.Timestamp(year=p_sc["by"], month=p_sc["bm"], day=1).strftime("%b %Y")
                sell_info = (pd.Timestamp(year=p_sc.get("sy",2031), month=p_sc.get("sm",1), day=1).strftime("%b %Y")
                             if p_sc.get("sell_house") else "—")
                return {"Scenario": lbl,
                        "House Buy Date":      buy_date,
                        "House Sell Date":     sell_info,
                        "Mortgage Rate":       f"{p_sc['mort_rate']*100:.1f}%",
                        "House Price":         f"€{p_sc['house_price']:,.0f}",
                        "Avg Net Income/mo":   f"€{dfm['Total Net'].mean():,.0f}",
                        "Avg Expenses/mo":     f"€{dfm['Total Expenses'].mean():,.0f}",
                        "Avg Savings/mo":      f"€{dfm['Net Saving'].mean():,.0f}",
                        "End Wealth (Buy)":    f"€{fin['Total Wealth (Buy)']:,.0f}",
                        "End Wealth (Rent)":   f"€{fin['Total Wealth (Rent)']:,.0f}",
                        "Home Equity (end)":   f"€{fin['Home Equity']:,.0f}",
                        "Buy vs Rent Edge":    f"€{fin['Wealth Delta']:,.0f}"}

            cmp = pd.DataFrame([scenario_summary(df_m_a, df_w_a, _sa_name, pa),
                                 scenario_summary(df_m_b, df_w_b, _sb_name, pb)])
            st.dataframe(cmp.set_index("Scenario").T, use_container_width=True)
            st.divider()

            # ── Variable diff table ────────────────────────────────────────────
            st.markdown("#### 🔍 What changed between scenarios?")
            _diff_fields = [
                ("Your gross income",    lambda p: f"€{p['inc_s']:,.0f}/yr"),
                ("Partner gross income", lambda p: f"€{p['inc_p']:,.0f}/yr" if p["partner"] else "—"),
                ("Your salary growth",   lambda p: f"{p.get('sal_growth',0)*100:.1f}%/yr"),
                ("Partner salary growth",lambda p: f"{p.get('sal_growth_p',0)*100:.1f}%/yr" if p["partner"] else "—"),
                ("30% Ruling (You)",     lambda p: f"{'On' if p.get('ruling_s') else 'Off'} {p.get('rs_s',p['rs'])}–{p.get('re_s',p['re'])}"),
                ("30% Ruling (Partner)", lambda p: f"{'On' if p.get('ruling_p') else 'Off'} {p.get('rs_p',p['rs'])}–{p.get('re_p',p['re'])}" if p["partner"] else "—"),
                ("Rent",                 lambda p: f"€{p['rent']:,.0f}/mo"),
                ("House price",          lambda p: f"€{p['house_price']:,.0f}"),
                ("Down payment",         lambda p: f"{p['dp']*100:.0f}%"),
                ("Mortgage rate",        lambda p: f"{p['mort_rate']*100:.2f}%"),
                ("Mortgage type",        lambda p: p.get("mort_type","Annuity")),
                ("Buy date",             lambda p: f"{p['by']}-{p['bm']:02d}"),
                ("Sell house",           lambda p: f"Yes — {p.get('sy','')} mo {p.get('sm','')}" if p.get("sell_house") else "No"),
                ("Projection years",     lambda p: str(p.get("n_years", 5))),
                ("Starting savings",     lambda p: f"€{p.get('savings',0):,.0f}"),
                ("House appreciation",   lambda p: f"{p.get('ha',0.03)*100:.1f}%/yr"),
                ("Investment return",    lambda p: f"{p.get('ir',0.05)*100:.1f}%/yr"),
                ("Health insurance",     lambda p: f"€{p.get('hi',420)}/mo"),
                ("Groceries",            lambda p: f"€{p.get('gr',400)}/mo"),
                ("Utilities",            lambda p: f"€{p.get('utilities',200)}/mo"),
                ("Car (fuel+ins)",       lambda p: f"€{p.get('cf',100)+p.get('ci',100)}/mo"),
                ("Phone",                lambda p: f"€{p.get('phone',50)}/mo"),
                ("Subscriptions",        lambda p: f"€{p.get('subscriptions',50)}/mo"),
                ("Gym",                  lambda p: f"€{p.get('gym',40)}/mo"),
                ("Dog",                  lambda p: f"€{p.get('dog',150)}/mo"),
                ("Other",                lambda p: f"€{p.get('ot',300)}/mo"),
                ("Children dagopvang",   lambda p: str(p.get("n_kdv", 0))),
                ("Children BSO",         lambda p: str(p.get("n_bso", 0))),
                    ]
            _diff_rows = []
            for _fname, _fget in _diff_fields:
                try:
                    _va = _fget(pa); _vb = _fget(pb)
                except Exception:
                    continue
                if _va != _vb:
                    _diff_rows.append({"Variable": _fname, _sa_name: _va, _sb_name: _vb})
            if _diff_rows:
                _diff_df = pd.DataFrame(_diff_rows)
                st.dataframe(_diff_df.set_index("Variable"), use_container_width=True)
                st.caption(f"Showing {len(_diff_rows)} variable(s) that differ between {_sa_name} and {_sb_name}. Identical inputs are hidden.")
            else:
                st.info("No differences found — Scenarios A and B have identical inputs. Change some values in Setup to compare.", icon="🔍")
            st.divider()

            cl, cr = st.columns(2)

            # ── Chart 1: Net income & savings with buy/sell markers ───────────────
            fig_c1 = go.Figure()
            fig_c1.add_trace(go.Scatter(x=df_m_a["Date"], y=df_m_a["Total Net"],
                                        name="Net Income A", line=dict(color="#2ecc71", width=2)))
            fig_c1.add_trace(go.Scatter(x=df_m_b["Date"], y=df_m_b["Total Net"],
                                        name="Net Income B", line=dict(color="#3498db", width=2, dash="dash")))
            fig_c1.add_trace(go.Scatter(x=df_m_a["Date"], y=df_m_a["Net Saving"],
                                        name="Savings A", line=dict(color="#f1c40f", width=1.5, dash="dot")))
            fig_c1.add_trace(go.Scatter(x=df_m_b["Date"], y=df_m_b["Net Saving"],
                                        name="Savings B", line=dict(color="#e67e22", width=1.5, dash="dot")))
            add_events(fig_c1, pa, label="A", buy_y=0.88, sell_y=0.75,
                       buy_color="#2ecc71", sell_color="#27ae60")
            add_events(fig_c1, pb, label="B", buy_y=0.78, sell_y=0.65,
                       buy_color="#3498db", sell_color="#2980b9")
            fig_c1.update_layout(**chart_layout("Net Income & Savings: A vs B", height=420))
            cl.plotly_chart(fig_c1, use_container_width=True, key="fig_ab_c1")

            # ── Chart 2: Total wealth with buy/sell markers ───────────────────────
            fig_c2 = go.Figure()
            fig_c2.add_trace(go.Scatter(x=df_w_a["Date"], y=df_w_a["Total Wealth (Buy)"],
                                        name="Buy Wealth A", line=dict(color="#2ecc71", width=2.5)))
            fig_c2.add_trace(go.Scatter(x=df_w_b["Date"], y=df_w_b["Total Wealth (Buy)"],
                                        name="Buy Wealth B", line=dict(color="#3498db", width=2.5, dash="dash")))
            fig_c2.add_trace(go.Scatter(x=df_w_a["Date"], y=df_w_a["Total Wealth (Rent)"],
                                        name="Rent Wealth A", line=dict(color="#e74c3c", width=1.5, dash="dot")))
            fig_c2.add_trace(go.Scatter(x=df_w_b["Date"], y=df_w_b["Total Wealth (Rent)"],
                                        name="Rent Wealth B", line=dict(color="#e67e22", width=1.5, dash="dot")))
            add_events(fig_c2, pa, label="A", buy_y=0.88, sell_y=0.75,
                       buy_color="#2ecc71", sell_color="#27ae60")
            add_events(fig_c2, pb, label="B", buy_y=0.78, sell_y=0.65,
                       buy_color="#3498db", sell_color="#2980b9")
            fig_c2.update_layout(**chart_layout("Total Wealth: A vs B", height=420))
            cr.plotly_chart(fig_c2, use_container_width=True, key="fig_ab_c2")

            # ── Chart 3: Expense breakdown (mid-period, all categories) ──────────
            fig_c3 = go.Figure()
            cats = ["Housing (net MRI)", "Health Ins.", "Car", "Groceries",
                    "Utilities", "Phone & Subs", "Gym", "Dog", "Other"]
            midx_a = min(30, len(df_m_a)-1); midx_b = min(30, len(df_m_b)-1)
            m30a = df_m_a.iloc[midx_a]; m30b = df_m_b.iloc[midx_b]
            va = [max(m30a["Housing Cost"] - m30a["MRI Benefit"], 0),
                  pa["hi"], pa["cf"]+pa["ci"], pa["gr"],
                  pa.get("utilities",0), pa.get("phone",0)+pa.get("subscriptions",0),
                  pa.get("gym",0), pa.get("dog",0), pa["ot"]]
            vb = [max(m30b["Housing Cost"] - m30b["MRI Benefit"], 0),
                  pb["hi"], pb["cf"]+pb["ci"], pb["gr"],
                  pb.get("utilities",0), pb.get("phone",0)+pb.get("subscriptions",0),
                  pb.get("gym",0), pb.get("dog",0), pb["ot"]]
            fig_c3.add_trace(go.Bar(name=_sa_name, x=cats, y=va, marker_color="#2ecc71"))
            fig_c3.add_trace(go.Bar(name=_sb_name, x=cats, y=vb, marker_color="#3498db"))
            fig_c3.update_layout(barmode="group",
                                  **chart_layout("Monthly Expense Breakdown: A vs B (mid-period)", height=380))
            st.plotly_chart(fig_c3, use_container_width=True, key="fig_ab_c3")

            # ── Chart 4: Home equity trajectory ──────────────────────────────────
            fig_c4 = go.Figure()
            fig_c4.add_trace(go.Scatter(x=df_w_a["Date"], y=df_w_a["Home Equity"],
                                        name="Home Equity A", line=dict(color="#f1c40f", width=2),
                                        fill="tozeroy", fillcolor="rgba(241,196,15,0.06)"))
            fig_c4.add_trace(go.Scatter(x=df_w_b["Date"], y=df_w_b["Home Equity"],
                                        name="Home Equity B", line=dict(color="#e67e22", width=2, dash="dash"),
                                        fill="tozeroy", fillcolor="rgba(230,126,34,0.06)"))
            add_events(fig_c4, pa, label="A", buy_y=0.88, sell_y=0.75,
                       buy_color="#2ecc71", sell_color="#27ae60")
            add_events(fig_c4, pb, label="B", buy_y=0.78, sell_y=0.65,
                       buy_color="#3498db", sell_color="#2980b9")
            fig_c4.update_layout(**chart_layout("Home Equity Over Time: A vs B", height=360))
            st.plotly_chart(fig_c4, use_container_width=True, key="fig_ab_c4")

            # ── How are these numbers calculated? (bottom of tab) ─────────────────
            st.divider()
            with st.expander("📖 How are these numbers calculated?", expanded=False):
                st.markdown("""
    ### Scenario A/B Comparison

    Both scenarios run the full financial model independently with their own inputs — income, tax, mortgage, savings, appreciation, and Box 3 wealth tax are all computed separately per scenario.

    **Chart guide:**
    - **Net Income & Savings** — monthly take-home pay and savings surplus per scenario. Differences arise from income levels, ruling periods, salary growth, or expense differences.
    - **Total Wealth** — total net worth over time for buy and rent within each scenario. The crossover point (buy beats rent) may differ if house prices, rates, or appreciation rates differ between scenarios.
    - **Expense Breakdown** — side-by-side bar at month ~30 for each expense category. Quickly shows where one scenario costs more.
    - **Home Equity** — equity build-up under each scenario's mortgage. Driven by house price, down payment %, appreciation rate, and mortgage rate.

    **"What changed?" diff table** lists every input that differs between A and B — use this to understand exactly what is driving any outcome difference.

    **Tip:** Set Scenario A as your base case and use Scenario B as a what-if — e.g., buying later, a different mortgage rate, or modelling a house sale.
                """)

    # ════════════════════════════════════════════════════════════════════════════════
    # TAB 4 — SENSITIVITY
    # ════════════════════════════════════════════════════════════════════════════════

    # ════════════════════════════════════════════════════════════════════════════════
    # TAB 5 — ACTUALS  (paid)
    # ════════════════════════════════════════════════════════════════════════════════

with tabs[5]:
    if not IS_PAID:
        _paid_gate("Actuals Tracking", icon="📝")
        st.caption(
            "Enter your real monthly income and savings to track actuals vs forecast. "
            "See exactly where you stand, spot trends, and measure progress toward your goals."
        )
        _paid_gate("Monthly income entry · ING bank statement import", icon="🏦", compact=True)
        _paid_gate("Actual vs forecast charts · Variance analysis", icon="📊", compact=True)
        _paid_gate("Cumulative savings tracker · Net worth over time", icon="💎", compact=True)
    else:
        st.subheader("📝 Actuals vs Forecast")

        p_act     = pa
        has_partner = bool(p_act.get("partner", False))
        actuals_df  = load_actuals()

        # ── Date range from Setup ─────────────────────────────────────────────────
        hist_start_str = p_act.get("hist_start", "2026-01")
        hist_end_str   = p_act.get("hist_end",   pd.Timestamp.today().strftime("%Y-%m"))
        today_str      = pd.Timestamp.today().strftime("%Y-%m")

        # Clamp end to not exceed hist_end
        st.info(
            f"📅 Showing actuals for **{hist_start_str}** → **{hist_end_str}** "
            f"as configured in the ⚙️ Setup tab → 📅 Historic Data Range. "
            f"Use **➕ Add Month** to extend beyond this range.",
            icon="📋"
        )

        # ── Session state: extra months beyond hist_end ───────────────────────────
        if "act_extra_months" not in st.session_state:
            st.session_state["act_extra_months"] = 0

        # ── Build month range: hist_start → hist_end + extras ────────────────────
        hist_start_ts = pd.Timestamp(hist_start_str + "-01")
        hist_end_ts   = pd.Timestamp(hist_end_str   + "-01")
        extra         = st.session_state["act_extra_months"]

        # Months from hist_start to hist_end
        all_months = pd.date_range(start=hist_start_ts, end=hist_end_ts, freq="MS")

        # Add any extra months unlocked via ➕ Add Month
        if extra > 0:
            extra_dates = pd.date_range(
                start=hist_end_ts + pd.DateOffset(months=1), periods=extra, freq="MS")
            all_months = all_months.append(extra_dates)

        month_strs  = [d.strftime("%Y-%m") for d in all_months]
        month_labels = [d.strftime("%b %Y") for d in all_months]

        # ── Merge saved actuals ────────────────────────────────────────────────────
        base_act = pd.DataFrame({"month": month_strs, "label": month_labels})
        if not actuals_df.empty and "month" in actuals_df.columns:
            saved_cols = [c for c in ["month","inc_s_actual","inc_p_actual","savings_actual","note"]
                          if c in actuals_df.columns]
            base_act = base_act.merge(actuals_df[saved_cols], on="month", how="left")
        for col_name in ["inc_s_actual","inc_p_actual","savings_actual"]:
            if col_name not in base_act.columns: base_act[col_name] = None
            base_act[col_name] = pd.to_numeric(base_act[col_name], errors="coerce")
        if "note" not in base_act.columns: base_act["note"] = ""
        base_act["note"] = base_act["note"].fillna("")

        # ── Compute forecast for every month ──────────────────────────────────────
        fc_rows = []
        for dt in all_months:
            yr = dt.year; mo_n = dt.month
            # For months beyond projection window, use last projection year's settings
            yr_tax = min(yr, 2030)
            a30_s  = p_act.get("ruling_s", True)  and p_act.get("rs_s", p_act["rs"]) <= yr < p_act.get("re_s", p_act["re"])
            a30_p  = p_act.get("ruling_p", False) and p_act.get("rs_p", p_act["rs"]) <= yr < p_act.get("re_p", p_act["re"])
            _act_rates_s = ruling_rate(p_act.get("rs_s_start", p_act.get("rs_s", p_act["rs"])))
            _act_rates_p = ruling_rate(p_act.get("rs_p_start", p_act.get("rs_p", p_act["rs"])))
            _re_s_act = _act_rates_s.get(yr, 0.30) if a30_s else 0.30
            _re_p_act = _act_rates_p.get(yr, 0.30) if a30_p else 0.30
            sg     = p_act.get("sal_growth", 0.0)
            sg_p   = p_act.get("sal_growth_p", sg)
            yrs_e  = yr - 2026
            inc_s_adj = p_act["inc_s"] * (1 + sg)   ** yrs_e
            inc_p_adj = p_act["inc_p"] * (1 + sg_p) ** yrs_e
            nm_s  = net_monthly_calc(inc_s_adj, yr_tax, a30_s, _re_s_act)
            nm_p  = net_monthly_calc(inc_p_adj, yr_tax, a30_p, _re_p_act) if has_partner else 0
            gross = inc_s_adj + (inc_p_adj if has_partner else 0)
            zts   = zorgtoeslag(gross, has_partner)
            owns  = (yr > p_act["by"]) or (yr == p_act["by"] and mo_n >= p_act["bm"])
            housing = mort_payment(p_act["house_price"], p_act["dp"], p_act["mort_rate"]) \
                      if owns else p_act["rent"]
            recurring = (p_act["hi"] + p_act["cf"] + p_act["ci"] + p_act["gr"] + p_act["ot"]
                         + p_act.get("utilities",0) + p_act.get("phone",0)
                         + p_act.get("subscriptions",0) + p_act.get("gym",0) + p_act.get("dog",0))
            fixed_total = housing + recurring
            fc_rows.append({
                "month":          dt.strftime("%Y-%m"),
                "fc_inc_s":       round(nm_s),
                "fc_inc_p":       round(nm_p),
                "fc_inc_total":   round(nm_s + nm_p),
                "fc_housing":     round(housing),
                "fc_recurring":   round(recurring),
                "fc_fixed":       round(fixed_total),
                "fc_zts":         round(zts),
                "fc_sav":         round(nm_s + nm_p + zts - fixed_total),
            })
        fc_df    = pd.DataFrame(fc_rows)
        base_act = base_act.merge(fc_df, on="month", how="left")

        # All months in range are editable (bounded by hist_start/hist_end + extras)
        editable = base_act.copy()

        # ── Fixed expenses breakdown ───────────────────────────────────────────────
        with st.expander("📋 Fixed Expenses breakdown (from Setup)", expanded=False):
            _today_ts = pd.Timestamp.today()
            owns_now = (_today_ts.year > p_act["by"]) or                    (_today_ts.year == p_act["by"] and _today_ts.month >= p_act["bm"])
            h_now = mort_payment(p_act["house_price"], p_act["dp"], p_act["mort_rate"]) \
                    if owns_now else p_act["rent"]
            fe_items = {
                "Housing (rent/mortgage)": h_now,
                "Health insurance":        p_act["hi"],
                "Car (fuel + insurance)":  p_act["cf"] + p_act["ci"],
                "Groceries":               p_act["gr"],
                "Utilities":               p_act.get("utilities", 0),
                "Phone & subscriptions":   p_act.get("phone",0) + p_act.get("subscriptions",0),
                "Gym":                     p_act.get("gym", 0),
                "Dog":                     p_act.get("dog", 0),
                "Other":                   p_act["ot"],
            }
            fe_rows = [{"Category": k, "€/month": f"€{v:,.0f}"}
                       for k, v in fe_items.items() if v > 0]
            fe_rows.append({"Category": "TOTAL", "€/month": f"€{sum(fe_items.values()):,.0f}"})
            st.dataframe(pd.DataFrame(fe_rows), use_container_width=True, hide_index=True)
            st.caption("Change these in the ⚙️ Setup tab → 🧾 Monthly Expenses.")

        # ── Bank statement importer ───────────────────────────────────────────────
        with st.expander("🏦 Import income from Bank Statement (optional)", expanded=False):
            st.markdown(
                """
    Upload your **ING bank statement CSV** (semicolon-delimited export).  
    The importer reads only **Credit** rows and sums them per calendar month.  
    The totals are treated as **income** and fill the *Actual Income* columns in the table below.  
    You can still edit every cell manually after importing.

    > **Columns expected:** `Date ; Name / Description ; Account ; Counterparty ; Code ;`  
    > `Debit/credit ; Amount (EUR) ; Transaction type ; Notifications`
                """
            )
            imp_col1, imp_col2 = st.columns(2)
            with imp_col1:
                st.markdown(f"**Your statement** *(fills: Actual You income)*")
                bank_file_s = st.file_uploader(
                    "Your bank statement (.csv)",
                    type=["csv"],
                    key="bank_stmt_you",
                    label_visibility="collapsed",
                )
            with imp_col2:
                st.markdown(f"**Partner's statement** *(fills: Actual Partner income)*")
                bank_file_p = st.file_uploader(
                    "Partner bank statement (.csv)",
                    type=["csv"],
                    key="bank_stmt_partner",
                    label_visibility="collapsed",
                    disabled=not has_partner,
                    help="Enable partner in Setup first." if not has_partner else "",
                )

            parsed_s, parsed_p = None, None
            err_msgs = []

            if bank_file_s:
                try:
                    parsed_s = parse_bank_statement(bank_file_s)
                    st.success(f"✅ Your statement: {len(parsed_s)} month(s) of Credit entries parsed.", icon="🏦")
                    prev_s = parsed_s.copy()
                    prev_s["amount"] = prev_s["amount"].apply(lambda x: f"€{x:,.2f}")
                    prev_s.columns = ["Month", "Credit Total (income)"]
                    st.dataframe(prev_s, use_container_width=True, hide_index=True)
                except Exception as exc:
                    err_msgs.append(f"Your statement: {exc}")

            if bank_file_p and has_partner:
                try:
                    parsed_p = parse_bank_statement(bank_file_p)
                    st.success(f"✅ Partner statement: {len(parsed_p)} month(s) of Credit entries parsed.", icon="🏦")
                    prev_p = parsed_p.copy()
                    prev_p["amount"] = prev_p["amount"].apply(lambda x: f"€{x:,.2f}")
                    prev_p.columns = ["Month", "Credit Total (income)"]
                    st.dataframe(prev_p, use_container_width=True, hide_index=True)
                except Exception as exc:
                    err_msgs.append(f"Partner statement: {exc}")

            for em in err_msgs:
                st.error(f"❌ {em}")

            if (parsed_s is not None or parsed_p is not None):
                if st.button("📥 Apply to table (income columns)", type="primary"):
                    existing = load_actuals()  # always returns DataFrame with all _ACTUALS_COLS

                    def _apply_income(existing_df, monthly_df, col):
                        for _, row in monthly_df.iterrows():
                            mask = existing_df["month"] == row["month"]
                            if mask.any():
                                existing_df.loc[mask, col] = row["amount"]
                            else:
                                new_row = {c: None for c in _ACTUALS_COLS}
                                new_row["month"] = row["month"]
                                new_row["note"]  = ""
                                new_row[col]     = row["amount"]
                                existing_df = pd.concat(
                                    [existing_df, pd.DataFrame([new_row])], ignore_index=True
                                )
                        return existing_df

                    if parsed_s is not None:
                        existing = _apply_income(existing, parsed_s, "inc_s_actual")
                    if parsed_p is not None:
                        existing = _apply_income(existing, parsed_p, "inc_p_actual")

                    existing = existing.sort_values("month").reset_index(drop=True)
                    save_actuals(existing)
                    st.success("✅ Income columns updated from bank statement(s). Table refreshed below.")
                    st.rerun()

        # ── Input grid — grouped by year ─────────────────────────────────────────
        st.markdown("### ✏️ Enter Monthly Actuals")

        if has_partner:
            col_w   = [1.4, 1.3, 1.3, 1.3, 1.3, 1.2, 1.3, 1.6]
            headers = ["**Month**", "**Target**",
                       "**You (€)**", "**Partner (€)**",
                       "**Savings (€)**", "**Fixed**", "**Variable**", "**Note**"]
        else:
            col_w   = [1.5, 1.5, 1.8, 1.5, 1.5, 1.5, 2.0]
            headers = ["**Month**", "**Target**",
                       "**Income (€)**", "**Savings (€)**",
                       "**Fixed**", "**Variable**", "**Note**"]

        # Group months by year
        editable["year"] = editable["month"].str[:4]
        years_in_range   = editable["year"].unique().tolist()
        current_year     = pd.Timestamp.today().strftime("%Y")

        updated_rows = []

        for yr_str in years_in_range:
            yr_rows = editable[editable["year"] == yr_str]

            # ── Year summary for the expander label ───────────────────────────────
            yr_inc_s = yr_rows["inc_s_actual"].sum(skipna=True)
            yr_inc_p = yr_rows["inc_p_actual"].sum(skipna=True) if has_partner else 0
            yr_sav   = yr_rows["savings_actual"].sum(skipna=True)
            yr_has_data = (
                yr_rows["inc_s_actual"].notna().any() or
                yr_rows["inc_p_actual"].notna().any() or
                yr_rows["savings_actual"].notna().any()
            )
            _yr_inc_total = yr_inc_s + yr_inc_p
            if yr_has_data:
                _yr_label_detail = (
                    f"  ·  Income: €{_yr_inc_total:,.0f}"
                    + (f"  ·  Savings: €{yr_sav:,.0f}" if yr_rows["savings_actual"].notna().any() else "")
                )
            else:
                _yr_label_detail = "  ·  no data entered yet"

            # All years collapsed by default — user opens the year they want to edit
            _yr_open = False

            with st.expander(f"📅 **{yr_str}**{_yr_label_detail}", expanded=_yr_open):
                # Column headers inside each year block
                hcols = st.columns(col_w)
                for hcol, hdr in zip(hcols, headers):
                    hcol.markdown(hdr)

                for _, row in yr_rows.iterrows():
                    is_future = row["month"] > today_str
                    cur_inc_s  = float(row["inc_s_actual"]) if pd.notna(row["inc_s_actual"]) else None
                    cur_inc_p  = float(row["inc_p_actual"]) if pd.notna(row["inc_p_actual"]) else None
                    cur_sav    = float(row["savings_actual"]) if pd.notna(row["savings_actual"]) else None
                    cur_note   = row["note"] if row["note"] else ""
                    fixed      = row["fc_fixed"]
                    target_sav = row["fc_sav"]
                    lbl_txt    = f"**{row['label']}**" + (" 🔮" if is_future else "")

                    if has_partner:
                        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(col_w)
                        c1.markdown(lbl_txt)
                        ts_col = "#2ecc71" if target_sav >= 0 else "#e74c3c"
                        c2.markdown(f"<span style='color:{ts_col}'>€{target_sav:,.0f}</span>",
                                    unsafe_allow_html=True)
                        inc_s_inp = c3.number_input("_", value=cur_inc_s, step=50.0,
                            placeholder="—", key=f"inc_s_{row['month']}",
                            label_visibility="collapsed", help="Your actual net income this month")
                        inc_p_inp = c4.number_input("_", value=cur_inc_p, step=50.0,
                            placeholder="—", key=f"inc_p_{row['month']}",
                            label_visibility="collapsed", help="Partner actual net income this month")
                        sav_inp = c5.number_input("_", value=cur_sav, step=50.0,
                            placeholder="—", key=f"sav_{row['month']}",
                            label_visibility="collapsed", help="Combined household savings this month")
                        c6.markdown(f"<span style='color:#aaa'>€{fixed:,.0f}</span>",
                                    unsafe_allow_html=True)
                        inc_total = ((inc_s_inp or 0) + (inc_p_inp or 0)
                                     if (inc_s_inp is not None or inc_p_inp is not None) else None)
                        if inc_total is not None and sav_inp is not None:
                            var_exp = inc_total - sav_inp - fixed
                            vcol = "#e74c3c" if var_exp < 0 else "#2ecc71"
                            c7.markdown(f"<span style='color:{vcol}'>€{var_exp:,.0f}</span>",
                                        unsafe_allow_html=True)
                        else:
                            c7.markdown("<span style='color:#555'>—</span>", unsafe_allow_html=True)
                        note_inp = c8.text_input("_", value=cur_note,
                            key=f"note_{row['month']}", placeholder="note",
                            label_visibility="collapsed")

                    else:
                        c1, c2, c3, c4, c5, c6, c7 = st.columns(col_w)
                        c1.markdown(lbl_txt)
                        ts_col = "#2ecc71" if target_sav >= 0 else "#e74c3c"
                        c2.markdown(f"<span style='color:{ts_col}'>€{target_sav:,.0f}</span>",
                                    unsafe_allow_html=True)
                        inc_s_inp = c3.number_input("_", value=cur_inc_s, step=50.0,
                            placeholder="—", key=f"inc_s_{row['month']}",
                            label_visibility="collapsed")
                        inc_p_inp = None
                        sav_inp = c4.number_input("_", value=cur_sav, step=50.0,
                            placeholder="—", key=f"sav_{row['month']}",
                            label_visibility="collapsed")
                        c5.markdown(f"<span style='color:#aaa'>€{fixed:,.0f}</span>",
                                    unsafe_allow_html=True)
                        if inc_s_inp is not None and sav_inp is not None:
                            var_exp = inc_s_inp - sav_inp - fixed
                            vcol = "#e74c3c" if var_exp < 0 else "#2ecc71"
                            c6.markdown(f"<span style='color:{vcol}'>€{var_exp:,.0f}</span>",
                                        unsafe_allow_html=True)
                        else:
                            c6.markdown("<span style='color:#555'>—</span>", unsafe_allow_html=True)
                        note_inp = c7.text_input("_", value=cur_note,
                            key=f"note_{row['month']}", placeholder="note",
                            label_visibility="collapsed")

                    updated_rows.append({
                        "month":          row["month"],
                        "inc_s_actual":   inc_s_inp,
                        "inc_p_actual":   inc_p_inp,
                        "savings_actual": sav_inp,
                        "note":           note_inp,
                    })

                # ── Year-end summary bar inside the expander ──────────────────────
                if yr_has_data or True:
                    _yr_inp_s = sum(
                        r["inc_s_actual"] for r in updated_rows
                        if r["month"].startswith(yr_str) and r["inc_s_actual"] is not None
                    )
                    _yr_inp_p = sum(
                        r["inc_p_actual"] for r in updated_rows
                        if r["month"].startswith(yr_str) and r["inc_p_actual"] is not None
                    ) if has_partner else 0
                    _yr_inp_sav = sum(
                        r["savings_actual"] for r in updated_rows
                        if r["month"].startswith(yr_str) and r["savings_actual"] is not None
                    )
                    _yr_fc_inc = yr_rows["fc_inc_s"].sum() + (yr_rows["fc_inc_p"].sum() if has_partner else 0)
                    _yr_fc_sav = yr_rows["fc_sav"].sum()
                    st.markdown("---")
                    _sc = st.columns(4 if has_partner else 3)
                    _sc[0].metric(f"{yr_str} Income (You)", f"€{_yr_inp_s:,.0f}",
                        delta=f"€{_yr_inp_s - yr_rows['fc_inc_s'].sum():+,.0f} vs forecast"
                        if _yr_inp_s > 0 else None)
                    if has_partner:
                        _sc[1].metric(f"{yr_str} Income (Partner)", f"€{_yr_inp_p:,.0f}",
                            delta=f"€{_yr_inp_p - yr_rows['fc_inc_p'].sum():+,.0f} vs forecast"
                            if _yr_inp_p > 0 else None)
                    _sc[-2].metric(f"{yr_str} Savings", f"€{_yr_inp_sav:,.0f}",
                        delta=f"€{_yr_inp_sav - _yr_fc_sav:+,.0f} vs forecast"
                        if _yr_inp_sav > 0 else None)
                    _sc[-1].metric(f"{yr_str} Forecast Income", f"€{_yr_fc_inc:,.0f}",
                        help="Combined forecast net income for the year")



        # ── Buttons row ──────────────────────────────────────────────────────────
        st.divider()
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns([2, 2, 2, 4])

        with btn_col1:
            if st.button("➕ Add Month", help="Unlock one more future month for data entry"):
                st.session_state["act_extra_months"] += 1
                st.rerun()

        with btn_col2:
            if st.button("💾 Save Actuals", type="primary",
                         help="Saves your entries to this browser session. Download below to keep them permanently."):
                # Build a DataFrame from what the user typed in the widgets
                widget_df = pd.DataFrame(updated_rows)
                for _c in ["inc_s_actual", "inc_p_actual", "savings_actual"]:
                    widget_df[_c] = pd.to_numeric(widget_df[_c], errors="coerce")

                # Merge with any already-saved data (preserves off-screen months)
                existing = load_actuals()
                if existing.empty or "month" not in existing.columns:
                    merged = widget_df.copy()
                else:
                    off_screen = existing[~existing["month"].isin(widget_df["month"])]
                    on_screen  = widget_df.copy()
                    if "note" in existing.columns:
                        disk_notes = existing.set_index("month")["note"]
                        on_screen["note"] = on_screen.apply(
                            lambda r: (disk_notes.get(r["month"], "") or "")
                            if not r["note"] else r["note"],
                            axis=1,
                        )
                    merged = pd.concat([off_screen, on_screen], ignore_index=True)

                # Drop entirely empty rows
                merged = merged[
                    merged["inc_s_actual"].notna() |
                    merged["inc_p_actual"].notna() |
                    merged["savings_actual"].notna()
                ]
                merged = merged.sort_values("month").reset_index(drop=True)
                save_actuals(merged)
                st.success(f"✅ {len(merged)} months saved to this session. Download below to keep permanently.")
                st.rerun()

        # Download actuals CSV
        _act_for_dl = load_actuals()
        with btn_col3:
            st.download_button(
                label="⬇️ Download actuals",
                data=actuals_to_csv_bytes(_act_for_dl) if not _act_for_dl.empty else b"month,inc_s_actual,inc_p_actual,savings_actual,note\n",
                file_name="dutch_dashboard_actuals.csv",
                mime="text/csv",
                use_container_width=True,
                help="Download your actuals data as a CSV to keep it permanently. Re-upload it next session.",
            )

        # Upload actuals CSV — shown below the button row for space
        st.markdown("**⬆️ Restore actuals from file**")
        _uploaded_actuals = st.file_uploader(
            "Upload actuals CSV",
            type=["csv"],
            key="actuals_upload",
            label_visibility="collapsed",
            help="Upload a previously downloaded actuals CSV to restore your data.",
        )
        if _uploaded_actuals is not None:
            _act_restored = actuals_from_uploaded_file(_uploaded_actuals)
            save_actuals(_act_restored)
            st.success(f"✅ {len(_act_restored)} months of actuals restored from file.")
            st.rerun()

        # ── Charts ────────────────────────────────────────────────────────────────
        actual_data = pd.DataFrame(updated_rows)
        for col_n in ["inc_s_actual","inc_p_actual","savings_actual"]:
            actual_data[col_n] = pd.to_numeric(actual_data[col_n], errors="coerce")
        actual_data = actual_data.merge(fc_df, on="month", how="left")
        actual_data["month_dt"]    = pd.to_datetime(actual_data["month"] + "-01")
        actual_data["inc_combined"] = actual_data["inc_s_actual"].fillna(0) + \
                                      actual_data["inc_p_actual"].fillna(0)
        actual_data["inc_combined"] = actual_data["inc_combined"].where(
            actual_data["inc_s_actual"].notna() | actual_data["inc_p_actual"].notna(), other=float("nan"))
        actual_data["var_exp"] = actual_data["inc_combined"] - \
                                 actual_data["savings_actual"] - \
                                 actual_data["fc_fixed"]

        has_actuals = actual_data["savings_actual"].notna().any() or \
                      actual_data["inc_s_actual"].notna().any()

        if has_actuals:
            st.divider()
            st.subheader("📊 Actuals vs Forecast")

            # Income chart: show all months that have any income data
            a_inc  = actual_data.dropna(subset=["inc_s_actual"], how="all").copy()
            # Savings chart: show months with savings data
            a_f    = actual_data.dropna(subset=["savings_actual"]).copy()
            # Full breakdown: need both income and savings
            a_full = actual_data.dropna(subset=["savings_actual","inc_combined"]).copy()

            # ── Chart 1: Income per person vs forecast ────────────────────────────
            cl, cr = st.columns(2)
            fig_a0 = go.Figure()
            if has_partner:
                # Forecast bars shown for all months with any actual income
                _months_with_inc = actual_data[
                    actual_data["inc_s_actual"].notna() | actual_data["inc_p_actual"].notna()
                ]
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"], y=_months_with_inc["fc_inc_s"],
                                        name=f"{p_act.get('name_s','You')} (fc)",
                                        marker_color="#3498db", opacity=0.45))
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"], y=_months_with_inc["fc_inc_p"],
                                        name=f"{p_act.get('name_p','Partner')} (fc)",
                                        marker_color="#8e44ad", opacity=0.45))
                if actual_data["inc_s_actual"].notna().any():
                    fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                            y=_months_with_inc["inc_s_actual"],
                                            name=f"{p_act.get('name_s','You')} (act)",
                                            marker_color="#2ecc71"))
                if actual_data["inc_p_actual"].notna().any():
                    fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                            y=_months_with_inc["inc_p_actual"],
                                            name=f"{p_act.get('name_p','Partner')} (act)",
                                            marker_color="#f1c40f"))
                fig_a0.update_layout(barmode="group",
                                      **chart_layout("Monthly Income per Person: Actual vs Forecast",
                                                     height=340))
            else:
                _months_with_inc = actual_data[actual_data["inc_s_actual"].notna()]
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"], y=_months_with_inc["fc_inc_s"],
                                        name="Income (fc)", marker_color="#3498db", opacity=0.5))
                if actual_data["inc_s_actual"].notna().any():
                    fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                            y=_months_with_inc["inc_s_actual"],
                                            name="Income (act)", marker_color="#2ecc71"))
                fig_a0.update_layout(barmode="overlay",
                                      **chart_layout("Monthly Income: Actual vs Forecast", height=340))
            cl.plotly_chart(fig_a0, use_container_width=True, key="fig_act_0")

            # ── Chart 2: Savings actual vs forecast ──────────────────────────────
            fig_a1 = go.Figure()
            fig_a1.add_trace(go.Bar(x=a_f["month_dt"], y=a_f["fc_sav"],
                                    name="Savings", marker_color="#3498db", opacity=0.5))
            fig_a1.add_trace(go.Bar(x=a_f["month_dt"], y=a_f["savings_actual"],
                                    name="Savings (act)", marker_color="#2ecc71"))
            fig_a1.update_layout(barmode="overlay",
                                  **chart_layout("Monthly Savings: Actual vs Forecast", height=340))
            cr.plotly_chart(fig_a1, use_container_width=True, key="fig_act_1")

            cl2, cr2 = st.columns(2)

            # ── Chart 3: Stacked breakdown ────────────────────────────────────────
            if not a_full.empty:
                a_full["var_pos"] = a_full["var_exp"].clip(lower=0)
                fig_a2 = go.Figure()
                fig_a2.add_trace(go.Bar(x=a_full["month_dt"], y=a_full["fc_fixed"],
                                        name="Fixed Exp.", marker_color="#e74c3c"))
                fig_a2.add_trace(go.Bar(x=a_full["month_dt"], y=a_full["var_pos"],
                                        name="Var. Exp.", marker_color="#e67e22"))
                fig_a2.add_trace(go.Bar(x=a_full["month_dt"], y=a_full["savings_actual"],
                                        name="Savings", marker_color="#2ecc71"))
                fig_a2.add_trace(go.Scatter(x=a_full["month_dt"], y=a_full["inc_combined"],
                                            name="Combined Income", mode="lines+markers",
                                            line=dict(color="white", width=2)))
                if has_partner:
                    fig_a2.add_trace(go.Scatter(x=a_full["month_dt"], y=a_full["inc_s_actual"],
                                                name=f"{p_act.get('name_s','You')} income",
                                                mode="lines", line=dict(color="#2ecc71", width=1.5, dash="dot")))
                fig_a2.update_layout(barmode="stack",
                                      **chart_layout("Monthly: Fixed + Variable + Savings vs Income",
                                                     height=380))
                cl2.plotly_chart(fig_a2, use_container_width=True, key="fig_act_2")

                # ── Chart 4: Variable expenses ────────────────────────────────────
                fig_a3 = go.Figure()
                fig_a3.add_trace(go.Bar(
                    x=a_full["month_dt"], y=a_full["var_exp"],
                    name="Var. Exp.",
                    marker_color=["#e74c3c" if v < 0 else "#e67e22" for v in a_full["var_exp"]]
                ))
                avg_var = a_full["var_exp"].mean()
                fig_a3.add_hline(y=avg_var, line_color="#f1c40f", line_dash="dash",
                                 annotation_text="" if st.session_state.get("narrow_mode") else f"avg €{avg_var:,.0f}",
                                 annotation_position="top right")
                fig_a3.add_hline(y=0, line_color="gray", line_dash="dot")
                fig_a3.update_layout(**chart_layout("Variable (Discretionary) Expenses per Month",
                                                    height=380))
                cr2.plotly_chart(fig_a3, use_container_width=True, key="fig_act_3")
            else:
                cl2.info("Enter both income and savings for full breakdown charts.", icon="📝")

            # ── Cumulative savings ────────────────────────────────────────────────
            a_f = a_f[a_f["month"] <= today_str].copy()   # exclude future months from cumulative
            if not a_f.empty:
                a_f["cumul_actual"]   = a_f["savings_actual"].cumsum()
                a_f["cumul_forecast"] = a_f["fc_sav"].cumsum()
                diff     = a_f["cumul_actual"].iloc[-1] - a_f["cumul_forecast"].iloc[-1]
                sign_lbl = "ahead of" if diff >= 0 else "behind"
                fig_a4 = go.Figure()
                fig_a4.add_trace(go.Scatter(x=a_f["month_dt"], y=a_f["cumul_actual"],
                                            name="Actual",
                                            line=dict(color="#2ecc71", width=2.5)))
                fig_a4.add_trace(go.Scatter(x=a_f["month_dt"], y=a_f["cumul_forecast"],
                                            name="Forecast",
                                            line=dict(color="#3498db", width=2, dash="dash")))
                fig_a4.update_layout(**chart_layout(
                    f"Cumulative Savings — €{abs(diff):,.0f} {sign_lbl} forecast", height=320))
                st.plotly_chart(fig_a4, use_container_width=True, key="fig_act_4")





            # ── KPI summary ───────────────────────────────────────────────────────
            kpi_cols = st.columns(5 if not has_partner else 6)
            kpi_cols[0].metric("Months Entered", len(a_f))
            if a_f["inc_s_actual"].notna().any():
                kpi_cols[1].metric(f"Avg {p_act.get('name_s','Your')} Income",
                                   f"€{a_f['inc_s_actual'].mean():,.0f}",
                                   delta=f"€{a_f['inc_s_actual'].mean()-a_f['fc_inc_s'].mean():,.0f} vs forecast")
            else:
                kpi_cols[1].metric(f"Forecast {p_act.get('name_s','Your')} Income",
                                   f"€{a_f['fc_inc_s'].mean():,.0f}")
            idx = 2
            if has_partner:
                if a_f["inc_p_actual"].notna().any():
                    kpi_cols[idx].metric(f"Avg {p_act.get('name_p','Partner')} Income",
                                         f"€{a_f['inc_p_actual'].mean():,.0f}",
                                         delta=f"€{a_f['inc_p_actual'].mean()-a_f['fc_inc_p'].mean():,.0f} vs forecast")
                else:
                    kpi_cols[idx].metric(f"Forecast {p_act.get('name_p','Partner')} Income",
                                         f"€{a_f['fc_inc_p'].mean():,.0f}")
                idx += 1
            kpi_cols[idx].metric("Avg Savings/mo", f"€{a_f['savings_actual'].mean():,.0f}",
                                 delta=f"€{a_f['savings_actual'].mean()-a_f['fc_sav'].mean():,.0f} vs forecast")
            kpi_cols[idx+1].metric("Avg Fixed/mo", f"€{a_f['fc_fixed'].mean():,.0f}")
            if not a_full.empty:
                kpi_cols[idx+2].metric("Avg Variable/mo", f"€{a_full['var_exp'].mean():,.0f}",
                                       help="Combined income − savings − fixed expenses")
            else:
                kpi_cols[idx+2].metric("Avg Variable/mo", "—")
        else:
            st.info("Enter actual income and savings above, then click **Save Actuals** to see charts.", icon="📝")

        # ── How are these numbers calculated? (bottom of tab) ─────────────────────
        st.divider()
        with st.expander("📖 How are these numbers calculated?", expanded=False):
            st.markdown("""
    ### Actuals vs Forecast — How the numbers work

    #### Data you enter
    - **Actual Income (You / Partner)** — your real net monthly take-home pay. This should match what lands in your bank account. Import directly from your ING bank statement (Credit rows) using the bank importer above, or type it manually.
    - **Actual Savings** — the total amount you actually saved or transferred to savings that month.

    #### Auto-computed columns
    - **Target Savings** *(green/red)* — the forecast combined household savings for that month, calculated from your Setup inputs. Green = positive surplus, red = deficit.
    - **Fixed** — your fixed monthly costs pulled directly from Setup (housing + all recurring expenses). This number changes when you switch from renting to owning.
    - **Variable** — the discretionary spend derived as:
      ```
      Variable = (Your Income + Partner Income) − Savings − Fixed Expenses
      ```
      This is everything not accounted for by fixed costs or savings: food out, clothing, holidays, entertainment. A negative number means income didn't cover fixed costs plus your target savings.

    #### Year summaries
    Each year section shows:
    - **Total income** received (You + Partner) vs the annual forecast
    - **Total savings** vs the annual forecast savings target

    #### Charts (below the table)
    - **Income chart** — actual income per person vs the forecast, by month. Useful for spotting income fluctuations or bonus months.
    - **Savings chart** — actual monthly savings vs forecast target.
    - **Expense breakdown** — shows how income splits across fixed costs, variable spending, and savings.
    - **Cumulative savings** — running total of actual savings vs cumulative forecast. Drift above or below the line shows whether you're ahead or behind your target.
            """)

with tabs[6]:
    if not IS_PAID:
        _paid_gate("Data & Export", icon="📋")
        st.caption("Download full monthly projections and wealth data as an Excel file. Available on Pro.")
        _paid_gate("Monthly P&L table · Wealth accumulation table · Excel download", icon="📥", compact=True)
    else:
        st.subheader("📋 Monthly P&L — Scenario A")
        disp = df_m_a.copy()
        disp["Date"] = disp["Date"].dt.strftime("%b %Y")
        disp["30% Ruling"] = disp["30% Ruling"].map({True: "✅", False: "❌"})
        for c in ["Net Self","Net Partner","Total Net","Zorgtoeslag","Housing Cost",
                  "MRI Benefit","Fixed Expenses","Total Expenses","Net Saving"]:
            disp[c] = disp[c].apply(lambda x: f"€{x:,.0f}")
        st.dataframe(disp.drop(columns=["Year","Month","Mortgage Balance"]),
                     use_container_width=True, hide_index=True)

        st.subheader("🏦 Monthly Wealth — Scenario A")
        disp_w = df_w_a.copy()
        disp_w["Date"] = disp_w["Date"].dt.strftime("%b %Y")
        for c in ["Cash (Buy)","Home Equity","House Value","Mortgage Balance",
                  "Total Wealth (Buy)","Cash (Rent)","Total Wealth (Rent)","Wealth Delta"]:
            disp_w[c] = disp_w[c].apply(lambda x: f"€{x:,.0f}")
        st.dataframe(disp_w.drop(columns=["Year"]), use_container_width=True, hide_index=True)

        st.divider()
        st.subheader("⬇️ Download as Excel")
        col1, col2 = st.columns(2)
        col1.download_button("📥 Download Scenario A",
                             data=to_excel_bytes(df_m_a, df_w_a),
                             file_name="dutch_dashboard_A.xlsx",
                             mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        if ab_mode:
            col2.download_button("📥 Download Scenario B",
                                 data=to_excel_bytes(df_m_b, df_w_b),
                                 file_name="dutch_dashboard_B.xlsx",
                                 mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")



        # ── How are these numbers calculated? (bottom of tab) ─────────────────────
        st.divider()
        with st.expander("📖 How are these numbers calculated?", expanded=False):
            st.markdown("""
    ### Data & Export — Column Definitions

    #### Monthly P&L table

    | Column | Description |
    |--------|-------------|
    | **Date** | Month and year |
    | **30% Ruling** | ✅ if the 30% ruling is active for that month (for You or Partner) |
    | **Net Self** | Your monthly net income after Box 1, ZVW, AHK, and arbeidskorting |
    | **Net Partner** | Partner's monthly net income (0 if no partner) |
    | **Total Net** | Combined household net income |
    | **Zorgtoeslag** | Monthly government health insurance subsidy |
    | **Housing Cost** | Rent or gross mortgage payment for that month |
    | **MRI Benefit** | Hypotheekrenteaftrek tax saving on mortgage interest (0 during rent period) |
    | **Fixed Expenses** | All recurring costs from Setup: housing (net of MRI), health insurance, car, groceries, utilities, phone, gym, dog, other |
    | **Total Expenses** | Fixed expenses minus zorgtoeslag (net of subsidy) |
    | **Net Saving** | Total Net income minus Total Expenses — your monthly surplus or deficit |

    #### Monthly Wealth table

    | Column | Description |
    |--------|-------------|
    | **Cash (Buy)** | Liquid savings in the buy scenario — starts with your initial savings, grows by monthly surplus and investment return, falls on down payment and buying costs |
    | **Home Equity** | House value minus outstanding mortgage balance. Grows with principal repayment and house appreciation. At sale, converts back to cash. |
    | **House Value** | Current market value of the house, appreciating at your Setup rate annually |
    | **Mortgage Balance** | Outstanding mortgage debt — falls with each principal repayment |
    | **Total Wealth (Buy)** | Cash (Buy) + Home Equity — your true net worth in the buy scenario |
    | **Cash (Rent)** | Liquid savings in the rent scenario — invested from day 1, grows by monthly surplus and investment return |
    | **Total Wealth (Rent)** | Same as Cash (Rent) — no home equity in this scenario |
    | **Wealth Delta** | Total Wealth (Buy) minus Total Wealth (Rent) — positive means buying is winning |

    #### Excel export
    The downloaded Excel file contains both the P&L and Wealth tables on separate sheets, with all values pre-formatted. Useful for building your own charts or sharing with a financial advisor.
            """)

    st.divider()
    st.caption("⚠️ Approximations of Dutch tax law 2026–2030. Box 3 uses fictitious return system. "
               "Zorgtoeslag is estimated. Always consult a belastingadviseur / financieel planner.")


# ════════════════════════════════════════════════════════════════════════════════
# TAB 7 — RETIREMENT PLANNING
# ════════════════════════════════════════════════════════════════════════════════

with tabs[7]:
    # ── Pro gate with gold lock header ───────────────────────────────────
    st.markdown(
        "<div style='display:flex;align-items:center;gap:10px;margin-bottom:4px'>"
        "<span style='font-size:22px;font-weight:700'>🏖️ Retirement Planning</span>"
        + ("" if IS_PAID else
        "<span style='background:linear-gradient(135deg,#d97706,#f59e0b);"
        "color:#000;font-weight:700;font-size:11px;padding:3px 10px;"
        "border-radius:20px;letter-spacing:0.3px'>🔒 PRO</span>")
        + "</div>",
        unsafe_allow_html=True
    )
    if not IS_PAID:
        # ── Greyed example charts ─────────────────────────────────────────
        st.caption("Upgrade to Pro to unlock full retirement planning — pension gap, FIRE number, portfolio growth, depletion analysis and sensitivity table.")
        import numpy as _np_ret_demo
        _ret_demo_yrs  = list(range(2026, 2059))
        _ret_demo_port = [50000 * (1.07 ** y) + 800 * y * 12 for y in range(len(_ret_demo_yrs))]
        _ret_demo_dep  = [max(600000 * (1.04 ** y) - 1200 * y * 12, 0) for y in range(34)]
        _ret_demo_ages = list(range(67, 67 + len(_ret_demo_dep)))
        st.markdown(
            "<div style='opacity:0.25;pointer-events:none;filter:blur(2px);"
            "border-radius:8px;overflow:hidden;margin-bottom:4px'>",
            unsafe_allow_html=True
        )
        _fig_ret_d1 = go.Figure()
        _fig_ret_d1.add_trace(go.Scatter(x=_ret_demo_yrs, y=_ret_demo_port,
            name="Portfolio", line=dict(color="#1d4ed8", width=2.5),
            fill="tozeroy", fillcolor="rgba(29,78,216,0.08)"))
        _fig_ret_d1.add_hline(y=750000, line_dash="dash", line_color="#b91c1c",
            annotation_text="Capital Needed", annotation_position="bottom right")
        _fig_ret_d1.update_layout(**chart_layout("Portfolio Growth to Retirement", "€", height=300,
            xaxis_title="Year"))
        st.plotly_chart(_fig_ret_d1, use_container_width=True, key="fig_ret_demo1")
        _rdc1, _rdc2 = st.columns(2)
        _fig_ret_d2 = go.Figure(go.Bar(
            x=["AOW", "Pension", "Capital (SWR)", "Target"],
            y=[1450, 500, 875, 3500],
            marker_color=["#0f766e", "#1d4ed8", "#15803d", "#b91c1c"]))
        _fig_ret_d2.update_layout(**chart_layout("Retirement Income Sources", "€/mo", height=280))
        _rdc1.plotly_chart(_fig_ret_d2, use_container_width=True, key="fig_ret_demo2")
        _fig_ret_d3 = go.Figure()
        _fig_ret_d3.add_trace(go.Scatter(x=_ret_demo_ages, y=_ret_demo_dep,
            name="Remaining Capital", line=dict(color="#15803d", width=2.5),
            fill="tozeroy", fillcolor="rgba(21,128,61,0.08)"))
        _fig_ret_d3.update_layout(**chart_layout("Portfolio Depletion in Retirement", "€", height=280,
            xaxis_title="Age"))
        _rdc2.plotly_chart(_fig_ret_d3, use_container_width=True, key="fig_ret_demo3")
        st.markdown("</div>", unsafe_allow_html=True)
        _paid_gate("Retirement Planning & FIRE Analysis", icon="🏖️")
    else:
        st.caption(
            "Dutch retirement projection — AOW · occupational pension · private capital · "
            "FIRE number · portfolio depletion · sensitivity analysis"
        )

        with st.expander("ℹ️ How does this tab work?", expanded=False):
            st.markdown("""
    This tab models your **path to retirement** and whether your projected capital is sufficient.

    **Three income pillars (Dutch system):**
    - **AOW** — state pension paid from age 67 (amount depends on years of residency; full AOW ≈ €1,450/mo single, €1,000/mo each for couples).
    - **Occupational pension (2e pijler)** — accrued via your employer. Enter your expected monthly amount.
    - **Private capital (3e pijler / Box 3)** — your own savings and investments drawn down in retirement.

    **Key metrics calculated:**
    - **Pension gap** — the difference between your target retirement income and AOW + pension.
    - **Capital needed at retirement** — gap capitalised using the Safe Withdrawal Rate (SWR).
    - **FIRE number** — total portfolio needed to retire, using your SWR. Based on the 4% rule / Trinity Study.
    - **Savings runway** — years until your projected portfolio reaches the FIRE number.
    - **Portfolio depletion** — how long capital lasts if drawn at the gap amount from retirement.

    **Assumptions:** Returns are nominal. Inflation adjustment reduces real purchasing power over time.
            """)

        p = pa   # use Scenario A parameters
        sv_ret = saved_A   # for reading saved retirement inputs

        st.divider()
        st.markdown("#### ⚙️ Retirement Inputs")
        rc1, rc2, rc3 = st.columns(3)

        ret_current_age = rc1.number_input(
            "Your current age", value=int(sv_ret.get("ret_current_age", 32)),
            min_value=18, max_value=80, step=1, key="ret_age_now",
            help="Used to calculate years to retirement and savings accumulation period.")
        ret_age = rc2.number_input(
            "Target retirement age", value=int(sv_ret.get("ret_age", 67)),
            min_value=40, max_value=80, step=1, key="ret_age",
            help="Dutch AOW age is currently 67. You can target early retirement (FIRE) by setting a lower age.")
        ret_target_income = rc3.number_input(
            "Target retirement income (€/mo net)", value=int(sv_ret.get("ret_target_income", 3500)),
            min_value=500, max_value=20000, step=100, key="ret_target",
            help="The monthly after-tax income you want in retirement. A common rule of thumb is 70–80% of your final net salary.")

        rc4, rc5, rc6 = st.columns(3)
        ret_aow = rc4.number_input(
            "Expected AOW (€/mo)", value=int(sv_ret.get("ret_aow", 1450)),
            min_value=0, max_value=3000, step=50, key="ret_aow",
            help="Full AOW (2026): ~€1,450/mo for singles, ~€1,000/mo each for couples. Reduced if you have fewer than 50 years of Dutch residency (2% per missing year).")
        ret_pension = rc5.number_input(
            "Expected occupational pension (€/mo)", value=int(sv_ret.get("ret_pension", 500)),
            min_value=0, max_value=10000, step=50, key="ret_pension",
            help="Monthly pension from your employer's scheme (2e pijler). Check your UPO (Uniform Pensioenoverzicht) from Mijnpensioenoverzicht.nl for your accrued and projected amount.")
        ret_swr = rc6.slider(
            "Safe Withdrawal Rate (%/yr)", 2.0, 6.0,
            float(sv_ret.get("ret_swr", 0.035)) * 100, 0.1,
            key="ret_swr",
            help="The % of your portfolio you withdraw annually in retirement. The classic '4% rule' (Trinity Study) works for 30yr horizons; use 3–3.5% for longer retirements or more safety.") / 100

        rc7, rc8, rc9 = st.columns(3)
        ret_return_pre = rc7.slider(
            "Pre-retirement return (%/yr)", 2.0, 12.0,
            float(sv_ret.get("ret_return_pre", 0.07)) * 100, 0.25,
            key="ret_ret_pre",
            help="Expected annual nominal return on investments before retirement. Global equity index funds have historically returned ~7–9% nominal.") / 100
        ret_return_post = rc8.slider(
            "Post-retirement return (%/yr)", 1.0, 8.0,
            float(sv_ret.get("ret_return_post", 0.04)) * 100, 0.25,
            key="ret_ret_post",
            help="Lower than pre-retirement as the portfolio shifts to more conservative assets (bonds, annuities) to reduce sequence-of-returns risk.") / 100
        ret_inflation = rc9.slider(
            "Inflation (%/yr)", 0.0, 6.0,
            float(sv_ret.get("ret_inflation", 0.025)) * 100, 0.25,
            key="ret_inflation",
            help="Used to show real (inflation-adjusted) values. ECB target is 2%. Dutch CPI averaged ~2.5% 2000–2024.") / 100

        # ── Core calculations ─────────────────────────────────────────────────────
        import datetime as _dt_ret
        years_to_ret  = max(ret_age - ret_current_age, 1)
        years_in_ret  = 100 - ret_age   # to age 100 (conservative)

        # Pension gap = target - (AOW + occupational pension)
        pillar1_2     = ret_aow + ret_pension
        pension_gap   = max(ret_target_income - pillar1_2, 0)

        # Capital needed at retirement to fund the gap (SWR method)
        capital_needed = pension_gap * 12 / ret_swr if ret_swr > 0 else 0

        # FIRE number = total capital that can fund full target income (no AOW/pension subtracted)
        fire_number   = ret_target_income * 12 / ret_swr if ret_swr > 0 else 0

        # Starting capital = current wealth from Buy vs Rent projection
        # Use end-of-projection wealth (Buy scenario total)
        starting_capital = df_w_a.iloc[-1]["Total Wealth (Buy)"]

        # Monthly savings (average over projection)
        avg_monthly_saving = df_m_a["Net Saving"].mean()

        # Project portfolio growth year-by-year (pre-retirement)
        _r_mo = (1 + ret_return_pre) ** (1/12) - 1
        portfolio = []
        cap = starting_capital
        _n_proj_years = pa.get("n_years", 5)
        _years_remaining_to_ret = years_to_ret - _n_proj_years
        # Phase 1: during projection window (we have monthly data)
        for _, row in df_m_a.iterrows():
            cap = cap * (1 + _r_mo) + row["Net Saving"]
        # Phase 2: after projection window to retirement (use avg saving, apply growth)
        for yr in range(max(_years_remaining_to_ret, 0)):
            for mo in range(12):
                cap = cap * (1 + _r_mo) + avg_monthly_saving
        projected_capital_at_ret = max(cap, 0)

        # Savings runway: years until projected portfolio hits capital_needed
        # Brute-force forward simulation from current end-of-projection capital
        _cap_run = starting_capital
        runway_years = None
        for yr in range(1, 61):
            for mo in range(12):
                _cap_run = _cap_run * (1 + _r_mo) + avg_monthly_saving
            if _cap_run >= capital_needed:
                runway_years = yr
                break

        # Portfolio depletion from projected_capital_at_ret
        _cap_dep = projected_capital_at_ret
        _r_mo_post = (1 + ret_return_post) ** (1/12) - 1
        _gap_mo = pension_gap
        depletion_years = None
        for yr in range(1, 71):
            for mo in range(12):
                _cap_dep = _cap_dep * (1 + _r_mo_post) - _gap_mo
                if _cap_dep <= 0:
                    depletion_years = yr
                    break
            if depletion_years:
                break

        # Net replacement ratio
        _cur_net = net_monthly_calc(p["inc_s"], 2026,
            p.get("ruling_s", False) and p.get("rs_s", 2026) <= 2026 < p.get("re_s", 2031))
        _cur_net += net_monthly_calc(p["inc_p"], 2026, False) if p.get("partner") else 0
        replacement_ratio = ret_target_income / max(_cur_net, 1) * 100

        # ── KPI strip ────────────────────────────────────────────────────────────
        st.divider()
        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Pension Gap / mo",
                  f"€{pension_gap:,.0f}",
                  help="Monthly shortfall: target income minus AOW and occupational pension.")
        k2.metric("Capital Needed at Retirement",
                  f"€{capital_needed:,.0f}",
                  help=f"Gap × 12 ÷ SWR ({ret_swr*100:.1f}%). Lump sum needed on retirement day to fund the shortfall indefinitely.")
        k3.metric("FIRE Number",
                  f"€{fire_number:,.0f}",
                  help="Total portfolio for full independence (no AOW/pension assumed). Same SWR applied to full target income.")
        k4.metric("Projected Capital at Retirement",
                  f"€{projected_capital_at_ret:,.0f}",
                  delta=f"{'✅ Surplus' if projected_capital_at_ret >= capital_needed else '⚠️ Shortfall'} €{abs(projected_capital_at_ret - capital_needed):,.0f}",
                  delta_color="normal" if projected_capital_at_ret >= capital_needed else "inverse",
                  help="Forward projection of your wealth at retirement age, growing at the pre-retirement return rate.")

        k5, k6, k7, k8 = st.columns(4)
        k5.metric("Years to Retirement", f"{years_to_ret} yr",
                  help=f"From age {ret_current_age} to {ret_age}.")
        k6.metric("Savings Runway",
                  f"{runway_years} yr" if runway_years else "< 1 yr" if starting_capital >= capital_needed else "> 60 yr",
                  help="Years until your growing portfolio hits the capital needed, continuing at your current avg monthly savings.")
        k7.metric("Portfolio Lasts (post-ret.)",
                  f"{depletion_years} yr" if depletion_years else f">{years_in_ret} yr ✅",
                  help="How long your projected capital sustains the pension gap at the post-retirement return rate.")
        k8.metric("Net Replacement Ratio",
                  f"{replacement_ratio:.0f}%",
                  help="Target retirement income as % of current net household income. Aim for 70–80%.")

        # ── Charts ───────────────────────────────────────────────────────────────
        st.divider()

        # Chart 1: Portfolio growth to retirement
        st.markdown("#### 📈 Portfolio Growth to Retirement")
        _yrs_axis  = list(range(0, years_to_ret + 1))
        _portfolio_curve = [starting_capital]
        _cap_c = starting_capital
        _r_mo_c = (1 + ret_return_pre) ** (1/12) - 1
        # use projected savings from df_m_a for first n_years, then avg
        _proj_months = len(df_m_a)
        _savings_list = list(df_m_a["Net Saving"])
        _month_counter = 0
        for _yr in range(1, years_to_ret + 1):
            for _mo in range(12):
                _s = _savings_list[_month_counter] if _month_counter < _proj_months else avg_monthly_saving
                _cap_c = _cap_c * (1 + _r_mo_c) + _s
                _month_counter += 1
            _portfolio_curve.append(_cap_c)

        fig_grow = go.Figure()
        fig_grow.add_trace(go.Scatter(
            x=[_dt_ret.date.today().year + y for y in _yrs_axis],
            y=_portfolio_curve,
            name="Projected Portfolio",
            line=dict(color="#1d4ed8", width=2.5),
            fill="tozeroy", fillcolor="rgba(29,78,216,0.08)"
        ))
        fig_grow.add_hline(y=capital_needed, line_dash="dash", line_color="#b91c1c",
                           annotation_text=f"Capital needed  €{capital_needed:,.0f}",
                           annotation_position="bottom right")
        fig_grow.add_hline(y=fire_number, line_dash="dot", line_color="#b45309",
                           annotation_text=f"FIRE number  €{fire_number:,.0f}",
                           annotation_position="top right")
        fig_grow.update_layout(
            **chart_layout("Portfolio Growth to Retirement", "Portfolio value (€)", height=350,
                           xaxis_title="Year")
        )
        st.plotly_chart(fig_grow, use_container_width=True)

        # Chart 2: Retirement income waterfall
        st.markdown("#### 💰 Retirement Income Breakdown")
        fig_income = go.Figure(go.Bar(
            x=["AOW (state)", "Occupational Pension", "Private Capital (SWR)", "Target"],
            y=[ret_aow, ret_pension,
               projected_capital_at_ret * ret_swr / 12,
               ret_target_income],
            marker_color=["#0f766e", "#1d4ed8", "#15803d", "#b91c1c"],
            text=[f"€{v:,.0f}" for v in [
                ret_aow, ret_pension,
                projected_capital_at_ret * ret_swr / 12,
                ret_target_income
            ]],
            textposition="outside",
        ))
        fig_income.update_layout(
            **chart_layout("Monthly Retirement Income Sources vs Target", "€/mo", height=330),
            showlegend=False,
        )
        st.plotly_chart(fig_income, use_container_width=True)

        # Chart 3: Portfolio depletion in retirement
        st.markdown("#### 📉 Portfolio Depletion in Retirement")
        _dep_yrs  = min(years_in_ret, 50)
        _dep_curve = [projected_capital_at_ret]
        _cap_d = projected_capital_at_ret
        for _yr in range(_dep_yrs):
            for _mo in range(12):
                _cap_d = _cap_d * (1 + _r_mo_post) - _gap_mo
            _dep_curve.append(max(_cap_d, 0))
            if _cap_d <= 0:
                _dep_curve += [0] * (_dep_yrs - _yr - 1)
                break

        fig_dep = go.Figure()
        fig_dep.add_trace(go.Scatter(
            x=[ret_age + y for y in range(len(_dep_curve))],
            y=_dep_curve,
            name="Remaining Capital",
            line=dict(color="#15803d", width=2.5),
            fill="tozeroy", fillcolor="rgba(21,128,61,0.08)"
        ))
        fig_dep.add_hline(y=0, line_color="#b91c1c", line_width=1)
        fig_dep.update_layout(
            **chart_layout("Portfolio Depletion in Retirement", "Remaining capital (€)", height=330,
                           xaxis_title="Age")
        )
        st.plotly_chart(fig_dep, use_container_width=True)

        # ── Sensitivity table ────────────────────────────────────────────────────
        st.divider()
        st.markdown("#### 🔢 Capital Needed — Sensitivity (Retirement Age × Target Income)")
        st.caption(
            "Shows the lump-sum capital required at retirement for each combination of "
            "retirement age and target monthly income, at the current SWR. "
            "Green = your projected capital covers it. Red = shortfall."
        )
        _ages     = [55, 60, 62, 65, 67, 70]
        _incomes  = [2000, 2500, 3000, 3500, 4000, 5000]
        _tbl_rows = []
        for _age in _ages:
            _row = [f"Age {_age}"]
            for _inc in _incomes:
                _gap  = max(_inc - pillar1_2, 0)
                _cap  = _gap * 12 / ret_swr if ret_swr > 0 else 0
                _ok   = projected_capital_at_ret >= _cap
                _cell = f"€{_cap/1e6:.2f}M" if _cap >= 1e6 else f"€{_cap:,.0f}"
                _row.append(("✅ " if _ok else "⚠️ ") + _cell)
            _tbl_rows.append(_row)

        _tbl_headers = [""] + [f"€{i:,}/mo" for i in _incomes]
        _cw_sens = [1.5] + [1.0] * len(_incomes)
        _cw_total = sum(_cw_sens)
        _cw_sens_norm = [c / _cw_total for c in _cw_sens]

        import pandas as _pd_ret
        _sens_df = _pd_ret.DataFrame(_tbl_rows, columns=_tbl_headers)
        st.dataframe(_sens_df, hide_index=True, use_container_width=True)

        # ── Dutch pension explanations ────────────────────────────────────────────
        st.divider()
        with st.expander("📚 Dutch Pension System Explained", expanded=False):
            st.markdown("""
    ### The Three Pillars of Dutch Retirement

    | Pillar | What | Who | Amount |
    |--------|------|-----|--------|
    | **1e pijler — AOW** | State pension | Everyone with 50 years Dutch residency | ~€1,450/mo (single), ~€1,000/mo each (couple) |
    | **2e pijler — Occupational** | Employer pension fund | Most employees | Depends on salary × accrual rate × years |
    | **3e pijler — Private** | Own savings / investments | You | Unlimited (Box 3 taxed) |

    ### AOW Calculation
    - Full AOW requires **50 years of residency** between ages 15 and 67.
    - Each missing year reduces AOW by **2%** (so 40 years = 80% of full AOW).
    - AOW age is currently **67**; expected to increase to 67y3mo in 2028.
    - Amount indexed annually; couples receive ~69% of single amount per person.

    ### Occupational Pension (2e pijler)
    - Most Dutch employees participate via their sector's pension fund (e.g. ABP, PFZW, PMT).
    - Under **WTP (Wet Toekomst Pensioenen, 2023)** all funds are transitioning to defined contribution.
    - Check **[mijnpensioenoverzicht.nl](https://www.mijnpensioenoverzicht.nl)** for your accrued pension.
    - Typical accrual: 1.5–1.875% of pensionable salary per year (salary minus AOW franchise ≈ €17,000).

    ### Safe Withdrawal Rate (SWR)
    - The **4% rule** (Bengen, 1994; Trinity Study) suggests withdrawing 4%/yr of your portfolio is sustainable for 30 years with a 50/50 stock-bond split.
    - For longer retirements (40–50 years) or all-equity, **3–3.5% is more conservative**.
    - Dutch context: Box 3 taxes on assets above €57,000 threshold reduce effective returns.

    ### Box 3 Tax on Investments
    - The Dutch tax authority assumes a fictitious return on assets above the threshold.
    - **2026 rates** (indicative): savings ≈ 1.44% fictitious return, investments ≈ 5.88%, taxed at **36%**.
    - This reduces your effective after-tax return on invested capital — factor this into your pre-retirement return assumption.

    ### Zorgtoeslag & AOW
    - AOW income counts toward the zorgtoeslag income test.
    - Full AOW recipients typically no longer qualify for zorgtoeslag.

    ### Vermogensopbouw Tips
    - **Lijfrente (annuity savings)**: tax-deductible up to the annual reservation margin (jaarruimte).
      - Jaarruimte = 30% × (income − AOW franchise) − pension accrual factor.
    - **Banksparen**: similar to lijfrente but bank-based, more flexible.
    - **Eigen woning**: home equity reduces the need for capital, but is illiquid.
            """)

        st.divider()
        st.caption(
            "⚠️ AOW amounts and rules as of 2026. Pension projections are illustrative — "
            "check mijnpensioenoverzicht.nl for your actual accrued pension. "
            "Tax treatment of Box 3 is subject to legislative change. "
            "This is not financial advice."
        )
