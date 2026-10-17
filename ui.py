import streamlit as st

CSS = """
<style>
.block-container {padding-top: 2rem; max-width: 1200px;}
.hero {background: linear-gradient(135deg,#14231F 0%,#2F7D5B 100%); color:#F6F4EC; padding:30px 34px; border-radius:18px; margin-bottom:22px;}
.hero h1 {color:#F6F4EC; font-size:2.1rem; margin:0 0 6px 0; padding:0;}
.hero p {color:#D6E3DC; font-size:1.05rem; margin:0;}
.card {background:#fff; border:1px solid #E1DED0; border-radius:16px; padding:20px 22px; height:100%;}
.card h4 {margin:0 0 8px 0; color:#2F7D5B;}
.card p {margin:0; color:#33433D;}
.price {font-size:3.2rem; font-weight:700; color:#14231F; line-height:1.1;}
.badge {display:inline-block; padding:3px 12px; border-radius:999px; font-size:.85rem; font-weight:600; margin-left:8px;}
.live {background:#DFF2E8; color:#1B6B45;} .stale {background:#FBE9C6; color:#7A5200;} .warn {background:#F8D9D4; color:#8A2B1E;}
.kpi {background:#fff; border:1px solid #E1DED0; border-radius:14px; padding:14px 18px;}
.kpi .v {font-size:1.7rem; font-weight:700; color:#14231F;} .kpi .l {color:#5B6B65; font-size:.85rem;}
</style>
"""
def style():
    st.markdown(CSS, unsafe_allow_html=True)
def hero(title, sub):
    st.markdown(f'<div class="hero"><h1>{title}</h1><p>{sub}</p></div>', unsafe_allow_html=True)
def kpi(col, value, label):
    col.markdown(f'<div class="kpi"><div class="v">{value}</div><div class="l">{label}</div></div>', unsafe_allow_html=True)
def card(col, title, body):
    col.markdown(f'<div class="card"><h4>{title}</h4><p>{body}</p></div>', unsafe_allow_html=True)
