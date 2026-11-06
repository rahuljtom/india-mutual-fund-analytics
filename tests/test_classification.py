"""Plan, option and category labelling on the awkward cases found in the real AMFI file."""
import duckdb
import pytest

from mfa import parse, pipeline

TEXT = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Dividend Yield Fund )

Alpha Mutual Fund
1;Alpha Dividend Yield Fund - Direct Plan - Growth;Direct Plan;GROWTH;;;10.0;01-Jan-2024
2;Alpha Dividend Yield Fund - Direct Plan - Growth Option;;;;;10.0;01-Jan-2024
3;Alpha Dividend Yield Fund - Direct Plan - IDCW;Direct Plan;IDCW Payout;;;10.0;01-Jan-2024
4;Alpha Equity Fund - Direct Plan - Dividend Payout;;;;;10.0;01-Jan-2024
5;Alpha Equity Fund - Regular Plan - Bonus Option;Regular Plan;Bonus Option;;;10.0;01-Jan-2024

Open Ended Schemes ( Equity Schemes - Thematic Fund )

Alpha Mutual Fund
6;Alpha Thematic Fund - Direct Plan - Growth;Direct Plan;Growth;;;10.0;01-Jan-2024

Open Ended Schemes ( Equity Schemes - ELSS- Tax Saver Fund )

Alpha Mutual Fund
7;Alpha Tax Saver - Direct Plan - Growth;Direct Plan;Growth;;;10.0;01-Jan-2024

Close Ended Schemes ( Income )

Alpha Mutual Fund
8;Alpha Fixed Term Plan - Growth;;;;;10.0;01-Jan-2024
"""


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    base = tmp_path_factory.mktemp("cls")
    raw = base / "raw"
    raw.mkdir()
    (raw / "amfi_20240101_20240101.txt").write_text(TEXT)
    pipeline.convert_raw(raw, base / "interim")
    conn = duckdb.connect(":memory:")
    pipeline.build(conn, str(base / "interim" / "amfi_*.csv.gz"), {"min_schemes_per_category": 1})
    return conn


def scheme(con, code):
    return con.execute(
        "select s.plan_type, s.option_type, c.asset_class, c.sub_category from dim_scheme s "
        "join dim_category c using (category_id) where scheme_code = ?", [code]).fetchone()


def test_dividend_yield_growth_is_not_mistaken_for_idcw(con):
    assert scheme(con, 1)[:2] == ("Direct", "Growth")
    assert scheme(con, 2)[:2] == ("Direct", "Growth")  # empty option column: falls back to the name


def test_idcw_and_dividend_payout_are_idcw(con):
    assert scheme(con, 3)[1] == "IDCW"
    assert scheme(con, 4)[1] == "IDCW"


def test_bonus_option_is_other(con):
    assert scheme(con, 5)[:2] == ("Regular", "Other")


def test_plural_and_renamed_categories_are_harmonised(con):
    assert scheme(con, 6)[2:] == ("Equity Scheme", "Sectoral/ Thematic")
    assert scheme(con, 7)[2:] == ("Equity Scheme", "ELSS")


def test_heading_without_separator_is_kept_whole(con):
    assert scheme(con, 8)[2:] == ("Income", "Income")
