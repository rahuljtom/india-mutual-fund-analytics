from collections import Counter

import pytest

from mfa import parse

SAMPLE = """Scheme Code;NAV Name;Plan;Option;ISIN Div Payout/ISIN Growth;ISIN Div Reinvestment;Net Asset Value;Date

Open Ended Schemes ( Equity Scheme - Large Cap Fund )

Alpha Mutual Fund
101;Alpha Large Cap Fund - Direct Plan - Growth;Direct Plan;GROWTH;INF000A01AA1;;10.5000;01-Jan-2024
101;Alpha Large Cap Fund - Direct Plan - Growth;Direct Plan;GROWTH;INF000A01AA1;;N.A.;02-Jan-2024
broken;line;with;too;few;fields

Open Ended Schemes( Other Scheme - Index Funds ** )

Beta Mutual Fund
202;Beta Nifty 50 Index Fund - Regular Plan - Growth;Regular Plan;GROWTH;INF000B01BB2;;20.0000;01-Jan-2024
Some stray heading without keyword
"""


def run(text):
    report = Counter()
    rows = list(parse.parse_lines(text.splitlines(), report))
    return rows, report


def test_rows_inherit_fund_house_and_category():
    rows, _ = run(SAMPLE)
    assert len(rows) == 3
    first, last = rows[0], rows[-1]
    assert first[0] == "101" and first[8] == "Alpha Mutual Fund"
    assert first[9] == "Open Ended" and first[10] == "Equity Scheme - Large Cap Fund"
    assert last[8] == "Beta Mutual Fund"
    assert last[10] == "Other Scheme - Index Funds"  # '**' marker and odd spacing removed


def test_every_non_data_line_is_counted():
    _, report = run(SAMPLE)
    assert report["rows"] == 3
    assert report["rejected_wrong_field_count"] == 1
    assert report["unclassified_lines"] == 1
    assert report["category_headings"] == 2
    assert report["fund_house_headings"] == 2
    assert report["column_header_lines"] == 1


def test_data_row_before_any_heading_is_rejected():
    rows, report = run("1;Name;;;;;10.0;01-Jan-2024")
    assert rows == [] and report["rejected_no_heading_context"] == 1


def test_non_numeric_nav_is_kept_as_text_for_sql_to_null_out():
    rows, _ = run(SAMPLE)
    assert rows[1][6] == "N.A."


def test_convert_roundtrip(tmp_path):
    raw = tmp_path / "raw.txt"
    raw.write_text(SAMPLE)
    report = parse.convert(raw, tmp_path / "out.csv.gz")
    assert report["rows"] == 3
    assert (tmp_path / "out.csv.gz").exists()
