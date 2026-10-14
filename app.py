import pandas as pd
import streamlit as st
from src.live import lookup
from src import db

st.set_page_config(page_title="SmartAgri Market Intelligence", layout="wide")
st.title("SmartAgri Market Intelligence Platform")
st.caption("Live mandi prices from the government daily feed (data.gov.in / Agmarknet), with data-quality checks.")

c1, c2, c3 = st.columns(3)
crop = c1.text_input("Crop", "Onion")
market = c2.text_input("Market or district", "Azadpur")
state = c3.text_input("State (optional)", "")

if st.button("Get price", type="primary"):
    with st.spinner("Fetching today's prices..."):
        r = lookup(crop, market, state.strip() or None)
    h = r["hit"]
    if h:
        tag = "LIVE" if h["is_live"] else "NOT LIVE - " + str(h["age_days"]) + " days old"
        st.metric(f"{crop} at {h['market']} ({h['state']})", f"Rs {h['price']:.0f} per quintal")
        st.caption(f"[{tag}] price date {h['date']} | source: {h['source']} | "
                   f"simple average of {h['n_varieties']} variety/grade quote(s)")
        if h["suspect"]:
            st.warning(f"This quote is far from the median Rs {h['ref']:.0f} across markets today. "
                       "It may be a unit or entry error in the source data.")
        if r["others"]:
            st.subheader("Other markets in the same state today")
            df = pd.DataFrame(r["others"], columns=["Market", "Price (Rs/qtl)"]).set_index("Market")
            st.bar_chart(df)
            st.caption("Prices before transport and commission costs. "
                       + (f"{r['excluded']} market(s) left out because their quotes look like errors."
                          if r["excluded"] else ""))
    else:
        st.error(("The live API could not be reached right now: " + r["error"]) if not r["api_ok"]
                 else f"No {crop} price for '{market}' in today's feed.")
        if r["stored"]:
            s_ = r["stored"]
            st.info(f"Last stored price: Rs {s_['price']:.0f} at {s_['market']} on {s_['date']} "
                    f"({s_['age_days']} days old, NOT LIVE)")
        if r["state_markets"]:
            st.write(f"{crop} markets reporting today in {state}:")
            st.dataframe(pd.DataFrame(r["state_markets"], columns=["Market", "Price (Rs/qtl)"]))
        elif r["states"]:
            st.write(f"{crop} is reported today in these states (markets):")
            st.dataframe(pd.DataFrame(list(r["states"].items()), columns=["State", "Markets"]))
            st.caption("Type one of these states in the State box and search again.")

st.divider()
st.subheader("Stored price history")
con = db.connect()
like = f"%{market.lower().strip()}%"
hist = pd.read_sql_query(
    "SELECT date, AVG(modal_price) AS price FROM prices "
    "WHERE lower(commodity)=? AND (lower(market) LIKE ? OR lower(district) LIKE ?) "
    "GROUP BY date ORDER BY date", con, params=(crop.lower(), like, like))
con.close()
if len(hist) >= 2:
    st.line_chart(hist.set_index("date"))
else:
    st.info(f"Only {len(hist)} day(s) stored so far for this crop and market. The daily collector builds "
            "this history.")

st.subheader("Forecast")
st.info("Not available yet. Forecasting needs a continuous recent price window (about 30 days) and real "
        "history for training. This panel will show calibrated 7 and 14 day forecasts once that data is loaded.")

