import os, time, html, sqlite3, requests
import pandas as pd, streamlit as st
import plotly.graph_objects as go
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="SmartAgri Market Intelligence", page_icon="🌾", layout="wide")

GREEN, AMBER, DARK, RED, GREY, SAND = "#2F7D5B", "#E0A526", "#14231F", "#B5443A", "#5B6B65", "#E1DED0"
CYCLE = [GREEN, AMBER, "#3C6E9F", RED, "#7B5EA7", "#2A9D8F", "#8D6E63", "#546E7A"]

st.markdown("""<style>
#MainMenu {visibility: hidden;} footer {visibility: hidden;}
.block-container {padding-top: 2rem; max-width: 1200px;}
.hero {background: linear-gradient(135deg,#14231F 0%,#2F7D5B 100%); padding:30px 34px; border-radius:18px; margin-bottom:22px;}
.hero h1 {color:#F6F4EC; font-size:2.1rem; margin:0 0 6px 0; padding:0;}
.hero p {color:#D6E3DC; font-size:1.05rem; margin:0;}
.card {background:#fff; border:1px solid #E1DED0; border-radius:16px; padding:20px 22px; height:100%;}
.card h4 {margin:0 0 8px 0; color:#2F7D5B;} .card p {margin:0; color:#33433D;}
.price {font-size:3rem; font-weight:700; color:#14231F; line-height:1.15;}
.badge {display:inline-block; padding:3px 12px; border-radius:999px; font-size:.85rem; font-weight:600; margin-left:8px;}
.live {background:#DFF2E8; color:#1B6B45;} .stale {background:#FBE9C6; color:#7A5200;} .warn {background:#F8D9D4; color:#8A2B1E;}
.kpi {background:#fff; border:1px solid #E1DED0; border-radius:14px; padding:14px 18px;}
.kpi .v {font-size:1.7rem; font-weight:700; color:#14231F;} .kpi .l {color:#5B6B65; font-size:.85rem;}
.flow {display:flex; align-items:stretch; gap:10px; flex-wrap:wrap; margin:8px 0 24px;}
.step {flex:1; min-width:150px; background:#fff; border:1px solid #E1DED0; border-radius:14px; padding:14px 16px;}
.step b {display:block; color:#2F7D5B; margin-bottom:4px;} .step span {font-size:.85rem; color:#33433D;}
.arrow {align-self:center; color:#2F7D5B; font-size:1.4rem;}
</style>""", unsafe_allow_html=True)


# ---------- small UI helpers ----------
def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)

def kpi(col, value, label):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)

def card(col, title, body):
    col.markdown(f'<div class="card"><h4>{title}</h4><p>{body}</p></div>', unsafe_allow_html=True)

def flow(steps):
    items = '<div class="arrow">&rarr;</div>'.join(f'<div class="step"><b>{t}</b><span>{d}</span></div>' for t, d in steps)
    st.markdown(f'<div class="flow">{items}</div>', unsafe_allow_html=True)


# ---------- chart helpers ----------
def _base(fig, h=360, title=None):
    fig.update_layout(height=h, margin=dict(l=10, r=10, t=60 if title else 24, b=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Segoe UI, Inter, sans-serif", color=DARK),
                      legend=dict(orientation="h", y=1.12, x=0), hoverlabel=dict(bgcolor="white"))
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=16, color=DARK)))
    fig.update_xaxes(gridcolor=SAND, zeroline=False)
    fig.update_yaxes(gridcolor=SAND, zeroline=False)
    return fig

def bar_compare(s, highlight=None, title=None):
    s = s.sort_values()
    colors = [AMBER if i == highlight else GREEN for i in s.index]
    fig = go.Figure(go.Bar(x=s.values, y=[str(i) for i in s.index], orientation="h", marker_color=colors,
                           hovertemplate="%{y}: Rs %{x:,.0f}<extra></extra>"))
    fig.update_xaxes(title="Rs per quintal")
    return _base(fig, max(300, 26 * len(s) + 80), title)

def lines(wide, title=None):
    fig = go.Figure()
    for i, c in enumerate(wide.columns):
        fig.add_trace(go.Scatter(x=wide.index, y=wide[c], name=str(c), mode="lines",
                                 line=dict(color=CYCLE[i % len(CYCLE)], width=2)))
    fig.update_yaxes(title="Rs per quintal")
    return _base(fig, 380, title)

