"""Nightly collector: every commodity, every state. Saves to the SQLite DB."""
import os, time, requests, pandas as pd
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
from src import db

KEY = os.getenv("DATAGOV_API_KEY")
RID = os.getenv("DATAGOV_RESOURCE_ID") or "9ef84268-d588-465a-a308-a864a43d0070"
URL = f"https://api.data.gov.in/resource/{RID}"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Accept": "application/json"}
SEED = ["Wheat", "Rice", "Paddy(Dhan)(Common)", "Maize", "Bajra(Pearl Millet/Cumbu)", "Jowar(Sorghum)", "Barley (Jau)",
        "Bengal Gram(Gram)(Whole)", "Arhar (Tur/Red Gram)(Whole)", "Green Gram (Moong)(Whole)", "Black Gram (Urd Beans)(Whole)",
        "Lentil (Masur)(Whole)", "Soyabean", "Groundnut", "Mustard", "Sunflower", "Sesamum(Sesame,Gingelly,Til)", "Cotton",
        "Onion", "Potato", "Tomato", "Cauliflower", "Cabbage", "Brinjal", "Bhindi(Ladies Finger)", "Green Chilli", "Carrot",
        "Cucumbar(Kheera)", "Garlic", "Ginger(Green)", "Peas Wet", "Banana", "Apple", "Mango", "Orange", "Grapes",
        "Pomegranate", "Papaya", "Lemon", "Coriander(Leaves)", "Turmeric", "Dry Chillies", "Cummin Seed(Jeera)", "Coconut"]

def get(params):
    for t in range(3):
        try:
            r = requests.get(URL, params=params, headers=H, timeout=(8, 40))
            if r.status_code == 200:
                return r.json().get("records", [])
        except Exception:
            pass
        time.sleep(2 * (t + 1))
    return None

def pull(commodity=None, cap=10000, page=1000):
    rows, off = [], 0
    while off < cap:
        p = {"api-key": KEY, "format": "json", "limit": page, "offset": off}
        if commodity:
            p["filters[commodity]"] = commodity
        rec = get(p)
        if not rec:
            break
        rows += rec
        if len(rec) < page:
            break
        off += page
        time.sleep(0.3)
    return rows

if not KEY:
    raise SystemExit("DATAGOV_API_KEY missing in .env")
names = set(SEED)
disc = pull()
names |= {r.get("commodity") for r in disc if r.get("commodity")}
print(f"{time.strftime('%Y-%m-%d %H:%M')} discovered {len(names)} commodity names")
total, got = 0, 0
for c in sorted(names):
    rows = pull(c)
    if not rows:
        continue
    df = pd.DataFrame(rows)
    db.upsert(df, "collect_all")
    total += len(df); got += 1
    print(f"  {c}: {len(df)} rows")
print(f"DONE: {total} rows across {got} commodities")
