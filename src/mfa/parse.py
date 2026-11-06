"""Parse AMFI historical NAV text reports into flat CSV rows.

The report is semi-structured text: a header line, then blocks of
    <category heading>        e.g.  Open Ended Schemes ( Equity Scheme - Large Cap Fund )
    <fund house heading>      e.g.  Axis Mutual Fund
    <data rows>               8 semicolon-separated fields
Headings apply to the data rows that follow them, so the parser keeps the current category and fund house as state.
Every line is either parsed, or counted in the report under a named reason; nothing is silently dropped.
"""
import csv
import gzip
import re
from collections import Counter
from pathlib import Path

CATEGORY_RE = re.compile(r"^(open ended|close ended|interval fund)\s+schemes?\s*\(\s*(.+?)\s*\)\s*$", re.IGNORECASE)
AMC_RE = re.compile(r"mutual fund\s*$", re.IGNORECASE)
HEADER_PREFIX = "Scheme Code;"
FIELD_COUNT = 8
OUT_COLUMNS = [
    "scheme_code", "scheme_name", "plan", "option", "isin_payout_growth", "isin_reinvest",
    "nav", "nav_date", "amc", "scheme_type", "category_raw",
]
SCHEME_TYPES = {"open ended": "Open Ended", "close ended": "Close Ended", "interval fund": "Interval"}


def clean_category(text):
    """Collapse whitespace and the stray '**' footnote markers that appear in some headings."""
    return re.sub(r"\s+", " ", text.replace("**", "")).strip()


def parse_lines(lines, report):
    """Yield one tuple per NAV row (OUT_COLUMNS order). `report` is a Counter that is updated in place."""
    amc, scheme_type, category = None, None, None
    for raw in lines:
        line = raw.strip()
        report["lines"] += 1
        if not line:
            report["blank_lines"] += 1
            continue
        if line.startswith(HEADER_PREFIX):
            report["column_header_lines"] += 1
            continue
        if ";" in line:
            fields = line.split(";")
            if len(fields) != FIELD_COUNT:
                report["rejected_wrong_field_count"] += 1
                continue
            if amc is None or category is None:
                report["rejected_no_heading_context"] += 1
                continue
            code, name, plan, option, isin1, isin2, nav, date = (f.strip() for f in fields)
            report["rows"] += 1
            yield (code, name, plan, option, isin1, isin2, nav, date, amc, scheme_type, category)
            continue
        match = CATEGORY_RE.match(line)
        if match:
            scheme_type = SCHEME_TYPES[match.group(1).lower()]
            category = clean_category(match.group(2))
            report["category_headings"] += 1
        elif AMC_RE.search(line):
            amc = line
            report["fund_house_headings"] += 1
        else:
            report["unclassified_lines"] += 1


def open_text(path):
    path = Path(path)
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", errors="replace", newline="")
    return open(path, "r", encoding="utf-8", errors="replace", newline="")


def convert(raw_path, out_path):
    """Convert one raw report to a gzip CSV and return the parse report as a dict."""
    report = Counter()
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".tmp")
    with open_text(raw_path) as src, gzip.open(tmp, "wt", encoding="utf-8", newline="") as dst:
        writer = csv.writer(dst)
        writer.writerow(OUT_COLUMNS)
        writer.writerows(parse_lines(src, report))
    tmp.rename(out_path)
    return dict(report)