def fan(o, h=7, title=None):
    x = o.index + pd.Timedelta(days=h)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=o["p_hi"], line=dict(width=0), hoverinfo="skip", showlegend=False))
    fig.add_trace(go.Scatter(x=x, y=o["p_lo"], fill="tonexty", fillcolor="rgba(47,125,91,0.18)",
                             line=dict(width=0), name="80% interval", hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=x, y=o["p_med"], line=dict(color=GREEN, width=2), name="Forecast"))
    fig.add_trace(go.Scatter(x=x, y=o["actual"], line=dict(color=DARK, width=1.5), name="Actual"))
    fig.update_yaxes(title="Rs per quintal")
    return _base(fig, 380, title)

def grouped(res, ycol, lo, hi, ytitle, title, ref=None, rng=None):
    fig = go.Figure()
    for h, col in ((7, GREEN), (14, AMBER)):
        x = res[res.h == h].sort_values("market")
        fig.add_trace(go.Bar(name=f"{h} day", x=x["market"], y=x[ycol], marker_color=col,
                             error_y=dict(type="data", symmetric=False, array=(x[hi] - x[ycol]).clip(lower=0),
                                          arrayminus=(x[ycol] - x[lo]).clip(lower=0), color=GREY, thickness=1.2)))
    if ref is not None:
        fig.add_hline(y=ref[0], line_dash="dash", line_color=RED if ref[0] else DARK, annotation_text=ref[1])
    fig.update_layout(barmode="group")
    fig.update_yaxes(title=ytitle, range=rng)
    return _base(fig, 380, title)

def gain_chart(res, title=None):
    return grouped(res, "gain_pts", "gain_lo", "gain_hi", "Error reduction vs naive (points)", title, ref=(0, "no gain"))

def coverage_chart(res, title=None):
    return grouped(res, "cov_rolling_%", "cov_lo", "cov_hi", "Interval coverage (%)", title, ref=(80, "target 80%"), rng=[0, 105])

def option_chart(rec):
    lab = rec["market"].astype(str) + " / " + rec["sell_after_days"].astype(int).astype(str) + "d"
    fig = go.Figure()
    fig.add_trace(go.Bar(name="Expected net", x=lab, y=rec["exp_net_per_qtl"], marker_color=GREEN))
    fig.add_trace(go.Bar(name="Worst case", x=lab, y=rec["worst_net_per_qtl"], marker_color=AMBER))
    fig.update_layout(barmode="group")
    fig.update_yaxes(title="Net Rs per quintal")
    return _base(fig, 340)


# ---------- database helpers ----------
DB = "data/mandi.db"

def db_ok():
    return os.path.exists(DB)

def _open():
    c = sqlite3.connect(DB, check_same_thread=False)
    best, n = None, -1
    for (t,) in c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
        k = c.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
        if k > n:
            best, n = t, k
    if not best:
        c.close(); return None, None, None
    cols = [r[1] for r in c.execute(f'PRAGMA table_info("{best}")')]
    pick = lambda *k: next((x for x in cols if any(y in x.lower() for y in k)), None)
    return c, best, {"D": pick("date"), "M": pick("market"), "C": pick("commodity"), "S": pick("state"), "P": pick("modal")}

def parse_dates(s):
    s = s.astype(str)
    d = pd.to_datetime(s, errors="coerce", format="ISO8601")
    bad = d.isna()
    if bad.any():
        d[bad] = pd.to_datetime(s[bad], errors="coerce", format="%d/%m/%Y")
    return d

@st.cache_data(ttl=300)
def db_summary():
    if not db_ok():
        return None
    c, t, m = _open()
    if not c or not all([m["C"], m["M"], m["D"]]):
        return None
    r = c.execute(f'SELECT COUNT(*), COUNT(DISTINCT "{m["C"]}"), COUNT(DISTINCT "{m["M"]}"), COUNT(DISTINCT "{m["D"]}"), MAX("{m["D"]}") FROM "{t}"').fetchone()
    c.close()
    return dict(rows=r[0], commodities=r[1], markets=r[2], days=r[3], last=r[4])

