"""STEP 7: data-augmentation assessment for D1 numeric features, backed by calculations.

Decision recorded here: augmentation is NOT adopted in this phase and no augmentation utility is shipped.
Nothing synthetic is added to the official benchmark; the numbers below are what the recommendation rests on.
"""
import csv
import os
import re

import numpy as np

from . import paths
from .common import read_json, write_json

SIGMAS = (0.01, 0.05, 0.1)


def _armor_aug_config():
    """Augmentation-related settings ARMOR itself already ships (read from its config text, not executed)."""
    text = open(paths.ARMOR_CFG).read()
    out = {}
    for key in ("noise_rate", "missing_loss_scale", "missing_prob", "aug_multiple", "node_mask_rate"):
        m = re.search(rf"^\s*{key}:\s*([0-9.]+)", text, re.M)
        out[key] = float(m.group(1)) if m else None
    return out


def run(labels, ts, X, is_test, splits_result, scalers):
    sc = scalers["official_train_period"]
    train = ts <= splits_result["ad_split"]
    live = ~sc["absent_entry"]
    # 1. size of a jitter relative to the spread of live, non-constant series
    scale = sc["scale"][live & ~sc["constant"]]
    med_std = float(np.median(scale))
    # 2. temporal dependence (lag-1 autocorrelation of node-mean series per channel, within contiguous train runs)
    S = (X[train] * live[None]).sum(axis=1) / np.maximum(live.sum(axis=0), 1)
    tt = ts[train]
    ok = np.diff(tt) == 60
    a, b = S[:-1][ok], S[1:][ok]
    sd = a.std(axis=0) * b.std(axis=0)
    r = ((a - a.mean(axis=0)) * (b - b.mean(axis=0))).mean(axis=0)[sd > 1e-12] / sd[sd > 1e-12]
    # 3. incident effect size (root-node |x| ratio rises) from the EDA table
    rows = list(csv.DictReader(open(os.path.join(paths.art("eda"), "incident_aligned.csv"))))
    metric = [x for x in rows if x["modality"] == "metric" and x["partition"] == "train_cases"]
    pre = np.mean([float(x["root_mean_abs"]) for x in metric if int(x["offset_min"]) < 0])
    post = np.mean([float(x["root_mean_abs"]) for x in metric if 0 <= int(x["offset_min"]) <= 4])
    zero_frac = float((X[train] == 0).mean())
    man = splits_result["official"]
    cls = man["case_ranges"]["train"]["class_counts"]
    calc = {
        "median_series_std_live_nonconstant_train": med_std,
        "jitter_sigmas_considered": list(SIGMAS),
        "jitter_relative_to_median_std": {str(s): s / med_std for s in SIGMAS},
        "zero_fraction_train_all_entries": zero_frac,
        "structural_zero_entries": int(sc["absent_entry"].sum()),
        "constant_entries_train": int(sc["constant"].sum()),
        "lag1_autocorrelation_median": float(np.median(r)), "lag1_autocorrelation_p10": float(np.percentile(r, 10)),
        "channels_in_lag1_estimate": int(r.size),
        "metric_root_node_mean_abs_before": float(pre), "metric_root_node_mean_abs_after": float(post),
        "train_case_class_counts_official": cls,
        "min_train_class_cases": int(min(cls.values())),
        "armor_existing_augmentation_config": _armor_aug_config(),
    }
    methods = [
        {"method": "Gaussian jitter on live, non-constant entries", "advantage": "cheap; mild regulariser for the 130-d numeric vectors",
         "risk": f"{zero_frac:.0%} of entries are exact zeros that carry meaning (series mean / absent block); adding noise to them invents signal. "
                 "Incident deviations are brief spikes, so noise comparable to them can erase or fake a fault signature.", "verdict": "possible later, train-only, never on zero/absent entries"},
        {"method": "Time warping / window slicing", "advantage": "more window variety",
         "risk": f"features are one-minute aggregates with lag-1 autocorrelation median {np.median(r):.2f}; warping changes the onset timing that defines the injection response, and "
                 "windows crossing a split boundary would leak.", "verdict": "not recommended"},
        {"method": "Mixup / interpolation between samples", "advantage": "smooths decision regions",
         "risk": "blends different fault classes or an incident with normal minutes into states that never occurred; labels become ill-defined (no incident durations exist).", "verdict": "not recommended"},
        {"method": "Synthetic incident generation (SMOTE-like, generative)", "advantage": "addresses the minority class",
         "risk": f"the rarest class has {min(cls.values())} training cases; synthetic incidents would be fabricated ground truth and are prohibited in the benchmark.", "verdict": "rejected"},
        {"method": "Modality masking / dropout", "advantage": "matches the missing-modality robustness goal and uses the real data unchanged",
         "risk": "must keep structural absence separate from simulated absence (indicators); ARMOR already applies it in its own pretraining.", "verdict": "already part of ARMOR; evaluate in Model 1 only with indicators"},
        {"method": "Normal-period oversampling for pretraining", "advantage": "none needed: 3,714 normal samples exist",
         "risk": "temporal leakage if it draws on samples after the training boundary.", "verdict": "not needed"},
    ]
    result = {"recommendation": "Do not adopt augmentation now. Keep the official benchmark and the data-preparation pipeline free of synthetic data. "
                                "Revisit only as a labelled, train-only sensitivity experiment after a Model 1 baseline exists, limited to masking and jitter on live non-constant entries.",
              "decision": "not_adopted", "utility_implemented": False, "calculations": calc, "methods": methods,
              "leakage_rules_if_revisited": ["fit and draw only from the training period of an approved split", "never augment validation or test",
                                              "windows must not cross a split boundary", "keep structural-absence indicators fixed"]}
    write_json(os.path.join(paths.art("augmentation"), "augmentation_assessment.json"), result)
    write_markdown(result, os.path.join(paths.ROOT, "docs", "d1_augmentation_assessment.md"))
    return result


