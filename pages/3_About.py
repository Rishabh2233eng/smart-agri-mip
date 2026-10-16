import streamlit as st
st.set_page_config(page_title="About", layout="wide")
st.title("About this system")
st.markdown("""
**Smart Agri Market Intelligence Platform** helps a farmer decide where and when to sell.

**Data.** Live prices come from the government mandi API (data.gov.in). History comes from public Agmarknet-based archives
and a nightly snapshot collected by this system. Quotes far from the same market's usual range are flagged.

**Forecast.** Quantile gradient boosting predicts the 7 and 14 day price change with an 80% range, calibrated with a rolling conformal method.

**Decision.** Each option (market, days to wait) is scored on net money after transport, storage, spoilage and commission,
and can be tuned for risk.

**Limits (please read).**
- Forecast results so far are preliminary: the gain over a simple baseline is not yet statistically proven.
- Costs and distances are placeholder assumptions.
- Historical pages use data that ends in 2022. Only the main page is live.
- This is decision support, not financial advice.
""")
