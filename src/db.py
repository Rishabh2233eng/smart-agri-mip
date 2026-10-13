"""SQLite store for mandi prices. Upserts, so re-running imports never duplicates rows."""
import os
import sqlite3
import numpy as np
import pandas as pd
from .realdata import RENAME, _make_series
from .config import ALIASES, MARKET_ALIASES

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "mandi.db")
COLS = ["date", "state", "district", "market", "commodity", "variety", "grade",
        "min_price", "max_price", "modal_price", "arrivals_qtl"]


def connect(path=DB):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    con = sqlite3.connect(path)
    con.execute("""CREATE TABLE IF NOT EXISTS prices(
        date TEXT, state TEXT, district TEXT, market TEXT, commodity TEXT, variety TEXT, grade TEXT,
        min_price REAL, max_price REAL, modal_price REAL, arrivals_qtl REAL, source TEXT,
        PRIMARY KEY(date, market, commodity, variety, grade))""")
    return con


def normalize(df, hints=None):
    hints = hints or {}
    df = df.copy()
    df.columns = [RENAME.get(str(c).strip().lower(), str(c).strip().lower()) for c in df.columns]
    df = df.loc[:, ~df.columns.duplicated()]
    if "market" not in df.columns and "district" in df.columns:
        df["market"] = df["district"]       # district-level downloads: each district is a market
    for k in ("commodity", "market"):
        if k not in df.columns and hints.get(k):
            df[k] = hints[k]                # fall back to the file name
    missing = [c for c in ("date", "modal_price", "market", "commodity") if c not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing}; columns found: {list(df.columns)}. "
                         "Add them to RENAME in src/realdata.py or name the file commodity_market.csv")
    for c in ("state", "district", "variety", "grade"):
        if c not in df.columns:
            df[c] = ""
    if "arrivals_qtl" not in df.columns:
        df["arrivals_qtl"] = (pd.to_numeric(df["arrivals_tonnes"], errors="coerce") * 10
                              if "arrivals_tonnes" in df.columns else np.nan)
    for c in ("min_price", "max_price", "modal_price", "arrivals_qtl"):
        df[c] = pd.to_numeric(df[c], errors="coerce") if c in df.columns else np.nan
    df["date"] = pd.to_datetime(df["date"], dayfirst=True, errors="coerce")
    df = df.dropna(subset=["date", "modal_price", "market", "commodity"])
    df = df[df["modal_price"] > 0].copy()
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")
    for c in ("state", "district", "variety", "grade", "market", "commodity"):
        df[c] = df[c].fillna("").astype(str).str.strip()
    return df[COLS]


def upsert(df, source, path=DB, hints=None):
    d = normalize(df, hints)
    if d.empty:
        return 0
    d["source"] = source
    rows = d[COLS + ["source"]].astype(object).where(d.notna(), None).values.tolist()
    con = connect(path)
    con.executemany("INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", rows)
    con.commit()
    con.close()
    return len(rows)


def has_rows(date_iso, state, commodity, path=DB):
    con = connect(path)
    r = con.execute("SELECT 1 FROM prices WHERE date=? AND state=? AND commodity=? LIMIT 1",
                    (date_iso, state, commodity)).fetchone()
    con.close()
    return r is not None


def stats(path=DB, top=60):
    con = connect(path)
    q = pd.read_sql_query(
        "SELECT commodity, market, MIN(date) AS start, MAX(date) AS end, COUNT(DISTINCT date) AS days "
        "FROM prices GROUP BY commodity, market ORDER BY days DESC", con)
    con.close()
    return q.head(top)


def read_agg(path=DB):
    con = connect(path)
    d = pd.read_sql_query("SELECT date, market, commodity, modal_price, arrivals_qtl FROM prices", con)
    con.close()
    if d.empty:
        return d
    d["date"] = pd.to_datetime(d["date"])
    d["commodity"] = d["commodity"].str.strip().str.lower().map(
        lambda x: next((k for k, v in ALIASES.items() if x in v), None))
    d["market"] = d["market"].str.lower().map(
        lambda x: next((k for k, v in MARKET_ALIASES.items() if any(a in x for a in v)), None))
    d = d.dropna(subset=["commodity", "market"])
    if d.empty:
        return d
    d["rainfall_mm"] = np.nan
    return (d.groupby(["commodity", "market", "date"])
             .agg(modal_price=("modal_price", "mean"),
                  arrivals_qtl=("arrivals_qtl", lambda s: s.sum(min_count=1)),
                  rainfall_mm=("rainfall_mm", "mean")).reset_index())


def load_from_db(path=DB, rain_csv="data/real/rainfall.csv"):
    if not os.path.exists(path):
        return None
    agg = read_agg(path)
    if agg.empty:
        return None
    rain = None
    if os.path.exists(rain_csv):
        r = pd.read_csv(rain_csv)
        r.columns = [c.strip().lower() for c in r.columns]
        r["date"] = pd.to_datetime(r["date"], dayfirst=True, errors="coerce")
        rain = r.dropna(subset=["date"]).drop_duplicates("date").set_index("date")["rainfall_mm"]
    S = {}
    for (c, m), sub in agg.groupby(["commodity", "market"]):
        g = _make_series(agg, c, m, rain)
        if g is None or g.empty:
            continue
        g.attrs["observed"] = int(sub["date"].between(g.index[0], g.index[-1]).sum())
        S[(c, m)] = g
    return S