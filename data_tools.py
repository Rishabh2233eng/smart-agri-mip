"""Usage:
  python data_tools.py ping                  # 1 request: is the key/resource/network OK?
  python data_tools.py probe                 # does the API serve old dates?
  python data_tools.py snapshot              # save today's prices
  python data_tools.py backfill --days 730   # try to pull history (resumable)
  python data_tools.py import <file|folder>  # load downloaded CSV/XLSX files
  python data_tools.py stats                 # days per crop and market

File naming for imports (used only if the file lacks commodity/market columns):
  commodity_market.csv   e.g. wheat_faridabad.csv
"""
import argparse
import datetime as dt
import glob
import os
import sys
import time
import pandas as pd
import requests
from dotenv import load_dotenv
from src import db

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
KEY = os.environ.get("DATAGOV_API_KEY")
RESOURCE_ID = os.environ.get("DATAGOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
STATES = ["Haryana", "Delhi", "Uttar Pradesh"]
COMMODITIES = ["Wheat", "Onion", "Tomato"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}


def need_key():
    if not KEY:
        sys.exit("Put DATAGOV_API_KEY=... in the .env file")


def get(params, tries=3):
    """GET with short timeouts and retries."""
    last = None
    for i in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=(10, 30))
            if r.status_code in (429, 500, 502, 503, 504):
                raise requests.RequestException(f"HTTP {r.status_code}")
            return r
        except requests.RequestException as e:
            last = e
            time.sleep(3 * (i + 1))
    raise last


def fetch(filters):
    rows, offset = [], 0
    while True:
        p = {"api-key": KEY, "format": "json", "limit": 500, "offset": offset}
        p.update({f"filters[{k}]": v for k, v in filters.items()})
        r = get(p)
        r.raise_for_status()
        recs = r.json().get("records", [])
        rows += recs
        offset += len(recs)
        if len(recs) < 500:
            break
        time.sleep(0.3)
    return rows


def cmd_ping():
    need_key()
    print("Resource id in use:", RESOURCE_ID)
    t = time.time()
    try:
        r = requests.get(URL, params={"api-key": KEY, "format": "json", "limit": 1},
                         headers=HEADERS, timeout=(10, 40))
    except requests.RequestException as e:
        print(f"FAILED after {time.time() - t:.0f}s: {type(e).__name__}")
        print("-> Server unreachable or too slow. Try: phone hotspot, VPN off, retry in 30 min, "
              "or use the CEDA downloads instead.")
        return
    print(f"HTTP {r.status_code} in {time.time() - t:.1f}s")
    print(r.text[:400])
    if r.status_code in (401, 403):
        print("-> Key rejected. Regenerate it on data.gov.in and update .env")
    elif r.status_code == 404:
        print("-> Resource id wrong. Copy the id from the dataset's API tab into .env as DATAGOV_RESOURCE_ID=...")
    elif r.status_code == 200:
        print("-> Works. Now run: python data_tools.py probe")


def cmd_probe():
    need_key()
    today = dt.date.today()
    for back in (0, 1, 7, 30, 90, 365, 730):
        d = today - dt.timedelta(days=back)
        try:
            recs = fetch({"state": "Haryana", "commodity": "Wheat", "arrival_date": f"{d:%d/%m/%Y}"})
        except requests.RequestException as e:
            print(f"{d} ({back:>3} days ago): request failed ({type(e).__name__})")
            continue
        dates = sorted({r.get("arrival_date") for r in recs})[:3]
        print(f"{d} ({back:>3} days ago): {len(recs):>4} records, dates: {dates}")
    print("\nIf old dates return 0 records, the API holds only recent data: use downloads + daily snapshots.")


def cmd_snapshot():
    need_key()
    total = 0
    for s in STATES:
        for c in COMMODITIES:
            try:
                recs = fetch({"state": s, "commodity": c})
            except requests.RequestException as e:
                print(f"{s} / {c}: failed ({type(e).__name__}), skipping")
                continue
            n = db.upsert(pd.DataFrame(recs), "datagov_snapshot") if recs else 0
            total += n
            print(f"{s} / {c}: {n} rows saved")
    print("Total saved:", total)


def cmd_backfill(days):
    need_key()
    today = dt.date.today()
    empty_streak = 0
    for back in range(0, days + 1):
        d = today - dt.timedelta(days=back)
        got_any = False
        for s in STATES:
            for c in COMMODITIES:
                if db.has_rows(d.isoformat(), s, c):
                    got_any = True
                    continue
                try:
                    recs = fetch({"state": s, "commodity": c, "arrival_date": f"{d:%d/%m/%Y}"})
                except requests.RequestException as e:
                    print(f"{d} {s}/{c}: failed ({type(e).__name__}), will be retried on the next run")
                    got_any = True      # a failure is not evidence of "no data"
                    continue
                if recs:
                    db.upsert(pd.DataFrame(recs), "datagov_backfill")
                    got_any = True
                time.sleep(0.3)
        empty_streak = 0 if got_any else empty_streak + 1
        if back % 10 == 0:
            print(f"{d}: done (empty streak {empty_streak})")
        if empty_streak >= 14:
            print("14 empty days in a row -> API has no history beyond this point. Stopping.")
            break


def cmd_import(path):
    if os.path.isfile(path):
        files = [path]
    else:
        files = glob.glob(os.path.join(path, "*.csv")) + glob.glob(os.path.join(path, "*.xlsx"))
    if not files:
        print("No .csv or .xlsx files found in", path)
        return
    for f in files:
        name = os.path.basename(f)
        if name.lower() == "rainfall.csv":
            continue
        raw = pd.read_excel(f) if f.lower().endswith(".xlsx") else pd.read_csv(f)
        parts = os.path.splitext(name)[0].split("_")
        hints = {"commodity": parts[0].title(), "market": parts[1].title() if len(parts) > 1 else None}
        try:
            n = db.upsert(raw, name, hints=hints)
        except ValueError as e:
            print(f"{name}: SKIPPED - {e}")
            continue
        print(f"{name}: {n} rows imported")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("ping")
    sub.add_parser("probe")
    sub.add_parser("snapshot")
    sub.add_parser("stats")
    b = sub.add_parser("backfill")
    b.add_argument("--days", type=int, default=365)
    i = sub.add_parser("import")
    i.add_argument("path")
    a = ap.parse_args()
    if a.cmd == "ping":
        cmd_ping()
    elif a.cmd == "probe":
        cmd_probe()
    elif a.cmd == "snapshot":
        cmd_snapshot()
    elif a.cmd == "backfill":
        cmd_backfill(a.days)
    elif a.cmd == "import":
        cmd_import(a.path)
    elif a.cmd == "stats":
        print(db.stats().to_string(index=False))