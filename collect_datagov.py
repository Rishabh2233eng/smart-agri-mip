import os
import sys
import time
import datetime as dt
import requests
import pandas as pd

API_KEY = os.environ.get("DATAGOV_API_KEY")
RESOURCE_ID = "9ef84268-d588-465a-a308-a864a43d0070"   # verify on the dataset's API tab on data.gov.in
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
STATES = ["Haryana", "Delhi", "Uttar Pradesh"]
COMMODITIES = ["Wheat", "Onion", "Tomato"]

if not API_KEY:
    sys.exit("Set your key first:  $env:DATAGOV_API_KEY='your_key'")


def fetch(state, commodity):
    rows, offset = [], 0
    while True:
        r = requests.get(URL, params={
            "api-key": API_KEY, "format": "json", "limit": 500, "offset": offset,
            "filters[state]": state, "filters[commodity]": commodity}, timeout=60)
        r.raise_for_status()
        recs = r.json().get("records", [])
        if not recs:
            break
        rows += recs
        offset += len(recs)
        if len(recs) < 500:
            break
        time.sleep(0.5)
    return rows


all_rows = []
for s in STATES:
    for c in COMMODITIES:
        got = fetch(s, c)
        print(f"{s} / {c}: {len(got)} records")
        all_rows += got

if not all_rows:
    sys.exit("No records returned. Check the API key, the resource id and the field names.")

df = pd.DataFrame(all_rows)
os.makedirs("data/real", exist_ok=True)
path = f"data/real/datagov_{dt.date.today():%Y%m%d}.csv"
df.to_csv(path, index=False)
print("\nSaved", path, "| columns:", list(df.columns))
print("\nMarkets found (use these names in src/config.py):")
print(df.groupby(["commodity", "market"]).size().to_string())