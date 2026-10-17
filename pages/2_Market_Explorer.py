import streamlit as st, pandas as pd, numpy as np
from src import casestudy
import src.config as C

st.title("Market explorer (real history)")
st.caption("Real daily mandi prices from public archives. Gaps up to 7 days are interpolated. Data ends where shown.")

@st.cache_resource(show_spinner="Loading real history...")
def load():
    S, crops, missing = casestudy.setup()
    return S, crops

S, crops = load()
if not crops:
    st.error("No crop data found in data/real."); st.stop()
crop = st.selectbox("Crop", crops)
mk = sorted(m for (c, m) in S if c == crop)
sel = st.multiselect("Markets", mk, default=mk[:4])
if not sel:
    st.info("Pick at least one market."); st.stop()
wide = pd.concat({m: pd.Series(S[(crop, m)]["modal_price"].to_numpy(), index=S[(crop, m)].index) for m in sel}, axis=1)
lo, hi = wide.index.min().date(), wide.index.max().date()
rng = st.slider("Date range", lo, hi, (lo, hi))
wide = wide.loc[str(rng[0]):str(rng[1])]

st.subheader("Price per quintal (Rs)")
st.line_chart(wide)
cols = st.columns(len(sel))
for col, m in zip(cols, sel):
    s = wide[m].dropna()
    if len(s) > 31:
        col.metric(m, f"Rs {s.iloc[-1]:.0f}", f"{(s.iloc[-1] / s.iloc[-31] - 1) * 100:+.1f}% vs 30 days")

st.subheader("Seasonality: average price by month (1.0 = overall average)")
m0 = st.selectbox("Market", sel)
s = S[(crop, m0)]["modal_price"]
st.bar_chart((s.groupby(s.index.month).mean() / s.mean()).rename("price index"))

home = S.get((crop, C.HOME))
if home is not None:
    st.subheader(f"Price gap versus {C.HOME} (positive = higher than home)")
    gap = wide.sub(pd.Series(home["modal_price"].to_numpy(), index=home.index).reindex(wide.index), axis=0)
    gap = gap.drop(columns=[C.HOME], errors="ignore")
    if gap.shape[1]:
        st.line_chart(gap)

