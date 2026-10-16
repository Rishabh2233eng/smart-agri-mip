"""Daily rainfall per market from Open-Meteo (free, no key). Run once; files go to data/weather."""
import os, time, requests, pandas as pd
from src.casestudy import COORDS
START, END = "2019-12-01", "2022-08-31"
os.makedirs("data/weather", exist_ok=True)
for m, (lat, lon) in COORDS.items():
    out = f"data/weather/{m}.csv"
    if os.path.exists(out):
        continue
    try:
        r = requests.get("https://archive-api.open-meteo.com/v1/archive", timeout=60, params={
            "latitude": lat, "longitude": lon, "start_date": START, "end_date": END,
            "daily": "precipitation_sum", "timezone": "Asia/Kolkata"})
        j = r.json()["daily"]
        pd.DataFrame({"date": j["time"], "rain_mm": j["precipitation_sum"]}).to_csv(out, index=False)
        print("saved", m)
    except Exception as e:
        print("FAILED", m, type(e).__name__, str(e)[:80])
    time.sleep(1)
