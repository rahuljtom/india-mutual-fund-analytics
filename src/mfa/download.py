"""Download AMFI historical NAV reports in 90-day windows (the portal's maximum per request).

Source: https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx (public, no key).
Each window is saved gzip-compressed to data/raw/amfi_<from>_<to>.txt.gz; windows already on disk are skipped,
so an interrupted run can simply be started again.

Usage:
    python -m mfa.download --start 2018-01-01 --end 2025-12-31
"""
import argparse
import datetime
import gzip
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

URL = "https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?frmdt={frm}&todt={to}"
RAW_DIR = Path(__file__).resolve().parents[2] / "data" / "raw"
WINDOW_DAYS = 90
FIRST_LINE_PREFIX = "Scheme Code;"


def fmt(day):
    return day.strftime("%d-%b-%Y")


def windows(start, end):
    """Consecutive, non-overlapping windows of at most WINDOW_DAYS days covering start..end inclusive."""
    cur = start
    while cur <= end:
        stop = min(cur + datetime.timedelta(days=WINDOW_DAYS - 1), end)
        yield cur, stop
        cur = stop + datetime.timedelta(days=1)


def fetch(frm, to, retries=8):
    url = URL.format(frm=fmt(frm), to=fmt(to))
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                body = resp.read()
            if body.startswith(FIRST_LINE_PREFIX.encode()):
                return body
        except (urllib.error.URLError, OSError):
            pass
        time.sleep(min(60, 5 * (attempt + 1)))
    raise RuntimeError(f"giving up on {frm}..{to}")


def download_window(window):
    frm, to = window
    out = RAW_DIR / f"amfi_{frm:%Y%m%d}_{to:%Y%m%d}.txt.gz"
    if out.exists():
        return 0
    body = fetch(frm, to)
    tmp = out.with_suffix(".tmp")
    with gzip.open(tmp, "wb") as fh:
        fh.write(body)
    tmp.rename(out)
    print(f"{out.name}: {len(body) / 1e6:.1f} MB", flush=True)
    return len(body)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=datetime.date.fromisoformat, default=datetime.date(2018, 1, 1))
    ap.add_argument("--end", type=datetime.date.fromisoformat, default=datetime.date(2025, 12, 31))
    ap.add_argument("--workers", type=int, default=2)
    args = ap.parse_args()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        total = sum(pool.map(download_window, list(windows(args.start, args.end))))
    print(f"downloaded {total / 1e6:.0f} MB this run", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
