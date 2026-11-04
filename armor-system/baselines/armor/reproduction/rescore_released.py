"""Tier A: re-score ARMOR's RELEASED D1 predictions (AD intervals, FT types, RCL rankings) with ARMOR's own metric code.

    .venv/bin/python -I armor-system/baselines/armor/reproduction/rescore_released.py [--run-dir DIR] [--out FILE]

This reproduces ARMOR's published numbers from the authors' released outputs. It is NOT an independent reproduction: no ARMOR model
is run. `--run-dir` can point at a run directory produced by ARMOR's own `main.py` (Tier B/C) to score it identically.

Populations (all in the D1 test period, after ARMOR's split_ts 1651852800 = our validation|test boundary):
  AD official : ARMOR's 98 post-split `ad_cases.pkl` labels (ARMOR's population, as published).
  AD cases    : the 84 documented test incidents (`cases.csv` rows 126..209), the population of Model 1's primary detection row.
  FT, RCL     : the 84 test cases (`cases.csv` rows 126..209; ARMOR's split_ratio 0.6 of 210 cases).
Metrics: ARMOR's `eval_AD` / `eval_RCL` from its released `task_metrics.py`; FT weighted P/R/F1 as ARMOR (sklearn average='weighted',
zero_division=0, rounded to 4 d.p.), plus macro-F1 and accuracy (Model 1's primary fault metrics), computed here without sklearn.

Pickles are read with an unpickler that forbids every global; nothing downloaded is executed except ARMOR's metric module.
"""
import argparse
import csv
import hashlib
import importlib.util
import io
import json
import os
import pickle
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ARMOR_SYSTEM = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
RAW = os.path.join(ARMOR_SYSTEM, "data", "raw", "armor_zenodo_21744694")
CODE = os.path.join(RAW, "ARMOR")
D1 = os.path.join(RAW, "extracted", "D1")
RELEASED_RUN = os.path.join(CODE, "res", "D1", "20260113_101332")
SPLIT_FILE = os.path.join(ARMOR_SYSTEM, "data", "artifacts", "d1", "splits", "official_armor_v1.json")
PUBLISHED = {"AD": {"precision": 0.9245, "recall": 1.0, "f1": 0.9608}, "FT": {"precision": 0.9464, "recall": 0.9405, "f1": 0.938},
             "RCL": {"topK": [0.8214, 0.8929, 0.9405, 0.9405, 0.9524], "avgK": 0.9095}}
N_TRAIN_CASES = 126                                      # int(210 * 0.6), ARMOR FT/RCL split_ratio 0.6


