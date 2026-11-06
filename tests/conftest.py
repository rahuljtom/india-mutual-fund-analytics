"""Synthetic AMFI history with answers that can be worked out by hand.

Daily NAVs from 2019-12-31 (index 0) to 2023-12-31 (index 1461), written in the real AMFI text layout so the whole
path is exercised: raw text -> parser -> SQL. The history is split over two raw files that overlap on one day, as
the real 90-day windows can, and one NAV is "N.A.".

  1001 Alpha Large Cap Direct Growth     compounds at exactly 10% a year
  1002 Alpha Large Cap Regular Growth    compounds at exactly 9% a year (pair of 1001)
  1003 Alpha Large Cap Direct IDCW       10% a year, but IDCW option: outside the analysis universe
  1004 Beta Large Cap Direct Growth      piecewise path: 100 -> 200 (i=400) -> 150 (i=600) -> 200 (i=900) -> 220
  1005 Gamma Nifty 50 Index Direct Growth  8% a year, the benchmark
  1006 Beta Large Cap Regular Growth     1004 less 1% a year (pair of 1004)
"""
import datetime
import math

import duckdb
import pytest

from mfa import parse, pipeline

START = datetime.date(2019, 12, 31)
END = datetime.date(2023, 12, 31)
N_DAYS = (END - START).days  # 1461
SPLIT = datetime.date(2022, 12, 31)  # last day of file 1 and first day of file 2 (overlap)


def piecewise(i):
    if i <= 400:
        return 100 + 100 * i / 400
    if i <= 600:
        return 200 - 50 * (i - 400) / 200
    if i <= 900:
        return 150 + 50 * (i - 600) / 300
    return 200 + 20 * (i - 900) / (N_DAYS - 900)


SCHEMES = [
    (1001, "Alpha Large Cap Fund - Direct Plan - Growth", "Direct Plan", "GROWTH", "Alpha Mutual Fund",
     "Equity Scheme - Large Cap Fund", lambda i: 100 * 1.10 ** (i / 365)),
    (1002, "Alpha Large Cap Fund - Regular Plan - Growth", "Regular Plan", "GROWTH", "Alpha Mutual Fund",
     "Equity Scheme - Large Cap Fund", lambda i: 100 * 1.09 ** (i / 365)),
    (1003, "Alpha Large Cap Fund - Direct Plan - IDCW", "Direct Plan", "IDCW", "Alpha Mutual Fund",
     "Equity Scheme - Large Cap Fund", lambda i: 100 * 1.10 ** (i / 365)),
    (1004, "Beta Large Cap Fund - Direct Plan - Growth", "Direct Plan", "GROWTH", "Beta Mutual Fund",
     "Equity Scheme - Large Cap Fund", piecewise),
    (1005, "Gamma Nifty 50 Index Fund - Direct Plan - Growth", "Direct Plan", "GROWTH", "Gamma Mutual Fund",
     "Other Scheme - Index Funds", lambda i: 100 * 1.08 ** (i / 365)),
    (1006, "Beta Large Cap Fund - Regular Plan - Growth", "Regular Plan", "GROWTH", "Beta Mutual Fund",
     "Equity Scheme - Large Cap Fund", lambda i: piecewise(i) * math.exp(-0.01 * i / 365)),
]


def render(first, last):
    """Raw AMFI-style text for all schemes between two dates (inclusive)."""
    lines = ["Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date", ""]
    by_category = {}
    for sch in SCHEMES:
        by_category.setdefault(sch[5], []).append(sch)
    for category, group in by_category.items():
        lines += [f"Open Ended Schemes ( {category} )", ""]
        for amc in sorted({g[4] for g in group}):
            lines += [amc]
            for code, name, plan, option, amc_name, _, fn in group:
                if amc_name != amc:
                    continue
                for i in range((first - START).days, (last - START).days + 1):
                    day = START + datetime.timedelta(days=i)
                    nav = "N.A." if (code == 1003 and i == 100) else f"{fn(i):.6f}"
                    lines.append(f"{code};{name};{plan};{option};INF{code};;{nav};{day:%d-%b-%Y}")
            lines.append("")
    return "\n".join(lines)


@pytest.fixture(scope="session")
def con(tmp_path_factory):
    base = tmp_path_factory.mktemp("mfa")
    raw = base / "raw"
    interim = base / "interim"
    raw.mkdir()
    (raw / "amfi_20191231_20221231.txt").write_text(render(START, SPLIT))
    (raw / "amfi_20221231_20231231.txt").write_text(render(SPLIT, END))
    pipeline.convert_raw(raw, interim)
    conn = duckdb.connect(":memory:")
    pipeline.build(conn, str(interim / "amfi_*.csv.gz"), {
        "as_of_date": END, "window_years": 2, "risk_years": 2, "dd_start": START,
        "min_schemes_per_category": 1, "min_benchmark_funds": 1,
    })
    yield conn
    conn.close()
