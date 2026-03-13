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

_HERE        = os.path.dirname(os.path.abspath(__file__))
SAVE_FILE    = os.path.join(_HERE, "dutch_dashboard_settings.csv")
ACTUALS_FILE = os.path.join(_HERE, "dutch_dashboard_actuals.csv")

DEFAULTS = dict(
    inc_s=72000, partner=True, inc_p=92000, sal_growth=0.0,
    sal_growth_p=0.0,
    ab_mode=False,
    rs=2026, re=2029,
    rs_s_start=2026, rs_p_start=2026,  # first year ruling was applied (drives rate schedule)                    # legacy (kept for CSV compat)
    ruling_s=True, rs_s=2026, re_s=2029, # your ruling
    ruling_p=False, rs_p=2026, re_p=2029, # partner ruling
    rent=1850, by=2026, bm=7,
    house_price=550000, dp=0.10, mort_rate=0.045, mort_type="Annuity (annuïteit)",
    hi=420, cf=100, ci=100, gr=400, ot=300,
    utilities=200, phone=50, subscriptions=50, gym=40, dog=150,
    savings=80000, n_years=5, ha=0.03, ir=0.05,
    global_inflation=0.0,
    sell_house=False, sy=2031, sm=1,
    n_kdv=0, n_bso=0, kdv_hrs=None, bso_hrs=None,   # kinderopvangtoeslag
    kdv_rate=None, bso_rate=None,
    kot_start_ym="2027-01", kot_end_ym="",
    future_expenses=[],
    exp_notes={},
    exp_growth={},
    hist_start="2026-01", hist_end="2026-03",
    net_worth_start=0,
    scenario_label="",
)

def load_settings():
    """Load scenario A & B settings from CSV. Returns (dict_A, dict_B)."""
    if not os.path.exists(SAVE_FILE):
        return DEFAULTS.copy(), DEFAULTS.copy()
    try:
        df = pd.read_csv(SAVE_FILE, index_col=0)
        def parse_row(col):
            d = DEFAULTS.copy()
            if col in df.columns:
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
                            # None-typed defaults (kdv_hrs, bso_hrs, kdv_rate, bso_rate):
                            # preserve None if the saved value is the string "null" or empty,
                            # otherwise store as float
                            if parsed is None or parsed == "" or parsed == "None":
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
                                d[k] = default_val  # fall back to default on bad data
            return d
        return parse_row("A"), parse_row("B")
    except Exception:
        return DEFAULTS.copy(), DEFAULTS.copy()

def save_settings(pa, pb):
    """Save scenario A & B dicts to CSV."""
    def _enc(v):
        if v is None:
            return json.dumps(None)           # saves as "null", round-trips cleanly
        if isinstance(v, (bool, list, dict)):
            return json.dumps(v)
        return v
    rows = {k: {"A": _enc(v), "B": _enc(pb.get(k, DEFAULTS.get(k)))}
            for k, v in pa.items()}
    pd.DataFrame(rows).T.to_csv(SAVE_FILE)

_ACTUALS_COLS = ["month", "inc_s_actual", "inc_p_actual", "savings_actual", "note"]

def load_actuals():
    empty = pd.DataFrame(columns=_ACTUALS_COLS)
    if not os.path.exists(ACTUALS_FILE):
        return empty
    try:
        df = pd.read_csv(ACTUALS_FILE)
        # Ensure all expected columns exist (backwards-compat with old files)
        for col in _ACTUALS_COLS:
            if col not in df.columns:
                df[col] = None
        extra = [c for c in df.columns if c not in _ACTUALS_COLS]
        return df[_ACTUALS_COLS + extra]
    except Exception:
        return empty

def save_actuals(df):
    df.to_csv(ACTUALS_FILE, index=False)

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
    max_w = "480px" if narrow else "100%"
    font_scale = "13px" if narrow else "inherit"
    metric_font = "0.85rem" if narrow else "inherit"
    st.markdown(f"""
<style>
/* ── Mobile / narrow mode ──────────────────────── */
.block-container {{
    max-width: {max_w};
    padding-left: 0.75rem;
    padding-right: 0.75rem;
}}
/* Scale down metric labels on narrow */
[data-testid="stMetricLabel"] {{ font-size: {metric_font}; }}
[data-testid="stMetricValue"] {{ font-size: {metric_font}; }}
/* Compact tab labels on narrow */
{"button[data-baseweb='tab'] { padding: 4px 6px !important; font-size: 11px !important; }" if narrow else ""}
/* Keep plotly charts from overflowing */
.js-plotly-plot {{ max-width: 100% !important; }}
/* Prevent wide tables from breaking layout */
[data-testid="stDataFrame"] {{ overflow-x: auto; }}
/* General font scale */
.main .block-container * {{ font-size: {font_scale}; }}
</style>
""", unsafe_allow_html=True)

# ── Theme ────────────────────────────────────────────────────────────────────────
DARK     = dict(plot_bgcolor="#0f1117", paper_bgcolor="#0f1117", font=dict(color="#e0e0e0"))
LEGEND_H = dict(orientation="h", y=-0.20, font=dict(size=11))

def chart_layout(title, yaxis_title="€", height=400, xaxis_title="", **kw):
    return dict(title=dict(text=title, font=dict(size=15)),
                xaxis_title=xaxis_title, yaxis_title=yaxis_title,
                legend=LEGEND_H, hovermode="x unified",
                height=height, **DARK, **kw)

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
    mp       = mort_payment(p["house_price"], p["dp"], p["mort_rate"])   # annuity fixed payment
    loan     = p["house_price"] * (1 - p["dp"])
    costs    = p["house_price"] * 0.02 + 3500   # overdrachtsbelasting + notaris

    mb        = loan
    buy_cash  = p["savings"]          # start with full savings; dp+costs deducted in purchase month
    rent_cash = p["savings"]
    mo_owned  = 0
    house_sold   = False   # latched True after sell event; prevents house reappearing
    purchase_done = False  # latched True once dp+costs have been deducted
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
            fig.add_annotation(x=rm[0].strftime("%Y-%m-%d"), y=0.97, xref="x", yref="paper",
                               text="30% ruling", showarrow=False, xanchor="left",
                               font=dict(color="#d4a017", size=10))
    prefix = f" {label}" if label else ""
    buy_str = pd.Timestamp(year=p["by"], month=p["bm"], day=1).strftime("%Y-%m-%d")
    fig.add_shape(type="line", x0=buy_str, x1=buy_str, y0=0, y1=1,
                  xref="x", yref="paper", line=dict(dash="dash", color=buy_color, width=1.5))
    fig.add_annotation(x=buy_str, y=buy_y, xref="x", yref="paper",
                       text=f"🏠{prefix}", showarrow=False, xanchor="left",
                       font=dict(color=buy_color, size=12))
    if p.get("sell_house", False):
        sell_str = pd.Timestamp(year=p.get("sy",2031), month=p.get("sm",1), day=1).strftime("%Y-%m-%d")
        fig.add_shape(type="line", x0=sell_str, x1=sell_str, y0=0, y1=1,
                      xref="x", yref="paper", line=dict(dash="dot", color=sell_color, width=1.5))
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

    # ── Mobile / narrow display toggle ───────────────────────────────────────
    st.markdown("### 📱 Display")
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
        "📋 **Data & Export** — raw tables & Excel download"
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
                "📝 Actuals", "📋 Data & Export"])