class _NoGlobals(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError(f"global {module}.{name} is not allowed")


def sha256(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def load_plain_pickle(path):
    with open(path, "rb") as fh:
        return _NoGlobals(io.BytesIO(fh.read())).load()


def armor_metrics():
    spec = importlib.util.spec_from_file_location("armor_task_metrics", os.path.join(CODE, "models", "diagnosis_tasks", "task_metrics.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def weighted_and_macro(y_true, y_pred):
    """sklearn precision/recall/f1 with average='weighted' and 'macro' (labels = union of y_true and y_pred, zero_division=0)."""
    labels = sorted(set(y_true) | set(y_pred))
    yt, yp = np.asarray(y_true), np.asarray(y_pred)
    p, r, f, s = [], [], [], []
    for c in labels:
        tp = int(((yp == c) & (yt == c)).sum())
        npred, ntrue = int((yp == c).sum()), int((yt == c).sum())
        pc = tp / npred if npred else 0.0
        rc = tp / ntrue if ntrue else 0.0
        p.append(pc), r.append(rc), f.append(2 * pc * rc / (pc + rc) if pc + rc else 0.0), s.append(ntrue)
    w = np.asarray(s, float) / sum(s)
    return {"weighted": {"precision": float(np.round(np.dot(w, p), 4)), "recall": float(np.round(np.dot(w, r), 4)), "f1": float(np.round(np.dot(w, f), 4))},
            "macro_f1": float(np.mean(f)),
            "accuracy": float((yt == yp).mean()), "per_class_f1": {int(c): float(fc) for c, fc in zip(labels, f)}, "support": {int(c): int(sc) for c, sc in zip(labels, s)}}


def score(run_dir):
    tm = armor_metrics()
    scen = os.path.join(run_dir, "scenarios", "full")
    files = {"pre_interval": os.path.join(scen, "tmp", "pre_interval.json"), "pre_types": os.path.join(scen, "tmp", "pre_types.json"),
             "rank_df": os.path.join(scen, "tmp", "rank_df.csv"), "res_json": os.path.join(scen, "res.json")}
    with open(SPLIT_FILE) as fh:
        split_ts = int(json.load(fh)["ad_split"]["timestamp"])
    with open(os.path.join(D1, "cases", "cases.csv"), newline="") as fh:
        cases = list(csv.DictReader(fh))
    test_cases = cases[N_TRAIN_CASES:]
    type_hash = load_plain_pickle(os.path.join(D1, "hash_info", "type_hash.pkl"))
    type_dict = load_plain_pickle(os.path.join(D1, "hash_info", "type_dict.pkl"))
    ad_labels = [int(x) for x in load_plain_pickle(os.path.join(D1, "cases", "ad_cases.pkl")) if int(x) > split_ts]
    case_labels = [int(c["timestamp"]) for c in test_cases]
    assert min(case_labels) > split_ts

    with open(files["pre_interval"]) as fh:
        intervals = [tuple(int(v) for v in pair) for pair in json.load(fh)]
    out = {"run_dir": os.path.relpath(run_dir, ARMOR_SYSTEM), "split_ts": split_ts, "inputs_sha256": {k: sha256(v) for k, v in files.items() if os.path.exists(v)},
           "armor_task_metrics_py_sha256": sha256(os.path.join(CODE, "models", "diagnosis_tasks", "task_metrics.py"))}
    p, r, f = tm.eval_AD(intervals, ad_labels, 300)
    out["AD_official_98"] = {"precision": float(p), "recall": float(r), "f1": float(f), "n_labels": len(set(ad_labels)), "n_intervals": len(intervals)}
    sys.path.insert(0, os.path.join(ARMOR_SYSTEM, "evaluation", "detection"))
    from armor_scoring import eval_AD_detail
    out["AD_official_98"]["counts"] = {k: int(v) for k, v in eval_AD_detail(intervals, ad_labels, 300).items() if k in ("TP", "FP", "FN")}
    d = eval_AD_detail(intervals, case_labels, 300)
    out["AD_cases_84"] = {k: (float(v) if isinstance(v, (float, np.floating)) else int(v)) for k, v in d.items()}
    from interval_diagnostics import in_intervals                   # Model 1's coverage definition, on ARMOR's evaluation minutes
    cache = os.path.join(ARMOR_SYSTEM, "data", "processed", "d1_features_v1.npz")
    if os.path.exists(cache):
        with np.load(cache, allow_pickle=False) as z:
            minutes = z["timestamps"][z["timestamps"] > split_ts]
        out["AD_alert_coverage"] = {"minutes": int(minutes.size), "coverage_raw": float(in_intervals(minutes, intervals).mean()),
                                    "coverage_padded_300s": float(in_intervals(minutes, intervals, 300).mean()),
                                    "note": "share of the post-split sample minutes inside an interval (raw, and padded by 300 s)"}

    with open(files["pre_types"]) as fh:
        pre_types = [int(x) for x in json.load(fh)]
    y_true = [int(type_hash[c["failure_type"]]) for c in test_cases]
    assert len(pre_types) == len(y_true) == 84
    ft = weighted_and_macro(y_true, pre_types)
    ft["class_names"] = {int(k): v for k, v in type_dict.items()}
    out["FT_cases_84"] = ft

    import pandas as pd                                   # only for ARMOR's own eval_RCL, which iterates a DataFrame
    rank_df = pd.read_csv(files["rank_df"])
    assert list(rank_df["timestamp"]) == case_labels and list(rank_df["cmdb_id"]) == [c["cmdb_id"] for c in test_cases]
    topk, avgk = tm.eval_RCL(rank_df, k=5)
    out["RCL_cases_84"] = {"topK": [float(x) for x in topk], "avgK": float(avgk)}

    if os.path.exists(files["res_json"]):
        with open(files["res_json"]) as fh:
            out["run_res_json"] = json.load(fh)
    out["matches_published"] = {
        "AD": {k: out["AD_official_98"][k] == PUBLISHED["AD"][k] for k in ("precision", "recall", "f1")},
        "FT": {k: out["FT_cases_84"]["weighted"][k] == PUBLISHED["FT"][k] for k in ("precision", "recall", "f1")},
        "RCL": {"topK": out["RCL_cases_84"]["topK"] == PUBLISHED["RCL"]["topK"], "avgK": out["RCL_cases_84"]["avgK"] == PUBLISHED["RCL"]["avgK"]}}
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-dir", default=RELEASED_RUN)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    res = score(os.path.abspath(a.run_dir))
    text = json.dumps(res, indent=1, sort_keys=True)
    print(text)
    if a.out:
        with open(a.out, "w") as fh:
            fh.write(text + "\n")


if __name__ == "__main__":
    main()
