"""Builds the real-data case study (any crop file in data/real, markets near HOME) and points src.config at it."""
import re, glob, os, math
import numpy as np, pandas as pd
import src.config as C

COORDS = {"DELHI":(28.61,77.21),"ALIGARH":(27.88,78.08),"AGRA":(27.18,78.01),"MUMBAI":(19.08,72.88),
 "PUNE":(18.52,73.86),"LUCKNOW":(26.85,80.95),"BAREILLY":(28.37,79.43),"KOLHAPUR":(16.70,74.24),
 "RAJKOT":(22.30,70.80),"SURAT":(21.17,72.83),"HUBLI":(15.36,75.12),"FARUKHABAD":(27.39,79.58),
 "ETAWAH":(26.78,79.02),"DEORIA":(26.50,83.78),"MAINPURI":(27.23,79.02),"GURGAON":(28.46,77.03),
 "FARIDABAD":(28.41,77.31),"KANPUR":(26.45,80.35),"JAIPUR":(26.91,75.79),"AHMEDABAD":(23.02,72.57),
 "NASHIK":(20.00,73.79),"AMRITSAR":(31.63,74.87),"AJMER":(26.45,74.64),"ALWAR":(27.55,76.63),
 "AHMEDNAGAR":(19.09,74.74),"AURANGABAD":(19.88,75.34),"ALLAHABAD":(25.44,81.85),"BALLIA":(25.76,84.15),
 "ABOHAR":(30.14,74.19),"ASANSOL":(23.68,86.98),"LASALGAON":(20.14,74.23),"MEERUT":(28.98,77.71)}

def key(name):
    return re.sub(r"\(.*?\)|[^A-Z ]", "", str(name).upper()).strip()

def hav(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    x = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 6371 * 2 * math.asin(math.sqrt(x))

def crop_name(fn):
    w = os.path.basename(fn).lower().split("_")[0]
    w = w[:-2] if w.endswith("oes") else (w[:-1] if w.endswith("s") else w)
    return w.title()

def setup(home="ALIGARH", radius_km=400, min_obs=400, road=1.3, folder="data/real"):
    frames = []
    for p in glob.glob(os.path.join(folder, "*.csv")):
        b = os.path.basename(p).lower()
        if "_all_clean" in b or "case_study" in b:
            continue
        df = pd.read_csv(p, low_memory=False)
        find = lambda *k: next((c for c in df.columns if any(x in c.lower() for x in k)), None)
        dc, mc, pc, ac = find("date"), find("market", "centre", "center"), find("modal"), find("arriv")
        if not (dc and mc and pc):
            print("SKIPPED (no date/market/modal columns):", b, list(df.columns))
            continue
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(df[dc], format="mixed", dayfirst=True, errors="coerce"),
            "market": df[mc].map(key),
            "modal": pd.to_numeric(df[pc], errors="coerce"),
            "arrivals": pd.to_numeric(df[ac], errors="coerce") if ac else np.nan,
            "commodity": crop_name(p)}))
    al = pd.concat(frames).dropna(subset=["date", "modal"]).drop_duplicates(["commodity", "market", "date"])
    S, DIST, missing = {}, {}, set()
    for (c, m), g in al.groupby(["commodity", "market"]):
        if len(g) < min_obs:
            continue
        if m not in COORDS:
            missing.add(m); continue
        d = round(road * hav(COORDS[home], COORDS[m]))
        if d > radius_km:
            continue
        DIST[m] = d
        g = g.set_index("date").sort_index()[["modal", "arrivals"]]
        n_obs = len(g); obs_idx = pd.DatetimeIndex(g.index)
        g = g.asfreq("D").interpolate(method="time", limit=7).dropna(subset=["modal"])
        g["arrivals"] = g["arrivals"].fillna(g["arrivals"].median())
        g = g.rename(columns={"modal": "modal_price", "arrivals": "arrivals_qtl"})
        g["rainfall_mm"] = _rain(m, g.index)
        g.index.name = "date"
        g.attrs["observed"] = n_obs; g.attrs["obs_dates"] = obs_idx
        S[(c, m)] = g[["modal_price", "arrivals_qtl", "rainfall_mm"]]
    assump = getattr(C, "ASSUMP", {})
    crops = [c for c in sorted({c for c, _ in S}) if (c, home) in S and c in assump]
    C.HOME, C.COMMODITIES = home, crops
    C.MARKETS = sorted({m for (c, m) in S if c in crops})
    C.DIST_KM = DIST
    return S, crops, missing


def _rain(m, idx):
    p = os.path.join("data", "weather", f"{m}.csv")
    if not os.path.exists(p):
        return 0.0
    w = pd.read_csv(p, parse_dates=["date"]).set_index("date")["rain_mm"]
    return w.reindex(idx).fillna(0.0).to_numpy()

