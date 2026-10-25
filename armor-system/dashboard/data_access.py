"""Cached, failure-tolerant access to the artifacts produced by data/pipeline.py.

Every loader returns None when an artifact is missing; pages then show an explicit message through
`ui.missing`, never a made-up number.
"""
import json
import os
import sys

import pandas as pd
import streamlit as st

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))
DATA = os.path.join(ROOT, "data")
if DATA not in sys.path:
    sys.path.insert(0, DATA)
from prep import paths  # noqa: E402

ART = paths.ART
M298_43 = paths.MANIFESTS_298_43
REPO = os.path.abspath(os.path.join(ROOT, ".."))


def art_path(*parts):
    return os.path.join(ART, *parts)


def rel(path):
    return os.path.relpath(path, REPO)


@st.cache_data(show_spinner=False)
def _json(path, mtime):
    with open(path) as fh:
        return json.load(fh)


@st.cache_data(show_spinner=False)
def _csv(path, mtime):
    return pd.read_csv(path)


@st.cache_data(show_spinner=False)
def _npz(path, mtime):
    import numpy as np
    z = np.load(path)
    return {k: z[k] for k in z.files}


def jload(*parts, base=None):
    p = os.path.join(base or ART, *parts)
    return _json(p, os.path.getmtime(p)) if os.path.exists(p) else None


def cload(*parts, base=None):
    p = os.path.join(base or ART, *parts)
    return _csv(p, os.path.getmtime(p)) if os.path.exists(p) else None


def nload(*parts):
    p = os.path.join(ART, *parts)
    return _npz(p, os.path.getmtime(p)) if os.path.exists(p) else None


def fig_path(name):
    p = art_path("eda", "figures", name)
    return p if os.path.exists(p) else None


@st.cache_resource(show_spinner="Loading the 7,200 x 46 x 130 feature cache (once)...")
def feature_cache():
    """Large array cache; only loaded when a page asks for live samples. Returns None if not built."""
    if not os.path.exists(paths.CACHE_FILE):
        return None
    from prep import loader
    ts, X, is_test = loader.load_arrays()
    return {"ts": ts, "X": X, "is_test": is_test}


def schema():
    return jload("inspection", "schema.json")


def split_manifests():
    out = {}
    for name in ("official_armor_v1", "model1_candidate_100_26_84_v1", "model1_alternative_v1"):
        m = jload("splits", f"{name}.json")
        if m:
            out[name] = m
    return out
