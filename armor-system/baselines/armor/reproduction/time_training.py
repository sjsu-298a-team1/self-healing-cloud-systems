"""Tier C sizing: time ARMOR's own `train()` for a few epochs with the official D1 config (only `epochs` is overridden).

    cd <isolated ARMOR copy> && <armor env python> time_training.py [--epochs 2]

The model trained here is discarded (it is a timing probe, not a result). ARMOR's full run is `epochs: 1000` with early stopping
after 50 epochs whose loss improves by less than 1e-3, so a complete training run costs between ~50 and 1000 epochs.
"""
import argparse
import os
import sys
import tempfile
import time

import xgboost  # noqa: F401  same load order as run_armor_cpu.py
import torch
import yaml

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=2)
    a = ap.parse_args()
    sys.path.insert(0, os.getcwd())
    from models.unified_representation.armor_train import train
    from utils.public_functions import load_samples
    with open("config/D1.yaml") as fh:
        cfg = yaml.safe_load(fh)
    samples, _ = load_samples(cfg["path"]["sample_dir"])
    mp = dict(cfg["model_param"], epochs=a.epochs)
    print("torch threads", torch.get_num_threads(), "train samples", len(samples), flush=True)
    t = time.time()
    with tempfile.TemporaryDirectory() as d:
        train(samples, mp, cfg["feat_span"], "D1", save_dir=d)
    s = time.time() - t
    print(f"seconds for {a.epochs} epochs {s:.1f}; per epoch {s / a.epochs:.1f}", flush=True)
