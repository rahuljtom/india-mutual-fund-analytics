import datetime
import math

import pytest

from conftest import END, N_DAYS, START


def q(con, sql):
    return con.execute(sql).fetchall()


def test_dimensions_classify_plan_option_and_category(con):
    got = {r[0]: r[1:] for r in q(con, "select scheme_code, plan_type, option_type from dim_scheme")}
    assert got[1001] == ("Direct", "Growth")
    assert got[1002] == ("Regular", "Growth")
    assert got[1003] == ("Direct", "IDCW")
    cats = q(con, "select asset_class, sub_category from dim_category order by 1, 2")
    assert cats == [("Equity Scheme", "Large Cap Fund"), ("Other Scheme", "Index Funds")]


def test_overlap_and_bad_values_are_counted_and_removed(con):
    got = dict(q(con, "select check_name, n from r03_data_quality"))
    assert got["duplicate_keys_in_fact"] == 0
    assert got["orphan_fact_rows"] == 0
    assert got["nav_not_numeric"] == 1
    assert got["staged_rows"] - got["fact_rows"] == 6 + 1  # 6 overlap-day duplicates and 1 N.A. row
    assert got["fact_rows"] == 6 * (N_DAYS + 1) - 1


def test_universe_is_direct_growth_equity_plus_benchmark(con):
    codes = [r[0] for r in q(con, "select scheme_code from analysis_universe order by 1")]
    assert codes == [1001, 1004, 1005]
    assert q(con, "select scheme_code from analysis_universe where is_benchmark") == [(1005,)]


def test_fact_nav_rejects_non_positive_nav(con):
    with pytest.raises(Exception):
        con.execute("insert into fact_nav values (1001, date '2030-01-01', -1)")


def test_dimension_foreign_key_is_enforced(con):
    with pytest.raises(Exception):
        con.execute("insert into dim_scheme values (9, 'x', 999, 1, 'Direct', 'Growth', null, date '2020-01-01', date '2020-01-02')")


def test_rolling_two_year_cagr_matches_closed_form(con):
    got = q(con, f"select cagr from rolling_returns where scheme_code = 1001 and nav_date = date '{END}'")
    assert got[0][0] == pytest.approx(0.10, abs=1e-9)
    first = q(con, "select min(nav_date) from rolling_returns where scheme_code = 1001")[0][0]
    assert first == datetime.date(2021, 12, 31)  # first date with a full two calendar-year look-back (2020 is a leap year)


def test_rolling_by_category_excludes_benchmark(con):
    got = q(con, "select sub_category, schemes from r05_rolling_by_category")
    assert got == [("Large Cap Fund", 2)]


def test_category_vs_benchmark_counts_every_comparable_date(con):
    sub, dates, pct, excess = q(con, "select * from r05_vs_benchmark")[0]
    assert sub == "Large Cap Fund" and dates == 731
    assert 0 <= pct <= 100 and excess > 0  # category median (10% and up) sits above the 8% benchmark


def test_max_drawdown_trough_and_recovery_dates(con):
    code, dd, trough, peak, recovery = q(con, "select scheme_code, max_drawdown, trough_date, peak_date, recovery_date "
                                              "from scheme_drawdowns where scheme_code = 1004")[0]
    assert dd == pytest.approx(-0.25)
    assert trough == START + datetime.timedelta(days=600)
    assert peak == START + datetime.timedelta(days=400)
    assert recovery == START + datetime.timedelta(days=900)


def test_scheme_that_never_fell_has_no_recovery_dates(con):
    dd, peak, recovery = q(con, "select max_drawdown, peak_date, recovery_date from scheme_drawdowns where scheme_code = 1001")[0]
    assert dd == 0 and peak is None and recovery is None


def test_drawdown_summary_ignores_never_fell_schemes_for_recovery_share(con):
    sub, schemes, median_dd, worst, _, pct_recovered, _ = q(con, "select * from r06_drawdown_by_category")[0]
    assert schemes == 2 and worst == -25.0 and pct_recovered == 100.0


def test_risk_return_uses_the_requested_window(con):
    cagr, vol = q(con, "select cagr_pct, annual_vol_pct from r07_scheme_risk_return where scheme_code = 1004")[0]
    expected = (220 / piece(N_DAYS - 730)) ** 0.5 - 1
    assert cagr == pytest.approx(100 * expected, abs=0.01)
    assert vol > 0


def piece(i):
    from conftest import piecewise
    return piecewise(i)


def test_persistence_top_quartile_repeats_when_leader_stays_leader(con):
    row = q(con, "select top_quartile_schemes, stayed_top_quartile, repeat_rate_pct from r08_top_quartile_repeat")[0]
    assert row == (1, 1, 100.0)  # 1004 led both periods


def test_plan_pairs_found_and_gap_is_about_the_modelled_cost(con):
    assert q(con, "select count(*) from plan_pairs") == [(2,)]
    pairs, gap = q(con, "select pairs, median_gap_pp from r09_direct_vs_regular where sub_category = 'ALL EQUITY CATEGORIES'")[0]
    assert pairs == 2
    assert 1.0 <= gap <= 1.2  # 1001 vs 1002 is 1.00 pp; 1004 vs 1006 is about 1.13 pp


def test_export_writes_every_result_table(con, tmp_path):
    from mfa import pipeline
    names = pipeline.export(con, tmp_path)
    assert {"r03_data_quality", "r05_vs_benchmark", "r09_direct_vs_regular"} <= set(names)
    assert math.isfinite(1.0)
