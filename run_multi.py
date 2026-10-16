import re, glob, os, math, pandas as pd, numpy as np, runpy
import src.config as C, src.db as db, src.realdata as rd

HOME, RADIUS_KM, MIN_OBS, ROAD = "ALIGARH", 400, 400, 1.3   # edit HOME / RADIUS_KM as you like

# Approximate city coordinates (lat, lon). Add more lines for markets that get reported as missing.
COORDS = {"DELHI":(28.61,77.21),"ALIGARH":(27.88,78.08),"AGRA":(27.18,78.01),"MUMBAI":(19.08,72.88),
 "PUNE":(18.52,73.86),"LUCKNOW":(26.85,80.95),"BAREILLY":(28.37,79.43),"KOLHAPUR":(16.70,74.24),
 "RAJKOT":(22.30,70.80),"SURAT":(21.17,72.83),"HUBLI":(15.36,75.12),"FARUKHABAD":(27.39,79.58),
 "ETAWAH":(26.78,79.02),"DEORIA":(26.50,83.78),"MAINPURI":(27.23,79.02),"GURGAON":(28.46,77.03),
 "FARIDABAD":(28.41,77.31),"KANPUR":(26.45,80.35),"JAIPUR":(26.91,75.79),"AHMEDABAD":(23.02,72.57),
 "NASHIK":(20.00,73.79),"AMRITSAR":(31.63,74.87),"AJMER":(26.45,74.64),"ALWAR":(27.55,76.63),
 "AHMEDNAGAR":(19.09,74.74),"AURANGABAD":(19.88,75.34),"ALLAHABAD":(25.44,81.85),"BALLIA":(25.76,84.15),
 "ABOHAR":(30.14,74.19),"ASANSOL":(23.68,86.98),"LASALGAON":(20.14,74.23),"MEERUT":(28.98,77.71)}

def key(name): return re.sub(r"\(.*?\)|[^A-Z ]", "", str(name).upper()).strip()
def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    x = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(x))
def crop_name(fn):
    w = os.path.basename(fn).lower().split("_")[0]
    w = w[:-2] if w.endswith("oes") else (w[:-1] if w.endswith("s") else w)
    return w.title()

frames = []
for p in glob.glob("data/real/*.csv"):
    b = os.path.basename(p).lower()
    if "_all_clean" in b or "case_study" in b: continue
    df = pd.read_csv(p, low_memory=False)
    find = lambda *k: next((c for c in df.columns if any(x in c.lower() for x in k)), None)
    dc, mc, pc, ac = find("date"), find("market", "centre", "center"), find("modal"), find("arriv")
    if not (dc and mc and pc):
        print("SKIPPED (cannot find date/market/modal columns):", b, list(df.columns)); continue
    frames.append(pd.DataFrame({
        "date": pd.to_datetime(df[dc], format="mixed", dayfirst=True, errors="coerce"),
        "market": df[mc].map(key), "modal": pd.to_numeric(df[pc], errors="coerce"),
        "arrivals": pd.to_numeric(df[ac], errors="coerce") if ac else np.nan,
        "commodity": crop_name(p)}))
al = pd.concat(frames).dropna(subset=["date", "modal"])
al = al.drop_duplicates(["commodity", "market", "date"])

S, DIST, missing, dropped = {}, {}, set(), []
for (c, m), g in al.groupby(["commodity", "market"]):
    if len(g) < MIN_OBS: continue
    if m not in COORDS: missing.add(m); continue
    d = round(ROAD * hav(COORDS[HOME], COORDS[m]))
    if d > RADIUS_KM: continue
    DIST[m] = d
    g = g.set_index("date").sort_index()[["modal", "arrivals"]]
    n_obs = len(g)
    g = g.asfreq("D").interpolate(method="time", limit=7).dropna(subset=["modal"])
    g["arrivals"] = g["arrivals"].fillna(g["arrivals"].median())
    g = g.rename(columns={"modal": "modal_price", "arrivals": "arrivals_qtl"})
    g["rainfall_mm"] = 0.0; g.index.name = "date"; g.attrs["observed"] = n_obs
    S[(c, m)] = g[["modal_price", "arrivals_qtl", "rainfall_mm"]]

assump = getattr(C, "ASSUMP", {})
crops = []
for c in sorted({c for c, _ in S}):
    if (c, HOME) not in S: print(f"Skipping {c}: no {HOME} series with >= {MIN_OBS} observed days"); continue
    if c not in assump: print(f"Skipping {c}: no spoilage/storage entry in ASSUMP in src/config.py"); continue
    crops.append(c)
if missing: print("Markets with enough data but no coordinates (add to COORDS):", sorted(missing))
print("Crops:", crops, "| markets within", RADIUS_KM, "km of", HOME, ":", sorted(DIST))

C.HOME, C.COMMODITIES = HOME, crops
C.MARKETS = sorted({m for (c, m) in S if c in crops})
C.DIST_KM = DIST          # approximate road km = 1.3 x straight line  (PLACEHOLDER)
db.load_from_db = lambda *a, **k: None
rd.load_real = lambda *a, **k: S
runpy.run_path("run_day2.py", run_name="__main__")
