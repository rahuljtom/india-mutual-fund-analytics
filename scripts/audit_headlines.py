"""Independent recomputation of the headline numbers in pandas, compared with the SQL result tables.

Needs the built warehouse (make build). It reads scheme attributes and NAVs from DuckDB but re-implements the
calculations (look-backs, drawdowns, plan pairing, quartiles) without using any of the analysis SQL, then fails if a
number differs from outputs/tables.

    PYTHONPATH=src python scripts/audit_headlines.py
"""
import re
import sys
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "outputs" / "tables"
AS_OF = pd.Timestamp("2025-12-31")
TOL = pd.Timedelta(days=7)
MIN_SCHEMES = 8
failures = []


def check(name, mine, theirs, tol=0.011):
    ok = abs(mine - theirs) <= tol
    print(f"{'ok  ' if ok else 'FAIL'} {name}: pandas {mine:.3f} vs sql {theirs:.3f}")
    if not ok:
        failures.append(name)


def load():
    con = duckdb.connect(str(ROOT / "data" / "mf.duckdb"), read_only=True)
    schemes = con.sql("""select s.scheme_code, s.scheme_name, s.amc_id, s.plan_type, s.option_type, s.first_nav_date,
        s.last_nav_date, c.sub_category, c.asset_class, c.scheme_type
        from dim_scheme s join dim_category c using (category_id)""").df()
    eq = schemes[(schemes.option_type == "Growth") & (schemes.scheme_type == "Open Ended") & (schemes.asset_class == "Equity Scheme")]
    navs = con.sql("select scheme_code, nav_date, nav from fact_nav where scheme_code in (select scheme_code from dim_scheme "
                   "join dim_category using (category_id) where option_type = 'Growth' and scheme_type = 'Open Ended' "
                   "and asset_class = 'Equity Scheme')").df()
    navs["nav_date"] = pd.to_datetime(navs["nav_date"])
    return eq, navs


def asof(navs, codes, targets):
    """NAV on or before each target date, within 7 days. targets: Series aligned to codes."""
    left = pd.DataFrame({"scheme_code": codes.values, "target": targets.values}).sort_values("target")
    left["target"] = pd.to_datetime(left["target"]).astype("datetime64[ns]")
    right = navs.sort_values("nav_date").assign(nav_date=lambda d: d["nav_date"].astype("datetime64[ns]"))
    out = pd.merge_asof(left, right, left_on="target", right_on="nav_date", by="scheme_code", direction="backward", tolerance=TOL)
    return out


def rolling_check(eq, navs):
    direct = eq[eq.plan_type == "Direct"]
    n = navs[navs.scheme_code.isin(direct.scheme_code)].copy()
    n["target"] = n["nav_date"] - pd.DateOffset(years=3)
    m = asof(navs[navs.scheme_code.isin(direct.scheme_code)], n["scheme_code"], n["target"])
    n = n.reset_index(drop=True)
    # Two end dates can share one look-back date (28 and 29 February), so de-duplicate before joining back.
    m = m.drop_duplicates(["scheme_code", "target"])
    left = n.merge(m[["scheme_code", "target", "nav"]].rename(columns={"nav": "nav_start"}), on=["scheme_code", "target"], how="left")
    left = left.dropna(subset=["nav_start"])
    left["cagr"] = (left["nav"] / left["nav_start"]) ** (1 / 3) - 1
    left = left.merge(direct[["scheme_code", "sub_category"]], on="scheme_code")
    sql = pd.read_csv(TABLES / "r05_rolling_by_category.csv").set_index("sub_category")
    for cat in ["Large Cap Fund", "Small Cap Fund"]:
        c = left[left.sub_category == cat]["cagr"]
        row = sql.loc[cat]
        check(f"{cat} rolling median %", 100 * c.median(), row.median_cagr_pct)
        check(f"{cat} rolling p10 %", 100 * c.quantile(0.10), row.p10_cagr_pct)
        check(f"{cat} rolling p90 %", 100 * c.quantile(0.90), row.p90_cagr_pct)
        check(f"{cat} windows negative %", 100 * (c < 0).mean(), row.pct_windows_negative, tol=0.11)