# ════════════════════════════════════════════════════════════════════════════════
# TAB 0 — SETUP
# ════════════════════════════════════════════════════════════════════════════════

with tabs[0]:
    st.subheader("⚙️ Scenario Setup")
    ab_mode = st.toggle("🔀 Enable Scenario B — compare two scenarios side-by-side",
                        value=bool(saved_A.get("ab_mode", False)), key="ab_mode_toggle")
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
    scen_cols = st.columns(2) if ab_mode else st.columns([1, 1])
    labels    = ["A", "B"] if ab_mode else ["A"]

    params = {}

    for idx, lbl in enumerate(labels):
        col = scen_cols[idx]

        with col:
            color = "#2ecc71" if lbl == "A" else "#3498db"
            _saved_slabel = (saved_A if lbl=="A" else saved_B).get("scenario_label", "")
            _scen_display = _saved_slabel if _saved_slabel else f"Scenario {lbl}"
            st.markdown(
                f"<h3 style='color:{color};margin-bottom:0'>{_scen_display}</h3>",
                unsafe_allow_html=True
            )
            scenario_label = st.text_input(
                "Scenario name (optional)", value=_saved_slabel,
                key=f"scen_label_{lbl}",
                placeholder="e.g. 'Buy 2026' or 'Rent longer'",
                help="Give this scenario a short name — shown on charts and the A/B comparison tab."
            )


            sv = saved_A if lbl == "A" else saved_B

            # ── Pre-compute collapsed-label summaries from saved values ────
            def _sv_net(sv_):
                """Combined net monthly income for the collapsed label, using saved values."""
                _a30s = sv_.get("ruling_s", True)  and sv_.get("rs_s", sv_.get("rs", 2026)) <= 2026 < sv_.get("re_s", sv_.get("re", 2029))
                _a30p = sv_.get("ruling_p", False) and sv_.get("rs_p", sv_.get("rs", 2026)) <= 2026 < sv_.get("re_p", sv_.get("re", 2029))
                _ns = net_monthly_calc(sv_.get("inc_s", 72000), 2026, _a30s)
                _np = net_monthly_calc(sv_.get("inc_p", 92000), 2026, _a30p) if sv_.get("partner", False) else 0
                return _ns + _np
            def _sv_fixed(sv_):
                return (sv_.get("hi",420) + sv_.get("cf",100) + sv_.get("ci",100)
                      + sv_.get("gr",400) + sv_.get("ot",300) + sv_.get("utilities",200)
                      + sv_.get("phone",50) + sv_.get("subscriptions",50)
                      + sv_.get("gym",40)   + sv_.get("dog",150))
            def _sv_mortgage(sv_):
                return mort_payment(sv_.get("house_price",550000), sv_.get("dp",0.10), sv_.get("mort_rate",0.045))
            def _sv_fe_total(sv_):
                return sum(fe.get("amount",0) for fe in sv_.get("future_expenses",[]))
            _lbl_income   = f"👤 People & Income — €{_sv_net(sv):,.0f}/mo net"
            def _sv_mri(sv_):
                try:
                    return amortisation_schedule(sv_.get("house_price",550000),
                        sv_.get("dp",0.10), sv_.get("mort_rate",0.045))["MRI_Benefit"].iloc[0]
                except Exception:
                    return 0
            _lbl_housing  = (f"🏠 Housing & Mortgage — "
                             f"€{sv.get('house_price',550000):,} · "
                             f"€{_sv_mortgage(sv):,.0f}/mo gross · "
                             f"€{_sv_mri(sv):,.0f}/mo MRI benefit · "
                             f"{sv.get('mort_rate',0.045)*100:.1f}% rate")
            _lbl_expenses = f"🧾 Monthly Expenses — €{_sv_fixed(sv):,.0f}/mo total"
            _lbl_proj     = f"📈 Projection Assumptions — {sv.get('n_years',5)}yr · {sv.get('ha',0.03)*100:.1f}% appreciation · {sv.get('ir',0.05)*100:.1f}% return"
            _lbl_future   = f"🍼 Future Recurring Expenses — {len(sv.get('future_expenses',[]))} item(s), €{_sv_fe_total(sv):,.0f}/mo at start"
            _lbl_hist     = f"📅 Historic Data Range — {sv.get('hist_start','2026-01')} → {sv.get('hist_end','2026-03')}"

            # ════════════════════════════════════════════════════════════════
            # 1 — PEOPLE & INCOME
            # ════════════════════════════════════════════════════════════════
            with st.expander(_lbl_income, expanded=False):
                c1, c2 = st.columns(2)
                inc_s = c1.number_input("Your gross income (€/yr)",
                    value=sv.get("inc_s", 72000), step=1000, key=f"inc_s_{lbl}",
                    help="Your annual gross salary before tax. Used to calculate Box 1 tax, ZVW, and all tax credits.")
                sal_growth = c2.slider("Annual salary growth (%)",
                    0.0, 10.0, sv.get("sal_growth", 0.0) * 100, 0.5, key=f"sg_{lbl}",
                    help="Compound annual salary growth from 2026. 2–3% tracks Dutch inflation and CAO agreements.") / 100

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
                ruling_s = st.checkbox("You have the 30% ruling",
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

                partner = st.checkbox("Include partner income",
                    value=sv.get("partner", True), key=f"pt_{lbl}")
                inc_p = 0
                sal_growth_p = 0.0   # default when no partner
                ruling_p, rs_p, re_p, rs_p_start = False, sv.get("rs_p", 2026), sv.get("re_p", 2029), sv.get("rs_p_start", 2026)
                if partner:
                    _pi1, _pi2 = st.columns(2)
                    inc_p = _pi1.number_input("Partner gross income (€/yr)",
                        value=sv.get("inc_p", 92000), step=1000, key=f"inc_p_{lbl}",
                        help="Partner's annual gross salary. Taxed independently — each person has their own brackets and credits.")
                    sal_growth_p = _pi2.slider("Partner salary growth (%)",
                        0.0, 10.0, sv.get("sal_growth_p", 0.0) * 100, 0.5, key=f"sg_p_{lbl}",
                        help="Compound annual salary growth for your partner from 2026. Can differ from yours if on a different career trajectory or CAO.") / 100

                    # ── Partner 30% ruling ───────────────────────────────────
                    st.markdown("**30% Ruling — Partner**")
                    ruling_p = st.checkbox("Partner has the 30% ruling",
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
            with st.expander(_lbl_housing, expanded=False):

                rent = st.number_input("Current rent (€/mo)",
                    value=sv.get("rent", 1850), step=50, key=f"rent_{lbl}",
                    help="Monthly rent before buying, and the ongoing cost in the Rent scenario throughout. Include service costs.")

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

                st.markdown("**🏡 Property**")
                house_price = st.number_input("House price (€)",
                    value=sv.get("house_price", 550000), step=5000, key=f"hp_{lbl}",
                    help="Total purchase price. Buying costs (2% overdrachtsbelasting + ~€3,500 notaris) are added automatically.")

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
            with st.expander(_lbl_expenses, expanded=False):
                eg    = sv.get("exp_growth", {})
                en    = sv.get("exp_notes",  {})   # per-category free-text notes
                def _eg_get(key, default=0.02):
                    return float(eg.get(key, default)) if isinstance(eg, dict) else default
                def _en_get(key):
                    return str(en.get(key, "")) if isinstance(en, dict) else ""

                # ── Column header row ──────────────────────────────────────────
                # 4 columns: Category name | €/mo input | %/yr input | Note
                _COLS = [2.6, 0.85, 0.85, 2.3]
                _hc = st.columns(_COLS)
                _hc[0].markdown("**Category**")
                _hc[1].markdown("**€ /mo**")
                _hc[2].markdown("**% /yr**")
                _hc[3].markdown("**Note**")

                def _exp_row(label, key, val, step, growth_default, growth_help, note_placeholder=""):
                    """Render one aligned expense row: label | €/mo | %/yr | note"""
                    rc = st.columns(_COLS)
                    rc[0].markdown(f"<div style='padding-top:8px'>{label}</div>", unsafe_allow_html=True)
                    amount = rc[1].number_input("€", value=float(val), step=float(step),
                        key=f"{key}_{lbl}", label_visibility="collapsed")
                    growth = rc[2].number_input("%", value=round(_eg_get(key, growth_default)*100, 1),
                        step=0.5, key=f"{key}_g_{lbl}",
                        help=growth_help, label_visibility="collapsed") / 100
                    note = rc[3].text_input("n", value=_en_get(key),
                        key=f"{key}_note_{lbl}",
                        placeholder=note_placeholder,
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
            with st.expander(_lbl_proj, expanded=False):
                w1, w2 = st.columns(2)
                savings = w1.number_input("Starting savings (€)",
                    value=sv.get("savings", 80000), step=5000, key=f"sv_{lbl}",
                    help="Total liquid savings at January 2026. Down payment and buying costs are deducted on the purchase date.")
                n_years = w2.slider("Projection years", 3, 15, sv.get("n_years", 5), key=f"ny_{lbl}",
                    help="How many years to project from January 2026. The Mortgage tab always shows the full 30-year schedule.")
                w3, w4 = st.columns(2)
                ha = w3.slider("House appreciation (%/yr)", 0.0, 8.0, sv.get("ha", 0.03) * 100, 0.5,
                    key=f"ha_{lbl}",
                    help="Annual house price growth. Long-run Dutch average ~2–4%; recent years 5–8%.") / 100
                ir = w4.slider("Investment return (%/yr)", 0.0, 10.0, sv.get("ir", 0.05) * 100, 0.5,
                    key=f"ir_{lbl}",
                    help="Annual return on savings/investments. Global index ETF historically ~7–9%/yr pre-tax.") / 100
                w5, w6 = st.columns(2)
                global_inflation = w5.slider("Global inflation floor (%/yr)", 0.0, 5.0,
                    sv.get("global_inflation", 0.0) * 100, 0.25,
                    key=f"gi_{lbl}",
                    help="Sets a minimum annual growth rate for ALL expense categories. Any category with a lower per-item rate will be raised to this floor. "
                         "0% = use per-category rates only. 2.5% = Dutch CPI baseline.") / 100
                net_worth_start = w6.number_input("Starting net worth (€)",
                    value=sv.get("net_worth_start", 0), step=5000, key=f"nws_{lbl}",
                    help="Your total net worth at Jan 2026, including savings, investments, pension value, etc. Used to track actual net worth over time in the 📝 Actuals tab.")

            # ════════════════════════════════════════════════════════════════
            # 6 — FUTURE RECURRING EXPENSES
            # ════════════════════════════════════════════════════════════════
            with st.expander(_lbl_future, expanded=False):
                st.caption(
                    "Add costs that don't exist yet but will start on a future date — "
                    "baby/childcare, school fees, a second car, etc. "
                    "Each is added to Fixed Expenses from its start month, compounding at its own growth rate."
                )
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
            # 7 — HISTORIC DATA RANGE (ACTUALS)
            # ════════════════════════════════════════════════════════════════
            with st.expander(_lbl_hist, expanded=False):
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
                inc_s=inc_s, partner=partner, inc_p=inc_p,
                n_kdv=n_kdv, n_bso=n_bso, kdv_hrs=kdv_hrs, bso_hrs=bso_hrs,
                kdv_rate=kdv_rate, bso_rate=bso_rate,
                sal_growth=sal_growth, sal_growth_p=sal_growth_p,
                rs=rs, re=re,
                ruling_s=ruling_s, rs_s=rs_s, re_s=re_s, rs_s_start=rs_s_start,
                ruling_p=ruling_p, rs_p=rs_p, re_p=re_p, rs_p_start=rs_p_start,
                rent=rent, by=by, bm=bm,
                house_price=house_price, dp=dp, mort_rate=mr,
                mort_type=mort_type,
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
                net_worth_start=net_worth_start,
                scenario_label=scenario_label,
            )

    # ── If B not shown, copy A as placeholder ────────────────────────────────
    if "B" not in params:
        params["B"] = params["A"].copy()

    # ── Live summary cards ───────────────────────────────────────────────────
    st.divider()
    st.markdown("### 📌 Quick Summary")
    sum_cols = st.columns(2) if ab_mode else [st.columns(1)[0]]

    for idx, lbl in enumerate(labels):
        p = params[lbl]
        _a30_s0 = p.get("ruling_s", True)  and p.get("rs_s", p["rs"]) <= 2026 < p.get("re_s", p["re"])
        _a30_p0 = p.get("ruling_p", False) and p.get("rs_p", p["rs"]) <= 2026 < p.get("re_p", p["re"])
        net_s = net_monthly_calc(p["inc_s"], 2026, _a30_s0)
        net_p = net_monthly_calc(p["inc_p"], 2026, _a30_p0) if p["partner"] else 0
        n_p   = 2 if p["partner"] else 1
        # Jan 2026 snapshot — no growth applied (yrs_e = 0)
        fixed = (p["hi"] + p["cf"] + p["ci"] + p["gr"] + p["ot"]
                 + p.get("utilities",0) + p.get("phone",0)
                 + p.get("subscriptions",0) + p.get("gym",0) + p.get("dog",0))
        mp    = mort_payment(p["house_price"], p["dp"], p["mort_rate"])
        with (sum_cols[idx] if ab_mode else sum_cols[0]):
            color = "#2ecc71" if lbl == "A" else "#3498db"
            _qs_name = p.get("scenario_label") or f"Scenario {lbl}"
            st.markdown(f"<b style='color:{color}'>{_qs_name} — Jan 2026 snapshot</b>",
                        unsafe_allow_html=True)
            sc1, sc2, sc3, sc4 = st.columns(4)
            sc1.metric("Net Income/mo", f"€{net_s+net_p:,.0f}")
            sc2.metric("Fixed Expenses/mo", f"€{fixed:,.0f}")
            sc3.metric("Rent/mo", f"€{p['rent']:,.0f}")
            sc4.metric("Future Mortgage/mo", f"€{mp:,.0f}")

    # ── Save button ──────────────────────────────────────────────────────
    st.divider()
    sav_col, info_col = st.columns([1, 3])
    if sav_col.button("💾 Save Settings to CSV", type="primary", use_container_width=True):
        save_settings(params["A"], params["B"])
        st.success(f"✅ Settings saved to `{SAVE_FILE}` — they will reload automatically next run.")
    if os.path.exists(SAVE_FILE):
        info_col.info(f"📂 Settings loaded from `{SAVE_FILE}`. Edit above and click Save to update.", icon="ℹ️")
    else:
        info_col.caption("No saved settings found — using defaults. Click **Save** to persist your inputs.")

# ════════════════════════════════════════════════════════════════════════════════
# RUN SIMULATIONS (after Setup tab so params are defined)
# ════════════════════════════════════════════════════════════════════════════════

pa = params["A"]
pb = params["B"]

df_m_a, df_w_a = run_sim(pa)
df_m_b, df_w_b = run_sim(pb)

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
- The **30% ruling** shaded band shows the period where 70% of gross is taxed — the yellow bar chart shows the monthly benefit per year
- **Zorgtoeslag** is subtracted as an income credit from your expenses
- The **tax breakdown table** at the bottom shows exact numbers for both ruling-on and ruling-off scenarios
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
        st.error(
            "⚠️ **30% Ruling expiry impact** — " + "  |  ".join(_banner_parts) +
            f"  |  Combined household drop: **−€{_combined_drop:,.0f}/mo (−€{_combined_drop*12:,.0f}/yr)**. "
            "Plan ahead: build savings during the ruling period to absorb this income drop.",
            icon="📉"
        )
        with st.expander("📐 How is this calculated?", expanded=False):
            _tbl_md = "| Person | Last ruling year | First post-ruling year | Monthly change |\n|---|---|---|---|\n"
            _tbl_md += "\n".join(_table_rows)
            st.markdown(_tbl_md)
            st.markdown("💡 During the ruling period, save the difference each month. Make sure your post-ruling net income still covers your mortgage payments.")
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
    # Use 3 metrics per row, stacked neatly — works on mobile and desktop
    _km1, _km2, _km3 = st.columns(3)
    _km1.metric("💰 Net Income",     f"€{cur_net:,.0f}",
        help=f"Combined household net income in {cur_lbl} after Box 1 tax, ZVW, AHK, and arbeidskorting.")
    _km2.metric("💸 Total Expenses", f"€{cur_exp:,.0f}",
        help=f"All fixed expenses in {cur_lbl}: housing, categories from Setup, net of MRI and subsidy credits.")
    _sav_sign = "surplus" if cur_sav >= 0 else "deficit"
    _km3.metric("🏦 Monthly Savings", f"€{cur_sav:,.0f}",
        delta=_sav_sign, delta_color="normal" if cur_sav >= 0 else "inverse",
        help=f"Net income minus total expenses in {cur_lbl}.")
    _km4, _km5, _km6 = st.columns(3)
    _km4.metric("🎯 30% Ruling Benefit", f"€{cur_ruling_ben:,.0f}",
        help="Extra net income this month because only 70% of gross is taxable. Drops to zero when ruling expires.")
    _km5.metric("🏥 Zorgtoeslag", f"€{cur_zts:,.0f}",
        help="Monthly Dutch government health insurance subsidy, income-tested.")
    if _has_kot:
        _km6.metric("👶 Kinderopvangtoeslag", f"€{cur_kot:,.0f}",
            help="Monthly childcare benefit (dagopvang/BSO), income-tested.")
    else:
        _km6.metric("📅 Period", cur_lbl, help="Current month shown in the KPIs above.")

    st.divider()

    # ── Actuals overlay toggle ─────────────────────────────────────────────────
    show_actuals_overlay = st.toggle(
        "📌 Overlay actuals data on chart",
        value=True,
        key="income_tax_actuals_toggle",
        help="Shows actual income and savings from the 📝 Actuals tab on top of the forecast lines. "
             "Enter data in the Actuals tab first."
    )

    # Load actuals for overlay
    _act_overlay = load_actuals()
    _has_overlay_data = (show_actuals_overlay and not _act_overlay.empty
                         and "month" in _act_overlay.columns)

    if show_actuals_overlay and not _has_overlay_data:
        st.caption("ℹ️ No actuals data found — enter data in the 📝 Actuals tab first.")

    fig1 = go.Figure()
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Total Net"], name="Forecast Net Income",
                              line=dict(color="#2ecc71", width=2.5),
                              fill="tozeroy", fillcolor="rgba(46,204,113,0.07)"))
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Total Expenses"], name="Forecast Expenses",
                              line=dict(color="#e74c3c", width=2.5),
                              fill="tozeroy", fillcolor="rgba(231,76,60,0.07)"))
    fig1.add_trace(go.Scatter(x=df["Date"], y=df["Net Saving"], name="Forecast Savings",
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
                name="Actual Income (combined)",
                mode="lines+markers",
                line=dict(color="#27ae60", width=2.5),
                marker=dict(size=7, symbol="circle"),
            ))
            # If partner: also show individual lines
            if p.get("partner") and _ov["inc_s_actual"].notna().any():
                _ov_s = _ov.dropna(subset=["inc_s_actual"])
                fig1.add_trace(go.Scatter(
                    x=_ov_s["month_dt"], y=_ov_s["inc_s_actual"],
                    name=f"Actual Income — {p.get('name_s','You')}",
                    mode="lines+markers",
                    line=dict(color="#2ecc71", width=1.5, dash="dot"),
                    marker=dict(size=5, symbol="circle-open"),
                ))
            if p.get("partner") and _ov["inc_p_actual"].notna().any():
                _ov_p = _ov.dropna(subset=["inc_p_actual"])
                fig1.add_trace(go.Scatter(
                    x=_ov_p["month_dt"], y=_ov_p["inc_p_actual"],
                    name=f"Actual Income — {p.get('name_p','Partner')}",
                    mode="lines+markers",
                    line=dict(color="#f1c40f", width=1.5, dash="dot"),
                    marker=dict(size=5, symbol="circle-open"),
                ))
        if not _ov_sav.empty:
            fig1.add_trace(go.Scatter(
                x=_ov_sav["month_dt"], y=_ov_sav["savings_actual"],
                name="Actual Savings",
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
        fig1.add_annotation(x=_fe_xs, y=0.60 - (_fi * 0.09), xref="x", yref="paper",
                            text=f"💸 {_fe['name']}", showarrow=False,
                            xanchor="left", font=dict(color=_fe_col, size=10))
    fig1.update_layout(**chart_layout("Monthly Income vs Expenses — Forecast" +
                                      (" + Actuals" if _has_overlay_data else ""), height=420))
    st.plotly_chart(fig1, use_container_width=True, key="fig_income_tax_1")

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

    with st.expander("🧮 Tax Breakdown — Ruling On vs Off", expanded=False):
        pb2 = {"You": p["inc_s"]}
        if p["partner"]: pb2["Partner"] = p["inc_p"]
        tbl2 = []
        _rf = {"You": p.get("ruling_s", True), "Partner": p.get("ruling_p", False)}
        for name, base_gross in pb2.items():
            _has_r = _rf.get(name, False)
            _scens = [(2026, _has_r), (min(2029, 2026 + p.get("n_years", 5) - 1), False)] if _has_r else [(2026, False)]
            for yr, a30 in _scens:
                gross = base_gross * (1 + sg) ** (yr - 2026)
                t   = income_tax(gross, yr, a30)
                ah  = ahk(gross, yr); kk = ak(gross, yr); z = zvw(gross, a30)
                net = net_annual_calc(gross, yr, a30)
                _lbl_r = "ruling on" if a30 else "ruling off"
                tbl2.append({"Person/Year": f"{name} {yr} ({_lbl_r})",
                    "Gross": f"€{gross:,.0f}", "Income Tax": f"€{t:,.0f}",
                    "AHK": f"€{ah:,.0f}", "Arbeidskorting": f"€{kk:,.0f}",
                    "ZVW": f"€{z:,.0f}", "Net Annual": f"€{net:,.0f}",
                    "Net Monthly": f"€{net/12:,.0f}",
                    "Effective Rate": f"{(gross-net)/gross*100:.1f}%"})
        st.dataframe(pd.DataFrame(tbl2), use_container_width=True, hide_index=True)

    # ── How are these numbers calculated? (bottom of tab) ─────────────────────
    st.divider()
    with st.expander("📖 How are these numbers calculated?", expanded=False):
        st.markdown("""
### Dutch Income Tax Components (Box 1)

| Component | Description |
|-----------|-------------|
| **Box 1 income tax** | Progressive tax on earned income. Rate 1 is **36.97%** on the first ~€38,441 (2026), rate 2 is **49.50%** above that threshold. Thresholds are indexed annually. |
| **Algemene heffingskorting (AHK)** | General tax credit of up to **€3,362/yr** (2026), phasing out linearly between ~€24,800 and ~€75,500 gross. Reduces your final tax bill directly. |
| **Arbeidskorting (AK)** | Labour tax credit of up to **€5,052/yr** (2026), phasing out between ~€38,100 and ~€124,900 gross. Rewards working over non-working income. |
| **ZVW** | Income-dependent healthcare contribution of **5.65%** on gross (capped at ~€71,628). Paid on top of your health insurance premium. |
| **30% ruling** | Eligible expats pay tax on only **70% of gross** (or 73% from 2027 starters). This affects Box 1, ZVW, and AHK/AK phase-outs. Duration is always 5 years. Rate drops from 30% to 27% from 2027 for 2024–2026 starters. |
| **Hypotheekrenteaftrek (MRI)** | Mortgage interest is deductible from Box 1 taxable income at **36.97%**. The monthly tax saving equals monthly interest × 36.97%. Benefit decreases as the mortgage balance falls. |
| **Zorgtoeslag** | Government health insurance subsidy, income-tested. Couples with combined gross above ~€45,000 receive little or none. Computed monthly and treated as an income credit. |
| **Kinderopvangtoeslag** | Childcare benefit for *dagopvang* (0–4 yrs) and *BSO* (4–12 yrs). Income-tested, covering up to 96% of the government-capped hourly rate multiplied by your hours. |
| **Box 3 wealth tax** | Annual tax on net assets above €57,000/person. Fictitious return rates: ~1.54% on savings, higher on investments. Taxed at **36%** of that fictitious return. |

### How net monthly income is calculated

```
Gross annual salary
  − Box 1 income tax (after AHK and AK credits)
  − ZVW contribution
= Net annual income
÷ 12
= Net monthly income
```

The **30% ruling** reduces taxable income before Box 1 and ZVW are applied, so the benefit compounds across all three components.

### Why do the KPI numbers change each year?

Salary growth (if set in Setup), ruling expiry, and annual tax bracket indexation all cause the numbers to shift year-by-year. The KPIs always show the **current calendar month** within the projection.
        """)

# ════════════════════════════════════════════════════════════════════════════════
# TAB 2 — BUY VS RENT
# ════════════════════════════════════════════════════════════════════════════════

with tabs[2]:
    dw = df_w_a; p = pa; fin = dw.iloc[-1]

    # ── Crossover: find when buying overtakes renting ────────────────────────
    crossover_row = dw[dw["Wealth Delta"] > 0].head(1)
    if not crossover_row.empty:
        cx_date   = crossover_row["Date"].iloc[0]
        cx_months = int((cx_date - pd.Timestamp("2026-01-01")).days / 30.44)
        cx_years  = cx_months / 12
        buy_date_ts = pd.Timestamp(year=p["by"], month=p["bm"], day=1)
        months_from_purchase = int((cx_date - buy_date_ts).days / 30.44)
        yrs_from_purchase    = months_from_purchase / 12
        st.success(
            f"🏆 **Buying overtakes renting after {cx_years:.1f} years** from Jan 2026 "
            f"— that's **{yrs_from_purchase:.1f} years after purchase** "
            f"(around **{cx_date.strftime('%B %Y')}**). "
            f"After that point the buy scenario builds more wealth every month.",
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
    kpi(k4, "Home Equity (final)", fin["Home Equity"])
    if sell_summary:
        k5.metric("Sale Net Proceeds", f"€{sell_summary['proceeds']:,.0f}",
                  help=f"Sale price minus mortgage payoff and selling costs on {sell_summary['date'].strftime('%b %Y')}")
    else:
        k5.metric("Projection End", dw["Date"].iloc[-1].strftime("%b %Y"))

    # ── Sell event breakdown panel ────────────────────────────────────────────
    if sell_summary:
        sell_years = (sell_summary["date"] - pd.Timestamp(year=p["by"], month=p["bm"], day=1)).days / 365.25
        with st.expander(f"🏷️ House Sale Breakdown — {sell_summary['date'].strftime('%B %Y')} "
                         f"({sell_years:.1f} years after purchase)", expanded=True):
            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            sc1.metric("Sale Price (market value)", f"€{sell_summary['hv']:,.0f}",
                       help="Appreciated house value at time of sale based on the annual appreciation rate in Setup.")
            sc2.metric("Mortgage Payoff", f"−€{sell_summary['mb']:,.0f}",
                       help="Outstanding mortgage balance that must be repaid to the bank on the settlement date.")
            sc3.metric("Selling Costs", f"−€{sell_summary['costs']:,.0f}",
                       help="Estimated selling costs: ~1.5% estate agent (makelaar) fee plus €2,500 fixed costs (notaris, valuatie, etc.).")
            sc4.metric("Net Proceeds to You", f"€{sell_summary['proceeds']:,.0f}",
                       help="Sale price minus mortgage payoff and selling costs. This amount is added to your investable cash.")
            equity_gain = sell_summary["hv"] - p["house_price"] * (1 - p["dp"]) - sell_summary["mb"]
            sc5.metric("Equity Gained vs Purchase", f"€{sell_summary['hv'] - p['house_price']:,.0f}",
                       help=f"House value appreciation since purchase: Sale price €{sell_summary['hv']:,.0f} minus original purchase price €{p['house_price']:,.0f}.")

            # Waterfall: Purchase Price → +Appreciation → −Mortgage → −Selling Costs → Net Proceeds
            _purchase_price = p["house_price"]
            _appreciation   = sell_summary["hv"] - _purchase_price
            fig_sell = go.Figure(go.Waterfall(
                orientation="v",
                measure=["absolute", "relative", "relative", "relative", "total"],
                x=["Purchase Price", "Appreciation", "Mortgage Payoff", "Selling Costs", "Net Proceeds"],
                y=[_purchase_price, _appreciation, -sell_summary["mb"], -sell_summary["costs"], 0],
                connector=dict(line=dict(color="rgba(255,255,255,0.3)")),
                increasing=dict(marker_color="#2ecc71"),
                decreasing=dict(marker_color="#e74c3c"),
                totals=dict(marker_color="#3498db"),
                text=[f"€{_purchase_price:,.0f}",
                      f"+€{_appreciation:,.0f}",
                      f"−€{sell_summary['mb']:,.0f}",
                      f"−€{sell_summary['costs']:,.0f}",
                      f"€{sell_summary['proceeds']:,.0f}"],
                textposition="outside",
            ))
            fig_sell.update_layout(**chart_layout(
                f"House Sale Waterfall — {sell_summary['date'].strftime('%B %Y')}",
                yaxis_title="€", height=400))
            st.plotly_chart(fig_sell, use_container_width=True, key="fig_sell_waterfall")

    with st.expander("ℹ️ What does this tab show & how is wealth calculated?", expanded=False):
        _buying_costs_exp = pa["house_price"] * 0.02 + 3500
        st.markdown(f"""
🏠 **Total wealth accumulation comparing buying vs renting**, using Scenario A inputs.

**Buy scenario:** On the purchase date, the down payment (€{pa['house_price']*pa['dp']:,.0f}) converts directly into home equity — so wealth is unchanged by the down payment itself. However, buying costs (2% overdrachtsbelasting = €{pa['house_price']*0.02:,.0f} + ~€3,500 notaris) are a pure loss, so **total wealth dips by ~€{_buying_costs_exp:,.0f} at purchase** — this is the visible drop on the chart at the 🏠 marker. After that, equity builds monthly as you repay principal and the house appreciates.

**Rent scenario:** Full savings invested from day 1. You pay rent throughout. Monthly surplus also invested. No home equity.

Both scenarios are subject to **Box 3** wealth tax on savings above €57k/person per year.

If you've enabled a **sell date**, net proceeds (sale price minus mortgage payoff and ~1.5% + €2,500 selling costs) are added to cash. The mortgage is fully repaid at that point.
        """)

    st.divider()

    fig5 = go.Figure()
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Total Wealth (Buy)"],
                              name="Total Wealth (Buy) ★", line=dict(color="#2ecc71", width=4)))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Total Wealth (Rent)"],
                              name="Total Wealth (Rent)", line=dict(color="#e74c3c", width=3)))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Home Equity"],
                              name="Home Equity", line=dict(color="#f1c40f", width=2, dash="dot")))
    fig5.add_trace(go.Scatter(x=dw["Date"], y=dw["Cash (Buy)"],
                              name="Cash (Buy)", line=dict(color="#3498db", width=1.5, dash="dash")))
    add_events(fig5, p)
    if not crossover_row.empty:
        cx_str = cx_date.strftime("%Y-%m-%d")
        fig5.add_shape(type="line", x0=cx_str, x1=cx_str, y0=0, y1=1,
                       xref="x", yref="paper",
                       line=dict(dash="dot", color="#f1c40f", width=2))
        fig5.add_annotation(x=cx_str, y=0.75, xref="x", yref="paper",
                            text=f"🏆 Buy leads<br>{cx_date.strftime('%b %Y')}",
                            showarrow=False, xanchor="left",
                            font=dict(color="#f1c40f", size=11))
    if sell_summary:
        sell_str = sell_summary["date"].strftime("%Y-%m-%d")
        fig5.add_shape(type="line", x0=sell_str, x1=sell_str, y0=0, y1=1,
                       xref="x", yref="paper", line=dict(dash="dot", color="#e74c3c", width=2))
        fig5.add_annotation(x=sell_str, y=0.60, xref="x", yref="paper",
                            text=f"🏷️ Sold<br>€{sell_summary['hv']:,.0f}<br>Net: €{sell_summary['proceeds']:,.0f}",
                            showarrow=False, xanchor="left",
                            font=dict(color="#e74c3c", size=10),
                            bgcolor="rgba(15,17,23,0.7)", bordercolor="#e74c3c", borderwidth=1)
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
                              line=dict(color="#2ecc71", width=1), name="Buy leads"))
    fig6.add_trace(go.Scatter(x=dw["Date"], y=dv.clip(upper=0),
                              fill="tozeroy", fillcolor="rgba(231,76,60,0.20)",
                              line=dict(color="#e74c3c", width=1), name="Rent leads"))
    fig6.add_trace(go.Scatter(x=dw["Date"], y=dv,
                              line=dict(color="white", width=1.5), name="Delta", showlegend=False))
    fig6.add_hline(y=0, line_color="gray", line_dash="dot")
    fig6.update_layout(**chart_layout("Wealth Gap (Buy − Rent)", height=360))
    cl.plotly_chart(fig6, use_container_width=True, key="fig_bvr_6")

    daw = dw.groupby("Year").last().reset_index()
    fig7 = go.Figure()
    fig7.add_trace(go.Bar(x=daw["Year"], y=daw["Home Equity"],
                          name="Home Equity", marker_color="#f1c40f"))
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
            name="House Value Appreciation",
            line=dict(color="#2ecc71", width=2.5),
            fill="tozeroy", fillcolor="rgba(46,204,113,0.08)"
        ))
        fig_be.add_trace(go.Scatter(
            x=_be_df["Date"], y=_be_df["Total Tx Costs"],
            name="Total Transaction Costs (buy + sell)",
            line=dict(color="#e74c3c", width=2, dash="dash")
        ))
        if not _breakeven_row.empty:
            _be_str = _be_date.strftime("%Y-%m-%d")
            fig_be.add_shape(type="line", x0=_be_str, x1=_be_str, y0=0, y1=1,
                             xref="x", yref="paper",
                             line=dict(color="#f1c40f", dash="dot", width=2))
            fig_be.add_annotation(x=_be_str, y=0.85, xref="x", yref="paper",
                                  text=f"✅ Breakeven<br>{_be_date.strftime('%b %Y')}",
                                  showarrow=False, xanchor="left",
                                  font=dict(color="#f1c40f", size=11))
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
    st.subheader("🏦 Mortgage Analysis — Annuity vs Linear")
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
                                name="Annuity — Gross", line=dict(color="#3498db", width=2)))
    fig_m1.add_trace(go.Scatter(x=df_ann_proj["Date"], y=df_ann_proj["Net_Payment"],
                                name="Annuity — Net (after MRI)", line=dict(color="#2ecc71", width=2)))
    fig_m1.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["Payment"],
                                name="Linear — Gross", line=dict(color="#e67e22", width=2, dash="dash")))
    fig_m1.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["Net_Payment"],
                                name="Linear — Net (after MRI)", line=dict(color="#f1c40f", width=2, dash="dash")))
    fig_m1.update_layout(**chart_layout(
        "Monthly Mortgage Payment: Gross vs Net (after Hypotheekrenteaftrek)", height=420))
    st.plotly_chart(fig_m1, use_container_width=True, key="fig_mort_1")

    cl, cr = st.columns(2)

    # ── Chart 2: Monthly MRI tax benefit ────────────────────────────────────
    fig_m2 = go.Figure()
    fig_m2.add_trace(go.Scatter(x=df_ann_proj["Date"], y=df_ann_proj["MRI_Benefit"],
                                name="MRI Benefit — Annuity",
                                fill="tozeroy", fillcolor="rgba(52,152,219,0.15)",
                                line=dict(color="#3498db", width=2)))
    fig_m2.add_trace(go.Scatter(x=df_lin_proj["Date"], y=df_lin_proj["MRI_Benefit"],
                                name="MRI Benefit — Linear",
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
                                name="Balance — Annuity", line=dict(color="#3498db", width=2)))
    fig_m4.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["Balance"],
                                name="Balance — Linear", line=dict(color="#e67e22", width=2, dash="dash")))
    proj_end = df_ann_proj["Date"].iloc[-1].strftime("%Y-%m-%d")
    fig_m4.add_shape(type="rect",
                     x0=df_ann["Date"].iloc[0].strftime("%Y-%m-%d"), x1=proj_end,
                     y0=0, y1=loan_amount, xref="x", yref="y",
                     fillcolor="rgba(255,255,255,0.03)", line_width=0)
    fig_m4.add_annotation(x=proj_end, y=loan_amount * 0.95, xref="x", yref="y",
                           text="← projection window", showarrow=False,
                           xanchor="right", font=dict(color="#aaa", size=10))
    fig_m4.update_layout(**chart_layout(
        "Outstanding Mortgage Balance (30yr full term)", height=360))
    cl2.plotly_chart(fig_m4, use_container_width=True, key="fig_mort_4")

    # ── Chart 5: Cumulative MRI vs interest ─────────────────────────────────
    fig_m5 = go.Figure()
    fig_m5.add_trace(go.Scatter(x=df_ann["Date"], y=df_ann["MRI_Benefit"].cumsum(),
                                name="Cumul. MRI — Annuity", line=dict(color="#2ecc71", width=2)))
    fig_m5.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["MRI_Benefit"].cumsum(),
                                name="Cumul. MRI — Linear",
                                line=dict(color="#f1c40f", width=2, dash="dash")))
    fig_m5.add_trace(go.Scatter(x=df_ann["Date"], y=df_ann["Interest"].cumsum(),
                                name="Cumul. Interest — Annuity",
                                line=dict(color="#e74c3c", width=1.5, dash="dot")))
    fig_m5.add_trace(go.Scatter(x=df_lin["Date"], y=df_lin["Interest"].cumsum(),
                                name="Cumul. Interest — Linear",
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

# TAB 3 — SCENARIO A/B
# ════════════════════════════════════════════════════════════════════════════════

with tabs[4]:
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
            ("Net worth start",      lambda p: f"€{p.get('net_worth_start',0):,.0f}"),
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
# TAB 5 — ACTUALS
# ════════════════════════════════════════════════════════════════════════════════

with tabs[5]:
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
    btn_col1, btn_col2, btn_col3 = st.columns([2, 2, 6])
    with btn_col1:
        if st.button("➕ Add Month", help="Unlock one more future month for data entry"):
            st.session_state["act_extra_months"] += 1
            st.rerun()
    with btn_col2:
        if st.button("💾 Save Actuals", type="primary"):
            # Build a DataFrame from what the user has typed in the widgets
            widget_df = pd.DataFrame(updated_rows)
            for _c in ["inc_s_actual", "inc_p_actual", "savings_actual"]:
                widget_df[_c] = pd.to_numeric(widget_df[_c], errors="coerce")

            # Load whatever is already on disk (could contain months outside the
            # current date-range window that are not shown in the grid)
            existing = load_actuals()

            # Merge: widget values take priority for any month that appears in both
            if existing.empty or "month" not in existing.columns:
                merged = widget_df.copy()
            else:
                # Keep disk rows for months not in the current window
                off_screen = existing[~existing["month"].isin(widget_df["month"])]
                # Update on-screen rows: start from widget values, fill note from
                # existing when widget note is blank and disk has one
                on_screen = widget_df.copy()
                if "note" in existing.columns:
                    disk_notes = existing.set_index("month")["note"]
                    on_screen["note"] = on_screen.apply(
                        lambda r: (disk_notes.get(r["month"], "") or "")
                        if not r["note"] else r["note"],
                        axis=1,
                    )
                merged = pd.concat([off_screen, on_screen], ignore_index=True)

            # Drop completely empty rows (no income and no savings entered at all)
            merged = merged[
                merged["inc_s_actual"].notna() |
                merged["inc_p_actual"].notna() |
                merged["savings_actual"].notna()
            ]
            merged = merged.sort_values("month").reset_index(drop=True)
            save_actuals(merged)
            st.success(f"✅ Saved {len(merged)} months to `{ACTUALS_FILE}`")
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
                                    name=f"Forecast {p_act.get('name_s','You')}",
                                    marker_color="#3498db", opacity=0.45))
            fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"], y=_months_with_inc["fc_inc_p"],
                                    name=f"Forecast {p_act.get('name_p','Partner')}",
                                    marker_color="#8e44ad", opacity=0.45))
            if actual_data["inc_s_actual"].notna().any():
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                        y=_months_with_inc["inc_s_actual"],
                                        name=f"Actual {p_act.get('name_s','You')}",
                                        marker_color="#2ecc71"))
            if actual_data["inc_p_actual"].notna().any():
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                        y=_months_with_inc["inc_p_actual"],
                                        name=f"Actual {p_act.get('name_p','Partner')}",
                                        marker_color="#f1c40f"))
            fig_a0.update_layout(barmode="group",
                                  **chart_layout("Monthly Income per Person: Actual vs Forecast",
                                                 height=340))
        else:
            _months_with_inc = actual_data[actual_data["inc_s_actual"].notna()]
            fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"], y=_months_with_inc["fc_inc_s"],
                                    name="Forecast Income", marker_color="#3498db", opacity=0.5))
            if actual_data["inc_s_actual"].notna().any():
                fig_a0.add_trace(go.Bar(x=_months_with_inc["month_dt"],
                                        y=_months_with_inc["inc_s_actual"],
                                        name="Actual Income", marker_color="#2ecc71"))
            fig_a0.update_layout(barmode="overlay",
                                  **chart_layout("Monthly Income: Actual vs Forecast", height=340))
        cl.plotly_chart(fig_a0, use_container_width=True, key="fig_act_0")

        # ── Chart 2: Savings actual vs forecast ──────────────────────────────
        fig_a1 = go.Figure()
        fig_a1.add_trace(go.Bar(x=a_f["month_dt"], y=a_f["fc_sav"],
                                name="Forecast Savings", marker_color="#3498db", opacity=0.5))
        fig_a1.add_trace(go.Bar(x=a_f["month_dt"], y=a_f["savings_actual"],
                                name="Actual Savings", marker_color="#2ecc71"))
        fig_a1.update_layout(barmode="overlay",
                              **chart_layout("Monthly Savings: Actual vs Forecast", height=340))
        cr.plotly_chart(fig_a1, use_container_width=True, key="fig_act_1")

        cl2, cr2 = st.columns(2)

        # ── Chart 3: Stacked breakdown ────────────────────────────────────────
        if not a_full.empty:
            a_full["var_pos"] = a_full["var_exp"].clip(lower=0)
            fig_a2 = go.Figure()
            fig_a2.add_trace(go.Bar(x=a_full["month_dt"], y=a_full["fc_fixed"],
                                    name="Fixed Expenses", marker_color="#e74c3c"))
            fig_a2.add_trace(go.Bar(x=a_full["month_dt"], y=a_full["var_pos"],
                                    name="Variable Expenses", marker_color="#e67e22"))
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
                name="Variable Expenses",
                marker_color=["#e74c3c" if v < 0 else "#e67e22" for v in a_full["var_exp"]]
            ))
            avg_var = a_full["var_exp"].mean()
            fig_a3.add_hline(y=avg_var, line_color="#f1c40f", line_dash="dash",
                             annotation_text=f"avg €{avg_var:,.0f}",
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
                                        name="Cumulative Actual",
                                        line=dict(color="#2ecc71", width=2.5)))
            fig_a4.add_trace(go.Scatter(x=a_f["month_dt"], y=a_f["cumul_forecast"],
                                        name="Cumulative Forecast",
                                        line=dict(color="#3498db", width=2, dash="dash")))
            fig_a4.update_layout(**chart_layout(
                f"Cumulative Savings — €{abs(diff):,.0f} {sign_lbl} forecast", height=320))
            st.plotly_chart(fig_a4, use_container_width=True, key="fig_act_4")

        # ── Net worth tracker ────────────────────────────────────────────────
        _nws = p_act.get("net_worth_start", 0)
        if not a_f.empty:
            a_f["net_worth"] = _nws + a_f["cumul_actual"]
            a_f["net_worth_fc"] = _nws + a_f["cumul_forecast"]
            _nw_latest = a_f["net_worth"].iloc[-1]
            _nw_fc_latest = a_f["net_worth_fc"].iloc[-1]
            _nw_delta = _nw_latest - _nw_fc_latest
            fig_nw = go.Figure()
            fig_nw.add_trace(go.Scatter(
                x=a_f["month_dt"], y=a_f["net_worth"],
                name="Actual Net Worth",
                line=dict(color="#f1c40f", width=2.5),
                fill="tozeroy", fillcolor="rgba(241,196,15,0.07)"))
            fig_nw.add_trace(go.Scatter(
                x=a_f["month_dt"], y=a_f["net_worth_fc"],
                name="Forecast Net Worth",
                line=dict(color="#95a5a6", width=1.5, dash="dash")))
            fig_nw.update_layout(**chart_layout(
                f"Net Worth — €{_nw_latest:,.0f} actual · "
                f"{'ahead of' if _nw_delta >= 0 else 'behind'} forecast by €{abs(_nw_delta):,.0f}",
                "€", height=300))
            st.plotly_chart(fig_nw, use_container_width=True, key="fig_act_nw")
            _nw_col1, _nw_col2, _nw_col3 = st.columns(3)
            _nw_col1.metric("Starting Net Worth", f"€{_nws:,.0f}",
                help="Set in ⚙️ Setup → 📈 Projection Assumptions.")
            _nw_col2.metric("Current Net Worth (actual)", f"€{_nw_latest:,.0f}",
                delta=f"€{_nw_delta:+,.0f} vs forecast")
            _nw_col3.metric("Net Worth Forecast", f"€{_nw_fc_latest:,.0f}")

        # ── Net Worth Tracker ────────────────────────────────────────────────
        _nws = p_act.get("net_worth_start", 0)
        if _nws > 0 and not a_f.empty:
            st.divider()
            st.subheader("💎 Net Worth Tracker")
            st.caption(
                f"Starting net worth **€{_nws:,.0f}** (from Setup → Projection Assumptions) "
                "plus cumulative savings to date. Liquid wealth only — "
                "home equity from the Buy vs Rent tab adds on top."
            )
            a_nw = a_f.copy()
            a_nw["nw_actual"]   = _nws + a_nw["cumul_actual"]
            a_nw["nw_forecast"] = _nws + a_nw["cumul_forecast"]
            _cur_nw   = a_nw["nw_actual"].iloc[-1]
            _fc_nw    = a_nw["nw_forecast"].iloc[-1]
            _nw_delta = _cur_nw - _fc_nw
            _nw_cols  = st.columns(3)
            _nw_cols[0].metric("Current Net Worth (liquid)", f"€{_cur_nw:,.0f}",
                delta=f"€{_nw_delta:+,.0f} vs forecast",
                help="Starting net worth + cumulative actual savings entered in this tab.")
            _nw_cols[1].metric("Forecast Net Worth (to date)", f"€{_fc_nw:,.0f}",
                help="Starting net worth + cumulative forecast savings for the same period.")
            _nw_cols[2].metric("Months Tracked", len(a_nw),
                help="Number of months with actual savings data entered.")
            fig_nw = go.Figure()
            fig_nw.add_trace(go.Scatter(
                x=a_nw["month_dt"], y=a_nw["nw_actual"],
                name="Actual Net Worth", mode="lines+markers",
                line=dict(color="#2ecc71", width=2.5), marker=dict(size=6)
            ))
            fig_nw.add_trace(go.Scatter(
                x=a_nw["month_dt"], y=a_nw["nw_forecast"],
                name="Forecast Net Worth", mode="lines",
                line=dict(color="#3498db", width=2, dash="dash")
            ))
            fig_nw.add_hline(y=_nws, line_color="#7f8c8d", line_dash="dot",
                annotation_text=f"Start €{_nws:,.0f}", annotation_position="bottom right")
            fig_nw.update_layout(**chart_layout(
                f"Net Worth Over Time — starting €{_nws:,.0f}", "€", height=340))
            st.plotly_chart(fig_nw, use_container_width=True, key="fig_act_nw")
        elif _nws == 0 and not a_f.empty:
            st.info(
                "💡 Set a **Starting net worth** in ⚙️ Setup → Projection Assumptions "
                "to enable the net worth tracker here.", icon="💎"
            )

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
- **Net Worth tracker** — starting net worth (from Setup) plus cumulative savings. Requires a starting net worth value in Setup → Projection Assumptions.
        """)

with tabs[6]:
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
