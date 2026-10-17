import os, pandas as pd, streamlit as st
import ui, dbinfo

ui.hero("Smart Agri Market Intelligence", "Real mandi prices, forecasts with honest uncertainty, and selling advice for farmers.")

@st.cache_data(ttl=300)
def summ():
    return dbinfo.summary() if dbinfo.available() else None

s = summ()
c = st.columns(5)
if s:
    ui.kpi(c[0], f"{s['rows']:,}", "price quotes collected")
    ui.kpi(c[1], f"{s['commodities']}", "commodities")
    ui.kpi(c[2], f"{s['markets']:,}", "markets")
    ui.kpi(c[3], f"{s['days']}", "days collected")
    ui.kpi(c[4], str(s["last"])[:10], "latest data")
else:
    st.info("No database yet. Run python collect_all.py once to start collecting real prices.")

st.write("")
a, b, d = st.columns(3)
ui.card(a, "1. Real prices, live", "Today's quote from the government mandi feed for any commodity, with stale-data and outlier warnings.")
ui.card(b, "2. Forecast with uncertainty", "Quantile gradient boosting with conformal calibration gives a price range, not just one number.")
ui.card(c[0] if False else d, "3. Where and when to sell", "Each option is scored on net money after transport, storage and spoilage, tuned for risk.")

st.subheader("Evaluation on real history (onion, markets near Aligarh)")
p = "outputs/real/eval_all_markets.csv"
if os.path.exists(p):
    r = pd.read_csv(p)
    k = st.columns(4)
    for col, h in zip(k[:2], (7, 14)):
        x = r[r.h == h]
        ui.kpi(col, f"{int((x.gain_pts > 0).sum())} of {len(x)}", f"markets where the model beats naive ({h} day)")
    for col, h in zip(k[2:], (7, 14)):
        x = r[r.h == h]
        ui.kpi(col, f"{x['cov_rolling_%'].mean():.1f}%", f"mean interval coverage ({h} day, target 80%)")
    piv = r.pivot_table(index="market", columns="h", values="gain_pts").rename(columns=lambda h: f"{h} day")
    st.caption("Error reduction versus the naive forecast, in percentage points (higher is better).")
    st.bar_chart(piv)
    st.caption("Preliminary: gains are mostly not yet statistically significant. More history is being added.")
else:
    st.info("Run python eval_all.py to generate these results.")

with st.expander("Nightly collector status"):
    if os.path.exists("snapshot.log"):
        st.code("".join(open("snapshot.log", errors="ignore").readlines()[-12:]) or "(empty)")
    else:
        st.write("No snapshot.log yet.")
