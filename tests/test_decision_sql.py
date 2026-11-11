"""Tests for the decision tables: month-end NAVs, the walk-forward backtest, the cost illustration and holding-period odds.

Answers are worked out from the synthetic histories in conftest.py (scheme 1001 compounds at exactly 10% a year; 1004 follows
a piecewise path), so each expected number can be rebuilt without reading the SQL.
"""
import datetime

import pytest

from conftest import START, piecewise


def q(con, sql):
    return con.execute(sql).fetchall()


def nav_1001(day):
    return 100 * 1.10 ** ((day - START).days / 365)


def nav_1004(day):
    return piecewise((day - START).days)


def month_ends(first, last):
    out, year, month = [], first.year, first.month
    while (year, month) <= (last.year, last.month):
        nxt = datetime.date(year + (month == 12), month % 12 + 1, 1)
        out.append(nxt - datetime.timedelta(days=1))
        year, month = nxt.year, nxt.month
    return out


def test_month_end_navs_cover_every_month_for_universe_schemes_only(con):
    got = dict(q(con, "select scheme_code, count(*) from monthly_nav group by 1"))
    assert got == {1001: 49, 1004: 49}  # Dec 2019 to Dec 2023; the benchmark and non-universe schemes are absent


def test_month_end_nav_is_the_last_day_of_the_month(con):
    got = q(con, "select nav_date from monthly_nav where scheme_code = 1001 and month_idx = 2021 * 12 + 2")
    assert got == [(datetime.date(2021, 2, 28),)]


def test_backtest_top_quartile_excess_in_2021(con):
    """Formation 31 Dec 2021: 1004 has the better trailing 24 months so it is the only top-quartile pick. Over 2022 it returned
    f4 and 1001 returned 10%, so its excess over the category average (f4 + 0.10) / 2 is (f4 - 0.10) / 2."""
    f4 = nav_1004(datetime.date(2022, 12, 31)) / nav_1004(datetime.date(2021, 12, 31)) - 1
    got = q(con, "select picks, survivors, avg_excess_pp from r10_backtest_by_year "
                 "where selection_rule like 'Top quartile%' and formation_year = 2021")
    assert got == [(1, 1, pytest.approx(round(100 * (f4 - 0.10) / 2, 2), abs=0.011))]


def test_backtest_counts_vanished_picks_when_there_is_no_forward_nav(con):
    """Formation 31 Dec 2023: there is no NAV 12 months later, so every pick has vanished and nothing is measured."""
    got = q(con, "select picks, survivors, avg_excess_pp from r10_backtest_by_year "
                 "where selection_rule like 'Top quartile%' and formation_year = 2023")
    assert got == [(1, 0, None)]


def test_backtest_skips_years_without_24_months_of_history(con):
    assert q(con, "select count(*) from r10_backtest_by_year where formation_year = 2020") == [(0,)]


def test_backtest_summary_reports_years_tested(con):
    got = q(con, "select years_tested from r10_backtest_summary where selection_rule like 'Top quartile%'")
    assert got == [(3,)]  # 2021, 2022 and 2023 have a full lookback


def test_cost_drag_matches_the_annuity_formula(con):
    gap = q(con, "select median_gap_pp from r09_direct_vs_regular where sub_category = 'ALL EQUITY CATEGORIES'")[0][0]
    got = q(con, "select regular_cagr_pct, sip_direct_inr, sip_regular_inr from r11_cost_drag "
                 "where horizon_years = 10 and direct_cagr_pct = 12")[0]

    def fv(rate_pct):
        i = (1 + rate_pct / 100) ** (1 / 12) - 1
        return 10000 * ((1 + i) ** 120 - 1) / i * (1 + i)

    assert got[0] == pytest.approx(12 - gap, abs=0.01)
    assert got[1] == pytest.approx(fv(12), abs=1)
    assert got[2] == pytest.approx(fv(12 - gap), rel=0.001)


def test_holding_period_counts_and_loss_share(con):
    """One-year windows end at each month end from Dec 2020 to Dec 2023 (37 per scheme). A window loses money when the NAV fell."""
    ends = month_ends(datetime.date(2020, 12, 1), datetime.date(2023, 12, 1))
    assert len(ends) == 37
    losses = sum(nav_1004(e) < nav_1004(datetime.date(e.year - 1, 12, 31) if e.month == 12 else
                                         (e.replace(day=1) - datetime.timedelta(days=1)).replace(year=e.year - 1)) for e in ends)
    got = q(con, "select windows, pct_windows_with_loss from r12_holding_period "
                 "where horizon_years = 1 and sub_category = 'ALL EQUITY CATEGORIES'")
    assert got[0][0] == 74
    assert got[0][1] == pytest.approx(round(100 * losses / 74, 1), abs=0.11)


def test_holding_period_longer_horizons_have_fewer_windows(con):
    got = dict(q(con, "select horizon_years, windows from r12_holding_period where sub_category = 'ALL EQUITY CATEGORIES'"))
    assert got[1] > got[3]
    assert 5 not in got  # the fixture is only four years long
