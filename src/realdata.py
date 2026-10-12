"""Loads real mandi price CSVs from data/real/*.csv (any number of files, they are stacked).
Optional: data/real/rainfall.csv with columns date,rainfall_mm."""
import glob
import os
import numpy as np
import pandas as pd
from .config import ALIASES, MARKET_ALIASES

RENAME = {
    "arrival_date": "date", "price date": "date", "reported date": "date", "date": "date",
    "commodity": "commodity", "commodity name": "commodity",
    "market": "market", "market name": "market", "mandi": "market",
    "modal_price": "modal_price", "modal price": "modal_price",
    "modal price (rs./quintal)": "modal_price",
    "arrivals_qtl": "arrivals_qtl", "arrivals": "arrivals_tonnes",
    "arrivals (tonnes)": "arrivals_tonnes", "rainfall_mm": "rainfall_mm",
}


def _read_all(folder):
    files = [f for f in glob.glob(os.path.join(folder, "*.csv"))
             if os.path.basename(f).lower() != "rainfall.csv"]
    frames = []
    for f in files:
        d = pd.read_csv(f)
        d.columns = [RENAME.get(c.strip().lower(), c.strip().lower()) for c in d.columns]
        frames.append(d.loc[:, ~d.columns.duplicated()])
    return pd.concat(frames, ignore_index=True) if frames else None


def _make_series(agg, c, m, rain, max_fill=7):
    g = agg[(agg.commodity == c) & (agg.market == m)].set_index("date").sort_index()
    g = g[["modal_price", "arrivals_qtl", "rainfall_mm"]].asfreq("D")
    g = g.ffill(limit=max_fill)                       # fill short gaps only
    if rain is not None:
        g["rainfall_mm"] = rain.reindex(g.index)
    ok = g["modal_price"].notna()
    grp = (ok != ok.shift()).cumsum()
    runs = g[ok].groupby(grp[ok]).size()
    if runs.empty:
        return None
    best = runs.idxmax()                              # keep longest gap-free stretch
    g = g[ok & (grp == best)].copy()
    g["arrivals_qtl"] = g["arrivals_qtl"].replace(0, np.nan)
    med = g["arrivals_qtl"].median()
    g["arrivals_qtl"] = g["arrivals_qtl"].fillna(1.0 if np.isnan(med) else med)
    g["rainfall_mm"] = g["rainfall_mm"].fillna(0.0)
    return g


def load_real(folder="data/real"):
    raw = _read_all(folder)
    if raw is None:
        return None
    missing = {"date", "commodity", "market", "modal_price"} - set(raw.columns)
    if missing:
        raise ValueError(f"Missing columns {missing}. Columns found: {list(raw.columns)}. "
                         "Edit RENAME in src/realdata.py to map your column names.")
    raw["date"] = pd.to_datetime(raw["date"], dayfirst=True, errors="coerce")
    raw["modal_price"] = pd.to_numeric(raw["modal_price"], errors="coerce")
    raw = raw.dropna(subset=["date", "modal_price"])
    raw = raw[raw["modal_price"] > 0].copy()
    if "arrivals_qtl" not in raw.columns:
        if "arrivals_tonnes" in raw.columns:
            raw["arrivals_qtl"] = pd.to_numeric(raw["arrivals_tonnes"], errors="coerce") * 10
        else:
            raw["arrivals_qtl"] = np.nan
    raw["arrivals_qtl"] = pd.to_numeric(raw["arrivals_qtl"], errors="coerce")
    if "rainfall_mm" not in raw.columns:
        raw["rainfall_mm"] = np.nan

    cl = raw["commodity"].astype(str).str.strip().str.lower()
    raw["c_std"] = cl.map(lambda x: next((k for k, v in ALIASES.items() if x in v), None))
    ml = raw["market"].astype(str).str.lower()
    raw["m_std"] = ml.map(lambda x: next((k for k, v in MARKET_ALIASES.items()
                                          if any(a in x for a in v)), None))
    keep = raw.dropna(subset=["c_std", "m_std"])
    if keep.empty:
        print("No rows matched your crops/markets. Commodities in file:",
              sorted(raw["commodity"].astype(str).unique())[:20])
        print("Markets in file:", sorted(raw["market"].astype(str).unique())[:20])
        raise ValueError("Fix ALIASES / MARKET_ALIASES in src/config.py")

    agg = (keep.groupby(["c_std", "m_std", "date"])
               .agg(modal_price=("modal_price", "mean"),
                    arrivals_qtl=("arrivals_qtl", lambda s: s.sum(min_count=1)),
                    rainfall_mm=("rainfall_mm", "mean"))
               .reset_index().rename(columns={"c_std": "commodity", "m_std": "market"}))

    rain = None
    rp = os.path.join(folder, "rainfall.csv")
    if os.path.exists(rp):
        r = pd.read_csv(rp)
        r.columns = [c.strip().lower() for c in r.columns]
        r["date"] = pd.to_datetime(r["date"], dayfirst=True, errors="coerce")
        rain = r.dropna(subset=["date"]).drop_duplicates("date").set_index("date")["rainfall_mm"]

    S = {}
    for (c, m), _ in agg.groupby(["commodity", "market"]):
        g = _make_series(agg, c, m, rain)
        if g is None or g.empty:
            continue
        sub = agg[(agg.commodity == c) & (agg.market == m)]
        g.attrs["observed"] = int(sub["date"].between(g.index[0], g.index[-1]).sum())
        S[(c, m)] = g
    return S