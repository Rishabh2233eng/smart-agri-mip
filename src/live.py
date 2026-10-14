"""Live price lookup with alternatives, quality checks and fallbacks. Always reports date, source and age."""
import os
import time
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
LAST_ERROR = ""              # why the last live fetch failed (shown to the user)


def _get(params, tries=2):
    """GET with retries for slow or failing servers. Client errors (401/403/404) are not retried."""
    last = None
    for _ in range(tries):
        try:
            r = requests.get(URL, params=params, headers=HEADERS, timeout=(6, 15))
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            last = e
            code = e.response.status_code if e.response is not None else 500
            if code < 500 and code != 429:
                break
        except requests.RequestException as e:
            last = e
        time.sleep(2)
    raise last


def _api_rows(commodity, state=None, max_pages=20):
    rows, offset = [], 0
    for _ in range(max_pages):
        params = {"api-key": KEY, "format": "json", "limit": 500, "offset": offset,
                  "filters[commodity]": commodity.title()}
        if state:
            params["filters[state]"] = state.title()
        recs = _get(params).json().get("records", [])
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
    """None = live API failed (reason in LAST_ERROR). Empty DataFrame = reachable but no rows."""
    global LAST_ERROR
    LAST_ERROR = ""
    if not KEY:
        LAST_ERROR = "no API key found in the .env file"
        return None
    try:
        rows = _api_rows(commodity, state)
    except requests.Timeout:
        LAST_ERROR = "the government server did not answer in time"
        return None
    except requests.HTTPError as e:
        code = e.response.status_code if e.response is not None else "?"
        LAST_ERROR = f"the server returned HTTP {code}" + (" (API key rejected)" if code in (401, 403) else "")
        return None
    except requests.RequestException as e:
        LAST_ERROR = "network problem (" + type(e).__name__ + ")"
        return None
    except ValueError:
        LAST_ERROR = "the server sent a response we could not read"
        return None
    if not rows:
        return pd.DataFrame()
    raw = pd.DataFrame(rows)
    try:
        d = db.normalize(raw)
        db.upsert(raw, "live_lookup")              # every lookup grows the history
    except ValueError as e:
        LAST_ERROR = "the data format changed (" + str(e)[:80] + ")"
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
    out = {"hit": None, "stored": None, "api_ok": False, "error": "", "states": {}, "others": [],
           "state_markets": [], "excluded": 0}
    d = _fetch(commodity, state)
    out["error"] = LAST_ERROR
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
