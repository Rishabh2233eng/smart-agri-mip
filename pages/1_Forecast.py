import streamlit as st, pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from src import casestudy
import src.config as C

st.title("Forecast and selling decision")
st.warning("Historical case study. Built on real daily mandi prices up to the last date shown below, "
           "NOT today's prices. For today's live price use the main page. Costs and distances are placeholder assumptions.")

@st.cache_resource(show_spinner="Training models on real history. The first load takes a few minutes...")
def load():
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

data = load()
if not data:
    st.error("No crop has enough real history yet. Check data/real and src/config.py (ASSUMP).")
    st.stop()
from src.forecast import metrics
from src.decision import recommend

c1, c2, c3 = st.columns(3)
crop = c1.selectbox("Crop", list(data))
qty = c2.number_input("Quantity (quintals)", 1, 5000, 50)
lam = c3.slider("Risk aversion (0 = chase profit, 1 = play safe)", 0.0, 1.0, 0.5, 0.05)

mk, fc, last_date = data[crop]
st.caption(f"Home market: {C.HOME}. Data as of {last_date}. Markets considered: {', '.join(mk)}.")
price_now = {m: fc[(m, 7)]["last"][0] for m in mk}
latest = {k: v["last"][1:] for k, v in fc.items()}
rec = recommend(crop, qty, mk, price_now, latest, lam=lam).head(5)
best = rec.iloc[0]
st.success(f"Best option: sell at {best['market']} after {int(best['sell_after_days'])} days. "
           f"Expected net Rs {best['exp_net_per_qtl']:.0f} per quintal "
           f"(worst case Rs {best['worst_net_per_qtl']:.0f}).")
st.subheader("Top options")
st.dataframe(rec, use_container_width=True)

st.subheader(f"7-day forecast at {C.HOME} with 80% interval (past predictions vs what happened)")
o = fc[(C.HOME, 7)]["out"].tail(200)
x = o.index + pd.Timedelta(days=7)
fig, ax = plt.subplots(figsize=(10, 3.5))
ax.plot(x, o["actual"], color="black", lw=1, label="Actual")
ax.plot(x, o["p_med"], color="tab:blue", lw=1, label="Forecast")
ax.fill_between(x, o["p_lo"], o["p_hi"], alpha=0.25, label="80% interval")
ax.set_ylabel("Rs per quintal"); ax.legend(loc="upper left", fontsize=8)
st.pyplot(fig)
st.subheader("How accurate has this been?")
rows = [{"horizon_days": h, **metrics(fc[(C.HOME, h)]["out"])} for h in (7, 14)]
st.dataframe(pd.DataFrame(rows).round(2), use_container_width=True)