def write_markdown(result, path):
    c = result["calculations"]
    lines = ["# D1 data augmentation assessment", "",
             "Generated by `armor-system/data/pipeline.py` from `armor-system/data/artifacts/d1/augmentation/augmentation_assessment.json`; do not edit by hand.", "",
             f"**Decision: {result['decision'].replace('_', ' ')}.** {result['recommendation']}", "", "## Calculations behind the decision", "",
             f"- Median per node-channel spread (std) of live, non-constant series in the training period: {c['median_series_std_live_nonconstant_train']:.3f}; "
             f"jitter sigmas considered {c['jitter_sigmas_considered']} are {', '.join(f'{v:.0%}' for v in c['jitter_relative_to_median_std'].values())} of that spread.",
             f"- {c['zero_fraction_train_all_entries']:.1%} of training entries are exactly zero; {c['structural_zero_entries']} entries belong to structurally absent blocks and {c['constant_entries_train']:,} entries are constant, so jitter would invent signal there.",
             f"- Lag-1 autocorrelation of system-level series: median {c['lag1_autocorrelation_median']:.2f}, 10th percentile {c['lag1_autocorrelation_p10']:.2f} over {c['channels_in_lag1_estimate']} non-constant channels (temporal structure matters).",
             f"- Metric root-node mean |value|: {c['metric_root_node_mean_abs_before']:.3f} before injection vs {c['metric_root_node_mean_abs_after']:.3f} in the 5 minutes after (training cases): the fault signature is a short, large change.",
             f"- Smallest official training class has {c['min_train_class_cases']} cases ({c['train_case_class_counts_official']}); window-level augmentation cannot create new incidents, and synthetic incidents would be fabricated ground truth.",
             f"- ARMOR already ships its own augmentation settings in `config/D1.yaml`: {c['armor_existing_augmentation_config']}.", "",
             "## Candidate methods", "", "| Method | Advantage | Risk | Verdict |", "|---|---|---|---|"]
    for m in result["methods"]:
        lines.append(f"| {m['method']} | {m['advantage']} | {m['risk']} | {m['verdict']} |")
    lines += ["", "## If revisited later", ""] + [f"- {r}" for r in result["leakage_rules_if_revisited"]]
    lines += ["", "No augmentation utility is implemented, nothing synthetic is added to the official benchmark, and the data-preparation pipeline does not alter any official ARMOR sample.", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
