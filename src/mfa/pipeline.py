"""Parse raw AMFI reports, build the DuckDB warehouse and export every result table.

Usage:
    python -m mfa.pipeline                 # parse (if needed), build, export
    python -m mfa.pipeline --as-of 2025-12-31 --window-years 3
"""
import argparse
import csv
import datetime
import sys
from pathlib import Path

import duckdb

from mfa import parse

ROOT = Path(__file__).resolve().parents[2]
SQL_DIR = ROOT / "sql"
RESULT_TABLE_PATTERN = "^r[0-9]{2}[a-z]?_"

DEFAULT_PARAMS = {
    "as_of_date": datetime.date(2025, 12, 31),   # end of all analysis windows
    "window_years": 3,                           # rolling-return and persistence window
    "risk_years": 3,                             # window for volatility and return per unit of volatility
    "dd_start": datetime.date(2018, 1, 1),       # start of the drawdown period
    "stale_gap_days": 7,                         # largest gap between a target date and the NAV used for it
    "min_schemes_per_category": 8,               # smaller categories are not reported
    "min_benchmark_funds": 2,                    # benchmark needs at least this many index funds on a date
}


def convert_raw(raw_dir, interim_dir):
    """Parse every raw report that has no parsed file yet. Returns {file: parse report}."""
    reports = {}
    for raw in sorted(Path(raw_dir).glob("amfi_*.txt*")):
        out = Path(interim_dir) / (raw.name.split(".")[0] + ".csv.gz")
        if not out.exists():
            reports[raw.name] = parse.convert(raw, out)
    return reports


def build(con, interim_glob, params=None):
    """Create the params table, then run every numbered SQL file in order."""
    p = dict(DEFAULT_PARAMS)
    p.update(params or {})
    con.execute(
        "create or replace table params as select ?::date as as_of_date, ?::integer as window_years, "
        "?::integer as risk_years, ?::date as dd_start, ?::integer as stale_gap_days, "
        "?::integer as min_schemes_per_category, ?::integer as min_benchmark_funds",
        [p["as_of_date"], p["window_years"], p["risk_years"], p["dd_start"], p["stale_gap_days"],
         p["min_schemes_per_category"], p["min_benchmark_funds"]],
    )
    for path in sorted(SQL_DIR.glob("[0-9][0-9]_*.sql")):
        con.execute(path.read_text().replace("__INTERIM_GLOB__", interim_glob))


def result_tables(con):
    rows = con.execute(
        "select table_name from information_schema.tables where regexp_matches(table_name, ?) order by table_name",
        [RESULT_TABLE_PATTERN],
    ).fetchall()
    return [r[0] for r in rows]


def export(con, out_dir):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in result_tables(con):
        con.execute(f"copy {name} to '{out_dir / (name + '.csv')}' (header, delimiter ',')")
    return result_tables(con)


def write_parse_report(reports, path):
    keys = sorted({k for r in reports.values() for k in r})
    with open(path, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["file"] + keys)
        for name, rep in reports.items():
            writer.writerow([name] + [rep.get(k, 0) for k in keys])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw-dir", default=str(ROOT / "data" / "raw"))
    ap.add_argument("--interim-dir", default=str(ROOT / "data" / "interim"))
    ap.add_argument("--db", default=str(ROOT / "data" / "mf.duckdb"))
    ap.add_argument("--out", default=str(ROOT / "outputs" / "tables"))
    ap.add_argument("--as-of", type=datetime.date.fromisoformat)
    ap.add_argument("--window-years", type=int)
    args = ap.parse_args()

    reports = convert_raw(args.raw_dir, args.interim_dir)
    if reports:
        write_parse_report(reports, Path(args.interim_dir) / "parse_report.csv")
        print(f"parsed {len(reports)} raw files")
    params = {}
    if args.as_of:
        params["as_of_date"] = args.as_of
    if args.window_years:
        params["window_years"] = args.window_years

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    Path(args.db).unlink(missing_ok=True)
    con = duckdb.connect(args.db)
    build(con, str(Path(args.interim_dir) / "amfi_*.csv.gz"), params)
    for name in export(con, args.out):
        print("wrote", name)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
