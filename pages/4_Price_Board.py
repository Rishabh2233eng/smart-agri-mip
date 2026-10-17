import sqlite3, pandas as pd, streamlit as st

st.set_page_config(page_title="Price board", layout="wide")
st.title("All-commodity price board (real data)")
st.caption("Prices collected nightly from the government mandi feed, in Rs per quintal as reported. "
           "Quotes far from the day's median are flagged and left out of rankings. Varieties and grades are mixed.")

@st.cache_resource
def conn():
    return sqlite3.connect("data/mandi.db", check_same_thread=False)

def main_table():
    c = conn()
    names = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")]
    best, n = None, -1
    for t in names:
        k = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if k > n:
            best, n = t, k
    return best

T = main_table()
if not T:
    st.error("Database is empty. Run: python collect_all.py"); st.stop()
cols = [r[1] for r in conn().execute(f'PRAGMA table_info("{T}")')]
def pick(*keys):
    return next((c for c in cols if any(k in c.lower() for k in keys)), None)
cD, cM, cC, cS, cP = pick("date"), pick("market"), pick("commodity"), pick("state"), pick("modal")
if not all([cD, cM, cC, cP]):
    st.error(f"Unexpected database columns: {cols}"); st.stop()

@st.cache_data(ttl=600)
def commodities():
    return [r[0] for r in conn().execute(f'SELECT DISTINCT "{cC}" FROM "{T}" ORDER BY 1') if r[0]]

cl = commodities()
crop = st.selectbox("Commodity (type to search)", cl, index=cl.index("Onion") if "Onion" in cl else 0)

@st.cache_data(ttl=600)
def load(crop):
    d = pd.read_sql_query(f'SELECT * FROM "{T}" WHERE "{cC}" = ?', conn(), params=(crop,))
    d[cD] = pd.to_datetime(d[cD], errors="coerce")
    d[cP] = pd.to_numeric(d[cP], errors="coerce")
    return d.dropna(subset=[cD, cP]).query(f'`{cP}` > 0').copy()

d = load(crop)
if d.empty:
    st.warning("No data for this commodity yet."); st.stop()
med = d.groupby(cD)[cP].transform("median")
cnt = d.groupby(cD)[cP].transform("count")
d["suspect"] = (cnt >= 10) & ((d[cP] > 2 * med) | (d[cP] < 0.5 * med))
last = d[cD].max()
today = d[d[cD] == last]
good = today[~today["suspect"]]

a, b, c, e = st.columns(4)
a.metric("Latest date", str(last.date()))
b.metric("Markets reporting", int(today[cM].nunique()))
c.metric("Median price (Rs/qtl)", f"{good[cP].median():.0f}" if len(good) else "n/a")
e.metric("Quotes flagged", int(today["suspect"].sum()))

if cS:
    st.subheader("By state")
    g = (good.groupby(cS)[cP].agg(median="median", lowest="min", highest="max", quotes="count")
         .sort_values("median", ascending=False).round(0))
    st.dataframe(g, use_container_width=True)

mm = good.groupby([cM] + ([cS] if cS else []))[cP].median().sort_values().round(0).reset_index()
l, r = st.columns(2)
l.subheader("Highest-priced markets")
l.dataframe(mm.tail(10).iloc[::-1], use_container_width=True, hide_index=True)
r.subheader("Lowest-priced markets")
r.dataframe(mm.head(10), use_container_width=True, hide_index=True)

st.subheader("National median price over time")
h = d[~d["suspect"]].groupby(cD)[cP].median()
if len(h) > 1:
    st.line_chart(h)
else:
    st.info("Only one day of data so far. This chart grows every night as the collector runs.")
