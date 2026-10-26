"""Static PNG renderings of the EDA tables (the dashboard draws interactive versions from the same files)."""
import csv
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from . import paths
from .common import read_json

COL = {"metric": "#2563eb", "trace": "#f59e0b", "log": "#10b981"}
SPLIT_COL = {"train": "#2563eb", "validation": "#f59e0b", "test": "#dc2626"}


def _csv(p):
    with open(p, newline="") as fh:
        return list(csv.DictReader(fh))


def run(splits_result):
    e = paths.art("eda")
    f = os.path.join(e, "figures")
    os.makedirs(f, exist_ok=True)
    made = []

    def save(fig, name):
        fig.tight_layout()
        fig.savefig(os.path.join(f, name), dpi=110)
        plt.close(fig)
        made.append(name)

    fd = [r for r in _csv(os.path.join(e, "fault_distribution.csv")) if r["level"] == "category"]
    fig, ax = plt.subplots(figsize=(7, 3.6))
    ax.barh([r["name"] for r in fd][::-1], [int(r["count"]) for r in fd][::-1], color="#2563eb")
    for i, r in enumerate(fd[::-1]):
        ax.text(int(r["count"]) + 1, i, r["count"], va="center", fontsize=9)
    ax.set_title("Fault category distribution (210 cases)")
    ax.set_xlabel("cases")
    save(fig, "01_fault_distribution.png")

    sc = _csv(os.path.join(e, "split_class_distributions.csv"))
    mans = list(dict.fromkeys(r["manifest"] for r in sc))
    classes = list(dict.fromkeys(r["class"] for r in sc))
    fig, axes = plt.subplots(1, len(mans), figsize=(4.2 * len(mans), 3.8), sharey=True)
    for ax, m in zip(np.atleast_1d(axes), mans):
        rows = [r for r in sc if r["manifest"] == m]
        splits = list(dict.fromkeys(r["split"] for r in rows))
        bottom = np.zeros(len(classes))
        for s in splits:
            v = np.array([next(int(r["cases"]) for r in rows if r["split"] == s and r["class"] == c) for c in classes])
            ax.bar(range(len(classes)), v, bottom=bottom, label=s, color=SPLIT_COL[s])
            bottom += v
        ax.set_xticks(range(len(classes)))
        ax.set_xticklabels([c.replace("Container ", "C. ") for c in classes], rotation=30, ha="right", fontsize=8)
        ax.set_title(m, fontsize=8)
        ax.legend(fontsize=7)
    save(fig, "02_split_class_distributions.png")

    h = read_json(os.path.join(e, "feature_histograms_train.json"))
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    for ax, m in zip(axes, h):
        ed = np.array(h[m]["bin_edges"])
        ax.bar((ed[:-1] + ed[1:]) / 2, h[m]["counts"], width=ed[1] - ed[0], color=COL[m])
        ax.set_yscale("log")
        z = h[m]["zero_count"] / (h[m]["zero_count"] + h[m]["nonzero_count"])
        ax.set_title(f"{m}: non-zero values (train); zeros {z:.0%}", fontsize=9)
    save(fig, "03_feature_distributions.png")

    mr = _csv(os.path.join(e, "missingness_node_modality_train.csv"))
    nodes = list(dict.fromkeys(r["node"] for r in mr))
    M = np.array([[float(next(r["zero_fraction_train"] for r in mr if r["node"] == n and r["modality"] == m)) for m in ("metric", "trace", "log")] for n in nodes])
    fig, ax = plt.subplots(figsize=(4.2, 9))
    im = ax.imshow(M, aspect="auto", cmap="viridis", vmin=0, vmax=1)
    ax.set_xticks(range(3))
    ax.set_xticklabels(["metric", "trace", "log"])
    ax.set_yticks(range(len(nodes)))
    ax.set_yticklabels(nodes, fontsize=6)
    ax.set_title("Zero fraction per node and modality (train)", fontsize=9)
    fig.colorbar(im, ax=ax, shrink=0.5)
    save(fig, "04_zero_fraction_node_modality.png")

    cr = _csv(os.path.join(e, "correlation_channels_train.csv"))
    names = [r["channel"] for r in cr]
    C = np.array([[np.nan if r[n] in ("", None) else float(r[n]) for n in names] for r in cr])
    fig, ax = plt.subplots(figsize=(7, 6))
    im = ax.imshow(C, cmap="coolwarm", vmin=-1, vmax=1)
    ax.set_title("System-level channel correlation (train); grey = constant channel")
    fig.colorbar(im, ax=ax, shrink=0.7)
    save(fig, "05_correlation_heatmap.png")

    tt = _csv(os.path.join(e, "temporal_trends_full_10min.csv"))
    x = np.arange(len(tt))
    fig, ax = plt.subplots(figsize=(11, 3.4))
    for m in ("metric", "trace", "log"):
        ax.plot(x, [float(r[f"{m}_mean_abs"]) for r in tt], label=m, color=COL[m], lw=0.9)
    ax.set_title("System-level mean |value| per modality (10-minute means, full timeline, descriptive)")
    ax.set_xlabel("10-minute bin (collection days concatenated)")
    ax.legend()
    save(fig, "06_temporal_trends.png")

    ia = _csv(os.path.join(e, "incident_aligned.csv"))
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6), sharex=True)
    for ax, m in zip(axes, ("metric", "trace", "log")):
        for cat in sorted({r["category"] for r in ia}):
            rows = sorted([r for r in ia if r["category"] == cat and r["modality"] == m and r["partition"] == "train_cases"], key=lambda r: int(r["offset_min"]))
            ax.plot([int(r["offset_min"]) for r in rows], [float(r["root_mean_abs"]) / max(float(r["other_mean_abs"]), 1e-9) for r in rows], label=cat, lw=1.2)
        ax.axvline(0, color="k", ls="--", lw=0.8)
        ax.set_title(f"{m}: root-node / other-node mean |value| (train cases)", fontsize=8)
        ax.set_xlabel("minutes from injection")
    axes[0].legend(fontsize=6)
    save(fig, "07_incident_aligned.png")

    vr = _csv(os.path.join(e, "variability_outliers_train.csv"))
    top = sorted([r for r in vr if r["constant"] == "False"], key=lambda r: -float(r["fraction_abs_gt_3"]))[:20]
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.barh([r["name"] for r in top][::-1], [float(r["fraction_abs_gt_3"]) for r in top][::-1], color=[COL[r["modality"]] for r in top][::-1])
    ax.set_title("Channels with the most values beyond |3| (train)")
    save(fig, "08_outliers.png")

    ks = sorted(_csv(os.path.join(e, "train_vs_validation_model1.csv")), key=lambda r: int(r["index"]))
    fig, ax = plt.subplots(figsize=(11, 3.2))
    ax.bar([int(r["index"]) for r in ks], [float(r["ks"]) for r in ks], color=[COL[r["modality"]] for r in ks])
    ax.axhline(0.2, color="r", ls="--", lw=0.8)
    ax.set_title("Train vs validation KS statistic per channel (approved Model 1 split; diagnostic only)")
    ax.set_xlabel("channel index")
    save(fig, "09_train_vs_validation_ks.png")

    rows = _csv(os.path.join(paths.art("splits"), "case_split_assignments.csv"))
    fig, axes = plt.subplots(3, 1, figsize=(11, 4.2), sharex=True)
    for ax, key, title in zip(axes, ("official_split", "rejected_100_26_84_split", "model1_split"), ("official ARMOR 126/84", "rejected 100/26/84 (fails checks)", "approved Model 1 101/25/84")):
        for sp_ in ("train", "validation", "test"):
            xs = [int(r["timestamp"]) for r in rows if r[key] == sp_]
            ax.scatter(xs, [0] * len(xs), s=10, color=SPLIT_COL[sp_], label=sp_)
        ax.set_yticks([])
        ax.set_ylabel(title, rotation=0, ha="right", va="center", fontsize=7)
    axes[0].legend(ncol=3, fontsize=7)
    axes[-1].set_xlabel("injection timestamp (epoch s)")
    save(fig, "10_split_timeline.png")
    return made
