"""Live price lookup with alternatives, quality checks and fallbacks. Always reports date, source and age."""
import os
import datetime as dt
import pandas as pd
import requests
from dotenv import load_dotenv
from . import db, quality

load_dotenv(os.path.join(db.BASE, ".env"))
KEY = os.environ.get("DATAGOV_API_KEY")
RESOURCE_ID = os.environ.get("DATAGOV_RESOURCE_ID", "9ef84268-d588-465a-a308-a864a43d0070")
URL = f"https://api.data.gov.in/resource/{RESOURCE_ID}"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json",
}
LIVE_MAX_AGE_DAYS = 2        # newer than this counts as live


def _api_rows(commodity, state=None, max_pages=20):
    rows, offset = [], 0
    for _ in range(max_pages):
        params = {"api-key": KEY, "format": "json", "limit": 500, "offset": offset,
                  "filters[commodity]": commodity.title()}
        if state:
            params["filters[state]"] = state.title()
        r = requests.get(URL, params=params, headers=HEADERS, timeout=(8, 25))
        r.raise_for_status()
        recs = r.json().get("records", [])
        rows += recs
        offset += len(recs)
        if len(recs) < 500:
            break
    return rows


def _match(d, text):
    t = text.lower().strip()
    return d[d["market"].str.lower().str.contains(t, regex=False)
             | d["district"].str.lower().str.contains(t, regex=False)]


def _age(date_iso):
    return (dt.date.today() - dt.date.fromisoformat(date_iso)).days


def _fetch(commodity, state=None):
    """None = API unreachable or unusable. Empty DataFrame = reachable but no rows."""
    if not KEY:
        return None
    try:
        rows = _api_rows(commodity, state)
    except (requests.RequestException, ValueError):
        return None
    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    try:
        d = db.normalize(raw)
        db.upsert(raw, "live_lookup")              # every lookup grows the history
    except ValueError:
        return None
    if state:                                      # enforce the state filter ourselves
        d = d[d["state"].str.lower() == state.lower().strip()]
    return d


def _db_latest(commodity, market):
    con = db.connect()
    like = f"%{market.lower().strip()}%"
    q = pd.read_sql_query(
        "SELECT date, market, modal_price FROM prices "
        "WHERE lower(commodity)=? AND (lower(market) LIKE ? OR lower(district) LIKE ?) "
        "ORDER BY date DESC LIMIT 50",
        con, params=(commodity.lower(), like, like))
    con.close()
    if q.empty:
        return None
    last = q[q["date"] == q["date"].max()]
    return {"price": float(last["modal_price"].mean()), "date": last["date"].iloc[0],
            "market": last["market"].iloc[0], "source": "stored database",
            "age_days": _age(last["date"].iloc[0]), "is_live": False}


def _ranked(today):
    clean = today[~today["suspect"]]
    prices = clean.groupby("market")["modal_price"].mean().round(0).sort_values(ascending=False)
    excluded = int(today[today["suspect"]]["market"].nunique())
    return prices, excluded


def lookup(commodity, market, state=None):
    out = {"hit": None, "stored": None, "api_ok": False, "states": {}, "others": [],
           "state_markets": [], "excluded": 0}
    d = _fetch(commodity, state)
    if d is not None:
        out["api_ok"] = True
        if not d.empty:
            d = quality.mark_suspect(d)
            latest = d["date"].max()
            hit = _match(d, market)
            if not hit.empty:
                last = hit[hit["date"] == hit["date"].max()]
                age = _age(last["date"].iloc[0])
                out["hit"] = {"price": float(last["modal_price"].mean()), "date": last["date"].iloc[0],
                              "market": last["market"].iloc[0], "state": last["state"].iloc[0],
                              "age_days": age, "is_live": age <= LIVE_MAX_AGE_DAYS,
                              "source": "live API", "n_varieties": len(last),
                              "suspect": bool(last["suspect"].mean() > 0.5),
                              "ref": float(last["ref"].iloc[0])}
                today = d[(d["state"] == out["hit"]["state"]) & (d["date"] == latest)]
                prices, out["excluded"] = _ranked(today)
                out["others"] = [(m, float(p)) for m, p in prices.items()
                                 if m != out["hit"]["market"]][:5]
            else:
                out["states"] = (d.groupby("state")["market"].nunique()
                                 .sort_values(ascending=False).head(8).to_dict())
                if state:
                    today = d[d["date"] == latest]
                    prices, out["excluded"] = _ranked(today)
                    out["state_markets"] = [(m, float(p)) for m, p in prices.items()][:10]
    if out["hit"] is None:
        out["stored"] = _db_latest(commodity, market)
    return out


def get_price(commodity, market, state=None):
    r = lookup(commodity, market, state)
    return r["hit"] or r["stored"]