@st.cache_data(ttl=600)
def db_commodities():
    if not db_ok():
        return []
    c, t, m = _open()
    if not c or not m["C"]:
        return []
    out = [r[0] for r in c.execute(f'SELECT DISTINCT "{m["C"]}" FROM "{t}" ORDER BY 1') if r[0]]
    c.close()
    return out

@st.cache_data(ttl=600)
def db_commodity_df(name):
    if not db_ok():
        return pd.DataFrame()
    c, t, m = _open()
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


# ---------- page: overview ----------
def page_home():
    hero("Smart Agri Market Intelligence",
         "Real mandi prices, forecasts with honest uncertainty, and selling advice for farmers. Final-year major project, IILM University.")
    s = db_summary()
    k = st.columns(5)
    if s:
        kpi(k[0], f"{s['rows']:,}", "price quotes collected")
        kpi(k[1], f"{s['commodities']}", "commodities")
        kpi(k[2], f"{s['markets']:,}", "markets")
        kpi(k[3], f"{s['days']}", "days collected")
        kpi(k[4], str(s["last"])[:10], "latest data")
    else:
        st.info("No database yet. Run python collect_all.py once to start collecting real prices.")

    st.subheader("How it works")
    flow([("Collect", "Government mandi feed every night, every commodity"),
          ("Clean", "Unusual quotes flagged against the market's own range"),
          ("Forecast", "Quantile boosting with a conformal 80% range"),
          ("Decide", "Net profit after transport, storage, spoilage"),
          ("Advise", "Dashboard for farmers and evaluators")])
    a, b, c = st.columns(3)
    card(a, "Real prices, live", "Today's quote from the government mandi feed for any commodity, with stale-data and outlier warnings.")
    card(b, "Forecast with uncertainty", "Not just one number: a price range that is checked against what actually happened.")
    card(c, "Where and when to sell", "Every option is scored on money in hand after costs and risk, tuned to how cautious the farmer is.")

    st.subheader("Evaluation on real history")
    st.caption("Onion, daily prices 2020 to 2022, markets within 400 km of Aligarh. Scored on real quotes only. Error bars are 95% block-bootstrap intervals.")
    p = "outputs/real/eval_all_markets.csv"
    if os.path.exists(p):
        r = pd.read_csv(p)
        k = st.columns(4)
        for col, h in zip(k[:2], (7, 14)):
            x = r[r.h == h]
            kpi(col, f"{int((x.gain_pts > 0).sum())} of {len(x)}", f"markets where the model beats naive ({h} day)")
        for col, h in zip(k[2:], (7, 14)):
            x = r[r.h == h]
            kpi(col, f"{x['cov_rolling_%'].mean():.1f}%", f"mean interval coverage ({h} day, target 80%)")
        st.write("")
        l, rt = st.columns(2)
        l.plotly_chart(gain_chart(r, "Error reduction vs naive forecast"), width="stretch")
        rt.plotly_chart(coverage_chart(r, "80% interval coverage"), width="stretch")
        st.caption("Preliminary: bars whose error bars cross zero are not yet statistically proven. More history is being added.")
        ab = "outputs/real/ablation_weather.csv"
        if os.path.exists(ab):
            with st.expander("Does real rainfall help the forecast?"):
                st.plotly_chart(gain_chart(pd.read_csv(ab), "Error reduction from adding rainfall"), width="stretch")
    else:
        st.info("Run python eval_all.py to generate these results.")
    with st.expander("Nightly collector status"):
        if os.path.exists("snapshot.log"):
            st.code("".join(open("snapshot.log", errors="ignore").readlines()[-12:]) or "(empty)")
        else:
            st.write("No snapshot.log yet.")


# ---------- page: live price ----------
KEY = os.getenv("DATAGOV_API_KEY")
URL = "https://api.data.gov.in/resource/9ef84268-d588-465a-a308-a864a43d0070"
HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124 Safari/537.36", "Accept": "application/json"}

def api_get(params):
    err = "unknown error"
    for t in range(3):
        try:
            r = requests.get(URL, params=params, headers=HDR, timeout=(8, 40))
            if r.status_code == 200:
                return r.json().get("records", []), None
            err = f"HTTP {r.status_code}"
        except Exception as e:
            err = type(e).__name__
        time.sleep(1.5 * (t + 1))
    return None, err