def drawdown_check(eq, navs):
    direct = eq[eq.plan_type == "Direct"]
    matured = direct[(direct.first_nav_date <= pd.Timestamp("2018-01-08")) & (direct.last_nav_date >= pd.Timestamp("2025-12-24"))]
    n = navs[navs.scheme_code.isin(matured.scheme_code) & (navs.nav_date >= "2018-01-01") & (navs.nav_date <= AS_OF)].sort_values(["scheme_code", "nav_date"])
    n["dd"] = n["nav"] / n.groupby("scheme_code")["nav"].cummax() - 1
    worst = n.groupby("scheme_code")["dd"].min().rename("max_dd").reset_index().merge(matured[["scheme_code", "sub_category"]])
    sql = pd.read_csv(TABLES / "r06_drawdown_by_category.csv").set_index("sub_category")
    for cat in ["Mid Cap Fund", "Small Cap Fund"]:
        check(f"{cat} median max drawdown %", 100 * worst[worst.sub_category == cat]["max_dd"].median(), sql.loc[cat].median_max_drawdown_pct, tol=0.11)


def stem(name):
    s = re.sub(r"\b(direct|regular|plan|growth|option|scheme)\b", " ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def pairs_check(eq, navs):
    g = eq[eq.plan_type.isin(["Direct", "Regular"])].copy()
    g["stem"] = g.scheme_name.map(stem)
    grp = g.groupby(["amc_id", "stem"])
    rows = []
    for _, part in grp:
        d, r = part[part.plan_type == "Direct"], part[part.plan_type == "Regular"]
        if len(d) == 1 and len(r) == 1:
            rows.append((d.scheme_code.iloc[0], r.scheme_code.iloc[0]))
    codes = pd.Series([c for pair in rows for c in pair])
    start = pd.Series([AS_OF - pd.DateOffset(years=3)] * len(codes))
    end = pd.Series([AS_OF] * len(codes))
    s = asof(navs, codes, start).set_index("scheme_code")["nav"]
    e = asof(navs, codes, end).set_index("scheme_code")["nav"]
    s, e = s[~s.index.duplicated()], e[~e.index.duplicated()]
    gaps = []
    for d, r in rows:
        vals = [s.get(d), e.get(d), s.get(r), e.get(r)]
        if any(pd.isna(v) for v in vals):
            continue
        gaps.append(((vals[1] / vals[0]) ** (1 / 3) - (vals[3] / vals[2]) ** (1 / 3)) * 100)
    sql = pd.read_csv(TABLES / "r09_direct_vs_regular.csv").set_index("sub_category").loc["ALL EQUITY CATEGORIES"]
    check("plan pairs", len(gaps), sql.pairs, tol=0)
    check("median Direct minus Regular gap (pp)", pd.Series(gaps).median(), sql.median_gap_pp)


def month_end_matrix(eq, navs):
    """Scheme x month table of month-end NAVs (Direct plans), a month counting only if its last NAV is within 7 days of month end."""
    direct = eq[eq.plan_type == "Direct"].scheme_code
    n = navs[navs.scheme_code.isin(direct)].sort_values("nav_date").copy()
    n["ym"] = n.nav_date.dt.year * 12 + n.nav_date.dt.month
    last = n.groupby(["scheme_code", "ym"]).tail(1)
    last = last[((last.nav_date + pd.offsets.MonthEnd(0)) - last.nav_date).dt.days <= 7]
    return last.pivot(index="scheme_code", columns="ym", values="nav")


def ntile(position, size, buckets):
    """SQL NTILE: bucket (1-based) of the row at 0-based `position` among `size` rows."""
    base, extra = divmod(size, buckets)
    cutoff = extra * (base + 1)
    return position // (base + 1) + 1 if position < cutoff else extra + (position - cutoff) // base + 1


def backtest_check(eq, navs):
    wide = month_end_matrix(eq, navs)
    cat = eq.set_index("scheme_code").sub_category
    picks = {"Top quartile of trailing 2-year return": [], "Everything except the bottom quartile": [],
             "Bottom quartile (the avoid list)": [], "Lowest-volatility third": []}
    for year in range(2020, 2025):
        m0 = year * 12 + 12
        if m0 - 24 not in wide.columns or m0 not in wide.columns:
            continue
        months = list(range(m0 - 24, m0 + 1))
        if not all(m in wide.columns for m in months):
            continue
        block = wide[months].dropna()
        rets = block.pct_change(axis=1).iloc[:, 1:]
        frame = pd.DataFrame({"trail": (block[m0] / block[m0 - 24]) ** 0.5 - 1, "vol": rets.std(axis=1, ddof=1)})
        frame["fwd"] = (wide[m0 + 12] / wide[m0] - 1).reindex(frame.index) if (m0 + 12) in wide.columns else float("nan")
        frame["cat"] = cat.reindex(frame.index)
        for _, grp in frame.groupby("cat"):
            if len(grp) < MIN_SCHEMES:
                continue
            avg = grp.fwd.mean()
            g = grp.reset_index().sort_values(["trail", "scheme_code"], ascending=[False, True]).reset_index(drop=True)
            g["q"] = [ntile(i, len(g), 4) for i in range(len(g))]
            v = grp.reset_index().sort_values(["vol", "scheme_code"]).reset_index(drop=True)
            v["t"] = [ntile(i, len(v), 3) for i in range(len(v))]
            for name, part in (("Top quartile of trailing 2-year return", g[g.q == 1]),
                               ("Everything except the bottom quartile", g[g.q < 4]),
                               ("Bottom quartile (the avoid list)", g[g.q == 4]),
                               ("Lowest-volatility third", v[v.t == 1])):
                picks[name] += [(len(part), (part.fwd - avg).dropna().tolist())]
    sql = pd.read_csv(TABLES / "r10_backtest_summary.csv").set_index("selection_rule")
    for name, parts in picks.items():
        excess = pd.Series([x for _, xs in parts for x in xs])
        check(f"Backtest picks: {name}", sum(n for n, _ in parts), sql.loc[name].picks, tol=0)
        check(f"Backtest survivors: {name}", len(excess), sql.loc[name].survivors, tol=0)
        check(f"Backtest average excess pp: {name}", 100 * excess.mean(), sql.loc[name].avg_excess_pp)


def holding_check(eq, navs):
    wide = month_end_matrix(eq, navs)
    sql = pd.read_csv(TABLES / "r12_holding_period.csv")
    for years in (1, 3, 5):
        h = 12 * years
        total = []
        for m in wide.columns:
            if m - h in wide.columns:
                both = wide[[m - h, m]].dropna()
                total += (both[m] / both[m - h] - 1).tolist()
        t = pd.Series(total)
        row = sql[(sql.horizon_years == years) & (sql.sub_category == "ALL EQUITY CATEGORIES")].iloc[0]
        check(f"{years}-year windows", len(t), row.windows, tol=0)
        check(f"{years}-year windows with a loss %", 100 * (t < 0).mean(), row.pct_windows_with_loss, tol=0.051)
        check(f"{years}-year median annualised %", 100 * ((1 + t) ** (1 / years) - 1).median(), row.median_annual_pct, tol=0.051)


def cost_check():
    gap = pd.read_csv(TABLES / "r09_direct_vs_regular.csv").set_index("sub_category").loc["ALL EQUITY CATEGORIES"].median_gap_pp
    row = pd.read_csv(TABLES / "r11_cost_drag.csv").query("horizon_years == 10 and direct_cagr_pct == 12").iloc[0]

    def corpus(rate):
        i = (1 + rate / 100) ** (1 / 12) - 1
        return sum(10000 * (1 + i) ** k for k in range(1, 121))  # 120 deposits at the start of each month

    check("10-year SIP corpus, Direct at 12% (rupees)", corpus(12), row.sip_direct_inr, tol=1)
    check("10-year SIP cost of Regular (rupees)", corpus(12) - corpus(12 - gap), row.sip_cost_inr, tol=1)


def main():
    eq, navs = load()
    rolling_check(eq, navs)
    drawdown_check(eq, navs)
    pairs_check(eq, navs)
    backtest_check(eq, navs)
    holding_check(eq, navs)
    cost_check()
    print("\nALL CHECKS PASSED" if not failures else f"\nFAILED: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
