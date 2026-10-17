import os, sqlite3, pandas as pd
PATH = "data/mandi.db"

def available():
    return os.path.exists(PATH)

def conn():
    return sqlite3.connect(PATH, check_same_thread=False)

def table(c):
    best, n = None, -1
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        k = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if k > n:
            best, n = t, k
    return best

def mapcols(cols):
    pick = lambda *k: next((c for c in cols if any(x in c.lower() for x in k)), None)
    return {"D": pick("date"), "M": pick("market"), "C": pick("commodity"), "S": pick("state"), "P": pick("modal")}

def parse_dates(s):
    s = s.astype(str)
    d = pd.to_datetime(s, errors="coerce", format="ISO8601")
    bad = d.isna()
    if bad.any():
        d[bad] = pd.to_datetime(s[bad], errors="coerce", format="%d/%m/%Y")
    return d

def _setup():
    c = conn(); t = table(c)
    if not t:
        c.close(); return None, None, None
    cols = [r[1] for r in c.execute(f'PRAGMA table_info("{t}")')]
    return c, t, mapcols(cols)

def summary():
    c, t, m = _setup()
    if not c or not all([m["C"], m["M"], m["D"]]):
        return None
    r = c.execute(f'SELECT COUNT(*), COUNT(DISTINCT "{m["C"]}"), COUNT(DISTINCT "{m["M"]}"), COUNT(DISTINCT "{m["D"]}"), MIN("{m["D"]}"), MAX("{m["D"]}") FROM "{t}"').fetchone()
    c.close()
    return dict(rows=r[0], commodities=r[1], markets=r[2], days=r[3], first=r[4], last=r[5])

def commodities():
    c, t, m = _setup()
    if not c or not m["C"]:
        return []
    out = [r[0] for r in c.execute(f'SELECT DISTINCT "{m["C"]}" FROM "{t}" ORDER BY 1') if r[0]]
    c.close()
    return out

def commodity_df(name):
    c, t, m = _setup()
    if not c or not all([m["C"], m["M"], m["D"], m["P"]]):
        return pd.DataFrame()
    d = pd.read_sql_query(f'SELECT * FROM "{t}" WHERE "{m["C"]}" = ?', c, params=(name,))
    c.close()
    out = pd.DataFrame({"date": parse_dates(d[m["D"]]), "market": d[m["M"]],
                        "modal": pd.to_numeric(d[m["P"]], errors="coerce")})
    out["state"] = d[m["S"]] if m["S"] else ""
    for k in ("variety", "grade"):
        out[k] = d[k] if k in d else ""
    return out.dropna(subset=["date", "modal"])