@st.cache_data(ttl=600, show_spinner=False)
def fetch_live(commodity):
    if not KEY:
        raise RuntimeError("DATAGOV_API_KEY is missing in .env")
    rows, off = [], 0
    while off < 10000:
        rec, err = api_get({"api-key": KEY, "format": "json", "limit": 1000, "offset": off, "filters[commodity]": commodity})
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

def norm_live(df):
    o = pd.DataFrame({"state": df.get("state", ""), "market": df.get("market", ""),
                      "variety": df.get("variety", ""), "grade": df.get("grade", ""),
                      "min": pd.to_numeric(df.get("min_price"), errors="coerce"),
                      "modal": pd.to_numeric(df.get("modal_price"), errors="coerce"),
                      "max": pd.to_numeric(df.get("max_price"), errors="coerce"),
                      "date": pd.to_datetime(df.get("arrival_date"), dayfirst=True, errors="coerce")})
    return o.dropna(subset=["modal", "date"])

def page_live():
    st.title("Live mandi price")
    st.caption("Real quotes from the government mandi feed (data.gov.in), in Rs per quintal as reported.")
    names = db_commodities()
    options = names or ["Onion", "Potato", "Tomato", "Wheat"]
    crop = st.selectbox("Commodity", options, index=options.index("Onion") if "Onion" in options else 0)
    df, err, mode = None, None, "live"
    try:
        with st.spinner("Fetching live prices..."):
            raw = fetch_live(crop)
        if raw.empty:
            err = "the feed has no quotes for this commodity today"
        else:
            df = norm_live(raw)
    except Exception as e:
        err = str(e)
    if df is None or df.empty:
        st.warning(f"Live feed unavailable ({err}). Showing the last stored prices if we have any.")
        df = db_commodity_df(crop)
        mode = "stored"
    if df.empty:
        st.info("No prices found for this commodity."); st.stop()
    df = df[df["date"] == df.groupby("market")["date"].transform("max")]
    states = sorted(s for s in df["state"].dropna().unique() if s)
    c1, c2 = st.columns(2)
    sel_state = c1.selectbox("State", ["All states"] + states)
    pool = df if sel_state == "All states" else df[df["state"] == sel_state]
    sel_market = c2.selectbox("Market", sorted(pool["market"].dropna().unique()))
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
    lo_p = rows["min"].min() if "min" in rows else float("nan")
    hi_p = rows["max"].max() if "max" in rows else float("nan")
    st.markdown(f'<div class="card"><h4>{html.escape(str(sel_market))} &middot; {html.escape(str(crop))}</h4>'
                f'<div class="price">Rs {price:,.0f}<span style="font-size:1.1rem;font-weight:400"> per quintal</span>{badge}</div>'
                f'<p>Quote date {date.date()} &middot; min Rs {lo_p:,.0f} &middot; max Rs {hi_p:,.0f}</p></div>', unsafe_allow_html=True)
    if suspect:
        st.warning(f"This price is far from the typical Rs {med:,.0f} for {sel_state}. Treat it with caution.")
    mm = pool.groupby("market")["modal"].median().sort_values(ascending=False)
    if len(mm) > 1:
        rank = int(list(mm.index).index(sel_market)) + 1
        st.write(f"Ranks **#{rank} of {len(mm)}** markets in {sel_state if sel_state != 'All states' else 'India'}, "
                 f"{(price / med - 1) * 100:+.0f}% versus the median of Rs {med:,.0f}.")
        st.subheader("Comparison with other markets")
        st.plotly_chart(bar_compare(mm.head(15), highlight=sel_market), width="stretch")
    with st.expander("All quotes for this market"):
        st.dataframe(rows[[c for c in ("variety", "grade", "min", "modal", "max") if c in rows]], hide_index=True, width="stretch")


