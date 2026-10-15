import pandas as pd, numpy as np, runpy
import src.config as cfg, src.db as db, src.realdata as rd

df = pd.read_csv("data/real/onions_all_clean.csv", parse_dates=["date"])
KEEP = {"ALIGARH(UP)": "ALIGARH", "DELHI": "DELHI", "AGRA(UP)": "AGRA"}
df = df[df.market.isin(KEEP)].copy()
df["market"] = df.market.map(KEEP)

S = {}
for m, g in df.groupby("market"):
    g = g.set_index("date").sort_index()[["modal", "arrivals"]]
    observed = len(g)
    g = g.asfreq("D")
    # fill gaps up to 7 days by time interpolation; longer gaps are dropped
    g = g.interpolate(method="time", limit=7).dropna(subset=["modal"])
    g["arrivals"] = g["arrivals"].fillna(g["arrivals"].median())
    g = g.rename(columns={"modal": "modal_price", "arrivals": "arrivals_qtl"})
    g["rainfall_mm"] = 0.0          # no real rainfall in this dataset
    g.index.name = "date"
    g.attrs["observed"] = observed
    S[("Onion", m)] = g[["modal_price", "arrivals_qtl", "rainfall_mm"]]

cfg.HOME = "ALIGARH"
cfg.MARKETS = ["ALIGARH", "DELHI", "AGRA"]
cfg.COMMODITIES = ["Onion"]
cfg.DIST_KM = {"ALIGARH": 0, "DELHI": 130, "AGRA": 85}   # PLACEHOLDER distances
db.load_from_db = lambda *a, **k: None
rd.load_real = lambda *a, **k: S
runpy.run_path("run_day2.py", run_name="__main__")
