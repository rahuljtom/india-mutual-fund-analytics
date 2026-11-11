"""The decision page is generated from the committed result tables; these tests check it builds and carries no template leftovers."""
import re

from mfa import site


def test_page_builds_from_result_tables(tmp_path):
    out = tmp_path / "index.html"
    site.build(out)
    html = out.read_text()
    assert "<title>" in html and "const DATA" in html
    for bad in ("nan", "None", "undefined", "{{", "}}"):
        assert not re.search(r"(?<![A-Za-z])" + re.escape(bad) + r"(?![A-Za-z])", html.split("<body>")[1].split("<script>")[0]), bad


def test_page_numbers_come_from_the_tables(tmp_path):
    import pandas as pd
    out = tmp_path / "index.html"
    site.build(out)
    html = out.read_text()
    gap = pd.read_csv(site.TABLES / "r09_direct_vs_regular.csv").set_index("sub_category").loc["ALL EQUITY CATEGORIES"]
    assert f"{gap.median_gap_pp:.2f} points a year less" in html
    assert f"{int(gap.pairs):,}" in html
