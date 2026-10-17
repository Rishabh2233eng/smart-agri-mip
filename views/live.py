import os, time, html, requests, pandas as pd, streamlit as st
from dotenv import load_dotenv
import dbinfo

load_dotenv()
KEY = os.getenv("DATAGOV_API_KEY")
URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
H = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Accept": "application/json"}

st.title("Live mandi price")
st.caption("Real quotes from the government mandi feed (data.gov.in), in Rs per quintal as reported.")

def get(params):
    err = "unknown error"
    for t in range(3):
        try:
            r = requests.get(URL, params=params, headers=H, timeout=(8, 40))
            if r.status_code == 200:
                return r.json().get("records", []), None
            err = f"HTTP {r.status_code}"
        except Exception as e:
            err = type(e).__name__
        time.sleep(1.5 * (t + 1))
    return None, err

@st.cache_data(ttl=600, show_spinner=False)
def fetch(commodity):
    if not KEY:
        raise RuntimeError("DATAGOV_API_KEY is missing in .env")
    rows, off = [], 0
    while off < 10000:
        rec, err = get({"api-key": KEY, "format": "json", "limit": 1000, "offset": off, "filters[commodity]": commodity})
        if rec is None:
            raise RuntimeError(err)
        rows += rec
        if len(rec) < 1000:
            break
        off += 1000
    df = pd.DataFrame(rows)
    if not df.empty:
        try:
            from src import db
            db.upsert(df.copy(), "live_lookup")
        except Exception:
            pass
    return df

def norm(df):
    o = pd.DataFrame({"state": df.get("state", ""), "market": df.get("market", ""),
                      "variety": df.get("variety", ""), "grade": df.get("grade", ""),
                      "min": pd.to_numeric(df.get("min_price"), errors="coerce"),
                      "modal": pd.to_numeric(df.get("modal_price"), errors="coerce"),
                      "max": pd.to_numeric(df.get("max_price"), errors="coerce"),
                      "date": pd.to_datetime(df.get("arrival_date"), dayfirst=True, errors="coerce")})
    return o.dropna(subset=["modal", "date"])

names = dbinfo.commodities() if dbinfo.available() else []
options = names or ["Onion", "Potato", "Tomato", "Wheat"]
crop = st.selectbox("Commodity", options, index=options.index("Onion") if "Onion" in options else 0)

df, err, mode = None, None, "live"
try:
    with st.spinner("Fetching live prices..."):
        raw = fetch(crop)
    if raw.empty:
        err = "the feed has no quotes for this commodity today"
    else:
        df = norm(raw)
except Exception as e:
    err = str(e)
if df is None or df.empty:
    st.warning(f"Live feed unavailable ({err}). Showing the last stored prices if we have any.")
    df = dbinfo.commodity_df(crop) if dbinfo.available() else pd.DataFrame()
    mode = "stored"
if df.empty:
    st.info("No prices found for this commodity."); st.stop()

df = df[df["date"] == df.groupby("market")["date"].transform("max")]
states = sorted(s for s in df["state"].dropna().unique() if s)
c1, c2 = st.columns(2)
sel_state = c1.selectbox("State", ["All states"] + states)
pool = df if sel_state == "All states" else df[df["state"] == sel_state]
markets = sorted(pool["market"].dropna().unique())
sel_market = c2.selectbox("Market", markets)
rows = pool[pool["market"] == sel_market]

price = float(rows["modal"].median())
date = rows["date"].max()
today = pd.Timestamp.now(tz="Asia/Kolkata").tz_localize(None).normalize()
age = max((today - date).days, 0)
med = float(pool["modal"].median())
suspect = len(pool) >= 5 and (price > 2 * med or price < 0.5 * med)
badge = '<span class="badge live">LIVE</span>' if (mode == "live" and age <= 1) else f'<span class="badge stale">{age} days old</span>'
if suspect:
    badge += '<span class="badge warn">Unusual quote</span>'
st.markdown(f'<div class="card"><h4>{html.escape(str(sel_market))} &middot; {html.escape(str(crop))}</h4>'
            f'<div class="price">Rs {price:,.0f}<span style="font-size:1.1rem;font-weight:400"> per quintal</span>{badge}</div>'
            f'<p>Quote date {date.date()} &middot; min Rs {rows["min"].min() if "min" in rows else float("nan"):,.0f} &middot; max Rs {rows["max"].max() if "max" in rows else float("nan"):,.0f}</p></div>',
            unsafe_allow_html=True)
if suspect:
    st.warning(f"This price is far from the typical Rs {med:,.0f} for {sel_state}. Treat it with caution.")

mm = pool.groupby("market")["modal"].median().sort_values(ascending=False)
if len(mm) > 1:
    rank = int(list(mm.index).index(sel_market)) + 1
    diff = (price / med - 1) * 100
    st.write(f"Ranks **#{rank} of {len(mm)}** markets in {sel_state if sel_state != 'All states' else 'India'}, {diff:+.0f}% versus the median of Rs {med:,.0f}.")
    st.subheader("Comparison with other markets")
    st.bar_chart(mm.head(15))
with st.expander("All quotes for this market"):
    cols = [c for c in ("variety", "grade", "min", "modal", "max") if c in rows]
    st.dataframe(rows[cols], hide_index=True, use_container_width=True)