# ---------- page: price board ----------
def page_board():
    st.title("All-commodity price board")
    st.caption("Prices collected nightly from the government mandi feed, Rs per quintal as reported. "
               "Quotes far from the day's median are flagged and left out of rankings. Varieties and grades are mixed.")
    names = db_commodities()
    if not names:
        st.error("Database is empty. Run: python collect_all.py"); return
    crop = st.selectbox("Commodity (type to search)", names, index=names.index("Onion") if "Onion" in names else 0)
    d = db_commodity_df(crop)
    d = d[d["modal"] > 0].copy()
    if d.empty:
        st.warning("No data for this commodity yet."); return
    med = d.groupby("date")["modal"].transform("median")
    cnt = d.groupby("date")["modal"].transform("count")
    d["suspect"] = (cnt >= 10) & ((d["modal"] > 2 * med) | (d["modal"] < 0.5 * med))
    last = d["date"].max()
    today = d[d["date"] == last]
    good = today[~today["suspect"]]
    a, b, c, e = st.columns(4)
    kpi(a, str(last.date()), "latest date")
    kpi(b, int(today["market"].nunique()), "markets reporting")
    kpi(c, f"{good['modal'].median():,.0f}" if len(good) else "n/a", "median price (Rs/qtl)")
    kpi(e, int(today["suspect"].sum()), "quotes flagged")
    st.write("")
    if d["state"].astype(str).str.len().gt(0).any():
        st.subheader("By state")
        g = (good.groupby("state")["modal"].agg(median="median", lowest="min", highest="max", quotes="count")
             .sort_values("median", ascending=False).round(0))
        st.dataframe(g, width="stretch")
    mm = good.groupby("market")["modal"].median().sort_values().round(0).reset_index()
    l, r = st.columns(2)
    l.subheader("Highest-priced markets")
    l.dataframe(mm.tail(10).iloc[::-1], width="stretch", hide_index=True)
    r.subheader("Lowest-priced markets")
    r.dataframe(mm.head(10), width="stretch", hide_index=True)
    st.subheader("National median price over time")
    h = d[~d["suspect"]].groupby("date")["modal"].median()
    if len(h) > 1:
        st.plotly_chart(lines(h.to_frame("Median price")), width="stretch")
    else:
        st.info("Only one day of data so far. This chart grows every night as the collector runs.")


# ---------- page: market explorer ----------
@st.cache_resource(show_spinner="Loading real history...")
def load_hist():
    from src import casestudy
    S, crops, missing = casestudy.setup()
    return S, crops

def page_explorer():
    st.title("Market explorer (real history)")
    st.caption("Real daily mandi prices from public archives. Gaps up to 7 days are interpolated. Data ends where shown.")
    try:
        S, crops = load_hist()
    except Exception as e:
        st.error(f"Could not load history: {e}"); return
    if not crops:
        st.error("No crop data found in data/real."); return
    import src.config as C
    crop = st.selectbox("Crop", crops)
    mk = sorted(m for (c, m) in S if c == crop)
    sel = st.multiselect("Markets", mk, default=mk[:4])
    if not sel:
        st.info("Pick at least one market."); return
    px = lambda m: pd.Series(S[(crop, m)]["modal_price"].to_numpy(), index=S[(crop, m)].index)
    wide = pd.concat({m: px(m) for m in sel}, axis=1, sort=True)
    lo, hi = wide.index.min().date(), wide.index.max().date()
    rng = st.slider("Date range", lo, hi, (lo, hi))
    wide = wide.loc[str(rng[0]):str(rng[1])]
    st.subheader("Price per quintal (Rs)")
    st.plotly_chart(lines(wide), width="stretch")
    cols = st.columns(len(sel))
    for col, m in zip(cols, sel):
        s = wide[m].dropna()
        if len(s) > 31:
            col.metric(m, f"Rs {s.iloc[-1]:.0f}", f"{(s.iloc[-1] / s.iloc[-31] - 1) * 100:+.1f}% vs 30 days")
    st.subheader("Seasonality: average price by month (1.0 = overall average)")
    m0 = st.selectbox("Market for seasonality", sel)
    s = px(m0)
    st.bar_chart((s.groupby(s.index.month).mean() / s.mean()).rename("price index"))
    if (crop, C.HOME) in S:
        st.subheader(f"Price gap versus {C.HOME} (positive = higher than home)")
        gap = wide.sub(px(C.HOME).reindex(wide.index), axis=0).drop(columns=[C.HOME], errors="ignore")
        if gap.shape[1]:
            st.plotly_chart(lines(gap), width="stretch")


