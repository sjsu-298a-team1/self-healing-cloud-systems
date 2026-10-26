"""ARMOR D1 data-preparation dashboard.  Launch:  armor-system/dashboard/run_dashboard.sh"""
import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import ui  # noqa: E402
from views import eda, evidence, explorer, overview, preprocessing, quality, splitting  # noqa: E402

PAGES = {
    "1 - Project Overview": overview,
    "2 - Dataset Explorer": explorer,
    "3 - Data Splitting": splitting,
    "4 - EDA": eda,
    "5 - Preprocessing": preprocessing,
    "6 - Data Quality": quality,
    "7 - Deliverables and Evidence": evidence,
}

st.set_page_config(page_title="ARMOR D1 Data Preparation", page_icon=":bar_chart:", layout="wide", initial_sidebar_state="expanded")
ui.inject_css()
with st.sidebar:
    st.markdown("### ARMOR D1")
    st.caption("DATA 298A - Team 1 - Linear 298-44")
    page = st.radio("Navigate", list(PAGES), label_visibility="collapsed")
    st.markdown("---")
    st.caption("Reads the generated artifacts in armor-system/data/artifacts/d1. Missing artifacts are reported, never invented.")
try:
    PAGES[page].render()
except Exception as exc:  # keep the app usable and show the real error
    st.error(f"This page failed to render: {type(exc).__name__}: {exc}")
    st.exception(exc)
