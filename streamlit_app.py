import streamlit as st

st.set_page_config(page_title="Allbridge x TRON", page_icon="🔴", layout="wide")

with open("tron-dashboard.html", "r") as f:
    html = f.read()

st.components.v1.html(html, height=900, scrolling=True)