# ---------- page: forecast and decision ----------
@st.cache_resource(show_spinner="Training models on real history. The first load takes a minute or two...")
def load_forecasts():
    from src import casestudy
    import src.config as C
    S, crops, missing = casestudy.setup()
    from src.forecast import run_forecasts
    from src.decision import HORIZONS
    data = {}
    for c in crops:
        mk = [m for m in C.MARKETS if (c, m) in S]
        if C.HOME not in mk or len(mk) < 2:
            continue
        fc = {(m, h): run_forecasts(S[(c, m)], h) for m in mk for h in HORIZONS}
        data[c] = (mk, fc, S[(c, C.HOME)].index[-1].date())
    return data

def page_forecast():
    hero("Forecast and selling decision",
         "The model forecasts the price with an 80% range, then ranks where and when to sell after transport, storage and spoilage.")
    st.info("Historical case study: real daily prices up to the date shown, not today's prices. Costs and distances are placeholder assumptions.")
    try:
        data = load_forecasts()
    except Exception as e:
        st.error(f"Could not build forecasts: {e}"); return
    if not data:
        st.error("No crop has enough real history yet. Check data/real and src/config.py (ASSUMP)."); return
    import src.config as C
    from src.forecast import metrics
    from src.decision import recommend
    x1, x2, x3 = st.columns(3)
    crop = x1.selectbox("Crop", list(data))
    qty = x2.number_input("Quantity (quintals)", 1, 5000, 50)
    lam = x3.slider("Caution (0 = chase profit, 1 = play safe)", 0.0, 1.0, 0.5, 0.05)
    mk, fc, last_date = data[crop]
    st.caption(f"Home market: {C.HOME}. Data as of {last_date}. Markets considered: {', '.join(mk)}.")
    price_now = {m: fc[(m, 7)]["last"][0] for m in mk}
    latest = {k: v["last"][1:] for k, v in fc.items()}
    rec = recommend(crop, qty, mk, price_now, latest, lam=lam).head(6)
    best = rec.iloc[0]
    st.markdown(
        f'<div class="card"><h4>Recommended</h4>'
        f'<div class="price">{best["market"]}<span style="font-size:1.2rem;font-weight:400"> sell after {int(best["sell_after_days"])} days</span></div>'
        f'<p>Expected net Rs {best["exp_net_per_qtl"]:,.0f} per quintal &middot; worst case Rs {best["worst_net_per_qtl"]:,.0f} '
        f'&middot; about Rs {best["expected_total_Rs"]:,.0f} for {qty} quintals</p></div>', unsafe_allow_html=True)
    st.write("")
    st.plotly_chart(option_chart(rec), width="stretch")
    with st.expander("Full table of options"):
        st.dataframe(rec, width="stretch", hide_index=True)
    t7, t14 = st.tabs(["7 day forecast", "14 day forecast"])
    for tab, h in ((t7, 7), (t14, 14)):
        with tab:
            o = fc[(C.HOME, h)]["out"].tail(220)
            st.plotly_chart(fan(o, h, f"{crop} at {C.HOME}: {h} day forecast against what happened"), width="stretch")
            st.caption("How accurate has it been on past data?")
            st.dataframe(pd.DataFrame([metrics(fc[(C.HOME, h)]["out"])]).round(2), hide_index=True, width="stretch")


# ---------- page: about ----------
def page_about():
    st.title("About this system")
    st.markdown("""
**Smart Agri Market Intelligence Platform** helps a farmer decide where and when to sell.

**Data.** Live prices come from the government mandi feed (data.gov.in). History comes from public Agmarknet-based archives and a nightly collection made by this system. Quotes far from the day's range are flagged.

**Forecast.** Quantile gradient boosting predicts the 7 and 14 day price change with an 80% range, calibrated with a rolling conformal method. Real rainfall is an input.

**Decision.** Each option (market, days to wait) is scored on net money after transport, storage, spoilage and commission, and can be tuned for risk.

**Limits (please read).**
- Forecast results are preliminary: the gain over a simple baseline is not yet statistically proven.
- Costs and distances are placeholder assumptions.
- Historical pages use data that ends in 2022. Only the live pages use today's data.
- This is decision support, not financial advice.
""")



