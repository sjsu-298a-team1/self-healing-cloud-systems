"""Shared look and small components."""
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

PALETTE = {"metric": "#2563eb", "trace": "#f59e0b", "log": "#10b981"}
SPLIT_COLORS = {"train": "#2563eb", "validation": "#f59e0b", "test": "#dc2626"}
CLASS_COLORS = ["#2563eb", "#0ea5e9", "#f59e0b", "#10b981", "#a855f7"]
STATUS_STYLE = {"PASS": ("#065f46", "#d1fae5"), "FAIL": ("#991b1b", "#fee2e2"), "WARN": ("#92400e", "#fef3c7"),
                "PASS_WITH_WARNINGS": ("#92400e", "#fef3c7"), "PENDING": ("#334155", "#e2e8f0"), "INFO": ("#1e40af", "#dbeafe"),
                "BLOCKED": ("#991b1b", "#fee2e2"), "UNKNOWN": ("#334155", "#e2e8f0")}

pio.templates["armor"] = go.layout.Template(layout=go.Layout(
    font=dict(family="Inter, -apple-system, Segoe UI, sans-serif", size=13, color="#0f172a"),
    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#ffffff", margin=dict(l=40, r=20, t=50, b=40),
    colorway=CLASS_COLORS, xaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1"), yaxis=dict(gridcolor="#e2e8f0", zerolinecolor="#cbd5e1"),
    title=dict(font=dict(size=15))))
pio.templates.default = "armor"

CSS = """
<style>
.block-container {padding-top: 1.6rem; padding-bottom: 3rem; max-width: 1280px;}
h1, h2, h3 {letter-spacing: -0.01em;}
.armor-hero {background: linear-gradient(135deg,#1e3a8a 0%,#2563eb 60%,#38bdf8 100%); color:#fff; padding: 1.4rem 1.6rem; border-radius: 14px; margin-bottom: 1.2rem;}
.armor-hero h1 {color:#fff; margin:0 0 .2rem 0; font-size: 1.7rem;}
.armor-hero p {margin:0; opacity:.92;}
.armor-card {background:#fff; border:1px solid #e2e8f0; border-radius:12px; padding: .9rem 1.1rem; box-shadow: 0 1px 2px rgba(15,23,42,.04);}
.armor-card .k {font-size:.78rem; text-transform:uppercase; color:#64748b; letter-spacing:.04em;}
.armor-card .v {font-size:1.7rem; font-weight:700; color:#0f172a; line-height:1.2;}
.armor-card .s {font-size:.8rem; color:#64748b;}
.armor-badge {display:inline-block; padding:.12rem .55rem; border-radius:999px; font-size:.75rem; font-weight:600;}
.armor-note {border-left:4px solid #2563eb; background:#eff6ff; padding:.6rem .9rem; border-radius:6px; font-size:.9rem;}
.armor-warn {border-left:4px solid #f59e0b; background:#fffbeb; padding:.6rem .9rem; border-radius:6px; font-size:.9rem;}
.armor-fail {border-left:4px solid #dc2626; background:#fef2f2; padding:.6rem .9rem; border-radius:6px; font-size:.9rem;}
section[data-testid="stSidebar"] {background:#0f172a;}
section[data-testid="stSidebar"] * {color:#e2e8f0 !important;}
</style>
"""


def inject_css():
    st.markdown(CSS, unsafe_allow_html=True)


def hero(title, subtitle):
    st.markdown(f'<div class="armor-hero"><h1>{title}</h1><p>{subtitle}</p></div>', unsafe_allow_html=True)


def card(col, key, value, sub=""):
    col.markdown(f'<div class="armor-card"><div class="k">{key}</div><div class="v">{value}</div><div class="s">{sub}</div></div>', unsafe_allow_html=True)


def badge(status):
    fg, bg = STATUS_STYLE.get(status, STATUS_STYLE["UNKNOWN"])
    return f'<span class="armor-badge" style="color:{fg};background:{bg}">{status.replace("_", " ")}</span>'


def note(text, kind="note"):
    st.markdown(f'<div class="armor-{kind}">{text}</div>', unsafe_allow_html=True)


def missing(label, hint="run `python armor-system/data/pipeline.py --stage all`"):
    st.warning(f"**Artifact not available:** {label}. Nothing is shown rather than an invented value - {hint}.")


def fmt_int(n):
    return f"{int(n):,}"
