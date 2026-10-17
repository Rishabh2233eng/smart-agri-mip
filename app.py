import streamlit as st
import ui

st.set_page_config(page_title="SmartAgri Market Intelligence", page_icon="🌾", layout="wide")
ui.style()
pg = st.navigation([
    st.Page("views/home.py", title="Overview", icon="🏠", default=True),
    st.Page("views/live.py", title="Live price", icon="💹"),
    st.Page("pages/4_Price_Board.py", title="Price board", icon="📊"),
    st.Page("pages/2_Market_Explorer.py", title="Market explorer", icon="🗺️"),
    st.Page("pages/1_Forecast.py", title="Forecast and decision", icon="🔮"),
    st.Page("pages/3_About.py", title="About and limits", icon="ℹ️"),
])
pg.run()