# ---------- page: market pulse ----------
@st.cache_data(ttl=600)
def pulse_table():
    if not db_ok():
        return pd.DataFrame()
    c, t, m = _open()
    if not c or not all([m["C"], m["M"], m["D"], m["P"]]):
        return pd.DataFrame()
    d = pd.read_sql_query(f'SELECT "{m["C"]}" c, "{m["M"]}" m, "{m["D"]}" d, "{m["P"]}" p' + (f', "{m["S"]}" s' if m["S"] else "") + f' FROM "{t}"', c)
    c.close()
    d["d"] = parse_dates(d["d"]); d["p"] = pd.to_numeric(d["p"], errors="coerce")
    if "s" not in d: d["s"] = ""
    return d.dropna(subset=["d", "p"]).query("p > 0")

def page_pulse():
    hero("Market pulse", "What is moving in Indian mandis right now: biggest price changes, state comparison, and whether today's price is high or low.")
    d = pulse_table()
    if d.empty:
        st.info("No data yet. Run python collect_all.py."); return
    g = d.groupby(["c", "d"])["p"].agg(med="median", n="count").reset_index()
    rows = []
    for c, x in g.groupby("c"):
        x = x[x.n >= 5].sort_values("d")
        if len(x) >= 2:
            a, b = x.iloc[-2], x.iloc[-1]
            rows.append((c, b.med, (b.med / a.med - 1) * 100, b.n, str(b.d.date())))
    mv = pd.DataFrame(rows, columns=["commodity", "price_now", "change_pct", "markets", "date"])
    mv = mv[mv.change_pct.abs() < 60]
    st.subheader("Biggest movers since the previous collection")
    if mv.empty:
        st.info("Need at least two collected days to show movers.")
    else:
        l, r = st.columns(2)
        up = mv.nlargest(8, "change_pct").sort_values("change_pct")
        dn = mv.nsmallest(8, "change_pct").sort_values("change_pct", ascending=False)
        for col, x, color, ttl in ((l, up, GREEN, "Rising"), (r, dn, RED, "Falling")):
            f = go.Figure(go.Bar(x=x.change_pct, y=x.commodity, orientation="h", marker_color=color,
                                 hovertemplate="%{y}: %{x:+.1f}%<extra></extra>"))
            f.update_xaxes(title="Change in national median (%)")
            col.plotly_chart(_base(f, 330, ttl), width="stretch")
        st.download_button("Download movers (CSV)", mv.round(2).to_csv(index=False), "movers.csv", "text/csv")
    st.subheader("Compare states and judge today's price")
    names = sorted(d["c"].unique())
    crop = st.selectbox("Commodity", names, index=names.index("Onion") if "Onion" in names else 0, key="pulse_crop")
    x = d[d.c == crop]
    last = x.d.max()
    today = x[x.d == last]
    med = today.p.median()
    today = today[(today.p < 2 * med) & (today.p > 0.5 * med)]
    stt = today[today.s.astype(str) != ""].groupby("s")["p"].median().sort_values()
    if len(stt) > 1:
        st.plotly_chart(bar_compare(stt.tail(20), title=f"{crop}: median price by state on {last.date()}"), width="stretch")
    mk = sorted(x.m.unique())
    m = st.selectbox("Your market", mk, key="pulse_mkt")
    hist = x[x.m == m].groupby("d")["p"].median()
    if len(hist) < 7:
        st.info(f"Only {len(hist)} days of history for this market so far. The high/low verdict unlocks after 7 days and gets better every night.")
    else:
        now = hist.iloc[-1]
        pct = (hist <= now).mean() * 100
        verdict = "HIGH: a good time to sell" if pct >= 75 else ("LOW: consider waiting" if pct <= 25 else "NORMAL")
        k = st.columns(3)
        kpi(k[0], f"Rs {now:,.0f}", f"latest price at {m}")
        kpi(k[1], f"{pct:.0f}th", f"percentile of its own {len(hist)}-day history")
        kpi(k[2], verdict.split(":")[0], verdict.split(": ")[-1] if ":" in verdict else "within its usual range")
        st.plotly_chart(lines(hist.to_frame(m)), width="stretch")
    st.caption("Based on prices this system has collected. It is a guide, not a guarantee.")


