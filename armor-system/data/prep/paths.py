import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))   # armor-system/
DATA = os.path.join(ROOT, "data")
TOOLS = os.path.join(DATA, "tools")
if TOOLS not in sys.path:
    sys.path.insert(0, TOOLS)

RAW = os.path.join(DATA, "raw", "armor_zenodo_21744694")
D1_DIR = os.path.join(RAW, "extracted", "D1")
ARMOR_CFG = os.path.join(RAW, "ARMOR", "config", "D1.yaml")
MANIFESTS_298_43 = os.path.join(DATA, "manifests", "armor_d1")
CACHE_DIR = os.path.join(DATA, "processed")                 # Git-ignored
CACHE_FILE = os.path.join(CACHE_DIR, "d1_features_v1.npz")
ART = os.path.join(DATA, "artifacts", "d1")                  # committed, small
SUBDIRS = ("inspection", "splits", "preprocessing", "eda", "quality", "augmentation")


def art(*parts):
    return os.path.join(ART, *parts)


def ensure_dirs():
    for s in SUBDIRS:
        os.makedirs(art(s), exist_ok=True)
    os.makedirs(CACHE_DIR, exist_ok=True)