# ---------- page: research results ----------
def _pool(df, h):
    import numpy as np
    from math import comb
    g = df[df.h == h].gain_pts.dropna().to_numpy()
    if len(g) == 0:
        return None
    rng = np.random.default_rng(0)
    b = [rng.choice(g, len(g)).mean() for _ in range(4000)]
    k, n = int((g > 0).sum()), len(g)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n)
    return dict(h=h, markets=n, mean_gain=g.mean(), lo=float(np.percentile(b, 2.5)), hi=float(np.percentile(b, 97.5)), better=f"{k}/{n}", p=p)

def page_research():
    hero("Research results", "Honest evaluation on real history: forecast accuracy, interval reliability, and statistical tests. Everything here is computed from real prices.")
    p = "outputs/real/eval_all_markets.csv"
    if not os.path.exists(p):
        st.info("Run python eval_all.py to generate results."); return
    r = pd.read_csv(p)
    st.subheader("Pooled result across all markets")
    pr = [x for x in (_pool(r, 7), _pool(r, 14)) if x]
    k = st.columns(len(pr))
    for col, x in zip(k, pr):
        kpi(col, f"{x['mean_gain']:+.2f} pts", f"{x['h']} day: mean error reduction vs naive, 95% CI [{x['lo']:.2f}, {x['hi']:.2f}], better in {x['better']}, sign test p={x['p']:.3f}")
    st.caption("Markets are correlated, so these tests are indicative rather than strict. A confidence interval that excludes zero supports a real gain.")
    l, rt = st.columns(2)
    l.plotly_chart(gain_chart(r, "Error reduction per market"), width="stretch")
    rt.plotly_chart(coverage_chart(r, "80% interval coverage per market"), width="stretch")
    with st.expander("Per-market table", expanded=True):
        st.dataframe(r.round(2), hide_index=True, width="stretch")
        st.download_button("Download results (CSV)", r.round(3).to_csv(index=False), "eval_all_markets.csv", "text/csv")
    ab = "outputs/real/ablation_weather.csv"
    if os.path.exists(ab):
        a = pd.read_csv(ab)
        st.subheader("Does real rainfall help?")
        ps = [x for x in (_pool(a, 7), _pool(a, 14)) if x]
        k = st.columns(len(ps))
        for col, x in zip(k, ps):
            kpi(col, f"{x['mean_gain']:+.2f} pts", f"{x['h']} day effect of rainfall, 95% CI [{x['lo']:.2f}, {x['hi']:.2f}]")
        st.plotly_chart(gain_chart(a, "Error reduction from adding rainfall"), width="stretch")
    dp = "outputs/real/decision_all_crops.csv"
    if os.path.exists(dp):
        with st.expander("Decision engine backtest"):
            st.dataframe(pd.read_csv(dp).round(2), hide_index=True, width="stretch")
    st.subheader("Method")
    st.markdown("""
- **Model:** quantile gradient boosting predicts the 7 and 14 day price change at the 10th, 50th and 90th percentiles.
- **Uncertainty:** conformalized quantile regression with a rolling 90-day window targets 80% coverage.
- **Baselines:** naive (last price), ridge regression and random forest.
- **Evaluation:** time-ordered 60/20/20 split with a gap, scored only on days with a real quote, 95% block-bootstrap intervals.
- **Limits:** about 2.5 years of onion history, costs and distances are placeholders, results are preliminary.
""")


pg = st.navigation([
    st.Page(page_home, title="Overview", icon="🏠", default=True),
    st.Page(page_live, title="Live price", icon="💹"),
    st.Page(page_board, title="Price board", icon="📊"),
    st.Page(page_explorer, title="Market explorer", icon="🗺️"),
    st.Page(page_pulse, title="Market pulse", icon="\U0001F4C8"),
    st.Page(page_forecast, title="Forecast and decision", icon="🔮"),
    st.Page(page_research, title="Research results", icon="\U0001F9EA"),
    st.Page(page_about, title="About and limits", icon="ℹ️"),
])
st.sidebar.caption("SmartAgri Market Intelligence Platform\nFinal-year major project, IILM University")
pg.run()