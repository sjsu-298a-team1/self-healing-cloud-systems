"""STEP 6: reproducible EDA. Full-dataset descriptive analysis is kept separate from training-only analysis.

Partitions
  full         all 7,200 samples (descriptive only; never used for a modelling decision)
  train        the approved Model 1 train period (before the 101|25 boundary): the only partition behind model-development statistics
  validation   the approved Model 1 validation period: used only for the diagnostic train-vs-validation comparison; nothing is tuned on it
  test         never read for any statistic except the clearly labelled full-dataset descriptive views
"""
import os
from collections import Counter

import numpy as np
from scipy import stats

from . import paths, preprocess as pp
from .common import iso, nearest_index, read_json, root_nodes, write_csv, write_json
from .loader import MODALITIES, category_of
from .preprocess_stage import periods

OFFSETS = list(range(-9, 5))   # minutes relative to the injection time
KS_FLAG = 0.20


def _live(scaler):
    return ~scaler["absent_entry"]          # (46,130) entries that are not structurally absent


def run(labels, ts, X, is_test, splits_result, scalers):
    out = paths.art("eda")
    groups, nodes, channels, cases = labels["groups"], labels["nodes"], labels["channels"], labels["cases"]
    cats = [category_of(c, labels) for c in cases]
    sc = scalers["model1_train_period"]
    live = _live(sc)
    ad_split = splits_result["ad_split"]
    final = splits_result["final"]
    per = periods(final)
    train = (ts >= per["train"][0]) & (ts < per["train"][1])
    a_tr = (ts >= per["train"][0]) & (ts < per["train"][1])
    a_va = (ts >= per["validation"][0]) & (ts < per["validation"][1])
    owner = {i: m for m, idx in groups.items() for i in idx}
    findings = []

    def add(fid, text, evidence):
        findings.append({"id": fid, "finding": text, "evidence": evidence})

    # 1 overview + descriptive stats per modality (full, descriptive)
    rows = []
    for m in MODALITIES:
        sub = X[:, :, groups[m]]
        lv = live[:, groups[m]]
        v = sub[:, lv]
        rows.append({"modality": m, "channels": len(groups[m]), "values_live_entries": int(v.size), "mean": float(v.mean()), "std": float(v.std()),
                     "min": float(v.min()), "max": float(v.max()), "zero_fraction_live": float((v == 0).mean()),
                     "zero_fraction_all_entries": float((sub == 0).mean())})
    write_csv(os.path.join(out, "descriptive_stats_by_modality_full.csv"), rows)
    mod_rows = {r["modality"]: r for r in rows}

    # 2/3 fault and split class distributions
    cc = Counter(cats)
    fine = Counter(c["failure_type"] for c in cases)
    write_csv(os.path.join(out, "fault_distribution.csv"),
              [{"level": "category", "name": k, "count": v, "share": v / len(cases)} for k, v in sorted(cc.items(), key=lambda kv: -kv[1])] +
              [{"level": "fine_type", "name": k, "count": v, "share": v / len(cases)} for k, v in sorted(fine.items(), key=lambda kv: -kv[1])])
    srows = []
    for key in ("official", "candidate", "final"):
        man = splits_result[key]
        if not man:
            continue
        for sp_, r in man["case_ranges"].items():
            for cl, n in r["class_counts"].items():
                srows.append({"manifest": man["name"], "split": sp_, "class": cl, "cases": n, "n_split": r["n_cases"]})
    write_csv(os.path.join(out, "split_class_distributions.csv"), srows)
    imb = max(cc.values()) / min(cc.values())
    add("F1_class_imbalance", f"Fault classes are imbalanced: {max(cc, key=cc.get)} has {max(cc.values())} cases and {min(cc, key=cc.get)} only {min(cc.values())} (ratio {imb:.1f}:1).",
        {"category_counts": dict(cc), "ratio": round(imb, 2)})

    # 4 feature distributions by modality (training partition, live entries)
    hist = {}
    edges = np.linspace(-6, 6, 61)
    for m in MODALITIES:
        sub = X[train][:, :, groups[m]][:, live[:, groups[m]]]
        nz = sub[sub != 0]
        h, _ = np.histogram(np.clip(nz, -6, 6), bins=edges)
        hist[m] = {"zero_count": int((sub == 0).sum()), "nonzero_count": int(nz.size), "bin_edges": edges.tolist(), "counts": h.tolist(),
                   "quantiles": {str(q): float(np.percentile(sub, q)) for q in (1, 5, 25, 50, 75, 95, 99)},
                   "fraction_abs_gt_3": float((np.abs(sub) > 3).mean())}
    write_json(os.path.join(out, "feature_histograms_train.json"), hist)

    # 5 missingness / structural zeros
    mrows = []
    for i, n in enumerate(nodes):
        for j, m in enumerate(MODALITIES):
            sub = X[train][:, i, :][:, groups[m]]
            mrows.append({"node": n, "modality": m, "zero_fraction_train": float((sub == 0).mean()),
                          "structurally_absent": int(sc["absent_block"][i, j]),
                          "all_zero_row_fraction_train": float((sub == 0).all(axis=1).mean())})
    write_csv(os.path.join(out, "missingness_node_modality_train.csv"), mrows)
    ch_rows = []
    for i, n in enumerate(channels):
        v = X[train][:, :, i][:, live[:, i]]
        ch_rows.append({"index": i, "name": n, "modality": owner[i], "live_nodes": int(live[:, i].sum()),
                        "zero_fraction_live_train": float((v == 0).mean()) if v.size else None})
    write_csv(os.path.join(out, "zero_fraction_by_channel_train.csv"), ch_rows)
    absent_total = int(sc["absent_block"].sum())
    drop_rows = sum(1 for r in mrows if not r["structurally_absent"] and r["all_zero_row_fraction_train"] > 0)
    add("F2_structural_zeros", f"{int(sc['absent_block'][:, 1].sum())} nodes have no trace features and {int(sc['absent_block'][:, 2].sum())} have no log features in any training sample "
        f"(structural absence, not missing values); overall {mod_rows['metric']['zero_fraction_all_entries']:.0%} of metric entries are exactly 0 (zero equals the series mean after ARMOR's scaling - inferred, so a zero is not a missing value).",
        {"structural_absent_blocks": absent_total, "node_modality_blocks_with_some_all_zero_rows": drop_rows})

    # 6 correlation (train, system-level series = mean over live nodes per channel)
    live_cnt = np.maximum(live.sum(axis=0), 1)
    S = (X[train] * live[None]).sum(axis=1) / live_cnt                 # (N_train, 130)
    sd = S.std(axis=0)
    keep = sd > 1e-9
    C = np.full((S.shape[1], S.shape[1]), np.nan)
    C[np.ix_(keep, keep)] = np.corrcoef(S[:, keep].T)
    write_csv(os.path.join(out, "correlation_channels_train.csv"),
              [dict({"channel": channels[i]}, **{channels[j]: (None if np.isnan(C[i, j]) else round(float(C[i, j]), 4)) for j in range(len(channels))}) for i in range(len(channels))])
    pairs = []
    ki = np.nonzero(keep)[0]
    for a in range(len(ki)):
        for b in range(a + 1, len(ki)):
            r = C[ki[a], ki[b]]
            if abs(r) >= 0.95:
                pairs.append((channels[ki[a]], channels[ki[b]], float(r)))
    pairs.sort(key=lambda p: -abs(p[2]))
    write_csv(os.path.join(out, "highly_correlated_pairs_train.csv"), [{"channel_a": a, "channel_b": b, "pearson_r": r, "same_modality": owner[channels.index(a)] == owner[channels.index(b)]} for a, b, r in pairs] or [{"channel_a": "", "channel_b": "", "pearson_r": "", "same_modality": ""}])
    mc = np.zeros((3, 3))
    for a, ma in enumerate(MODALITIES):
        for b, mb in enumerate(MODALITIES):
            sub = C[np.ix_(groups[ma], groups[mb])]
            mc[a, b] = float(np.nanmean(np.abs(sub))) if np.isfinite(sub).any() else float("nan")
    write_json(os.path.join(out, "correlation_modality_summary_train.json"), {"modalities": list(MODALITIES), "mean_abs_correlation": mc.tolist(),
                                                                          "non_constant_channels": int(keep.sum()), "constant_channels": int((~keep).sum())})
    add("F3_correlation", f"{len(pairs)} channel pairs have |r| >= 0.95 on system-level training series ({int((~keep).sum())} channels are constant and excluded); "
        f"mean |r| within metrics is {mc[0, 0]:.2f}.", {"pairs_ge_0.95": len(pairs), "mean_abs_corr": mc.tolist()})

    # 7 temporal trends (full timeline, descriptive): system-level mean |x| per modality, 10-min means
    tt = []
    A = np.abs(X)
    mod_series = {m: (A[:, :, groups[m]] * live[None][:, :, groups[m]]).sum(axis=(1, 2)) / max(int(live[:, groups[m]].sum()), 1) for m in MODALITIES}
    step = 10
    for s in range(0, len(ts) - step + 1, step):
        sl = slice(s, s + step)
        if ts[s + step - 1] - ts[s] != 60 * (step - 1):
            continue
        tt.append({"timestamp": int(ts[s]), "utc": iso(ts[s]), **{f"{m}_mean_abs": float(mod_series[m][sl].mean()) for m in MODALITIES},
                   "test_file_fraction": float(is_test[sl].mean())})
    write_csv(os.path.join(out, "temporal_trends_full_10min.csv"), tt)

    # 8 incident-aligned numerical plots
    inc = []
    cover = Counter()
    per_case = {}
    for i, c in enumerate(cases):
        ridx, how = root_nodes(c["cmdb_id"], nodes)
        j0 = nearest_index(ts, c["timestamp"], 30)
        if not ridx or j0 is None:
            continue
        others = [k for k in range(len(nodes)) if k not in ridx]
        rec = {}
        for k in OFFSETS:
            j = j0 + k
            if not (0 <= j < len(ts)) or ts[j] - ts[j0] != 60 * k:
                continue
            cover[k] += 1
            a = np.abs(X[j])
            for m in MODALITIES:
                cm = groups[m]
                lv = live[:, cm]
                def mean_over(rows):
                    msk = lv[rows]
                    return float((a[rows][:, cm] * msk).sum() / msk.sum()) if msk.sum() else None
                rec[(k, m)] = (mean_over(ridx), mean_over(others))
        per_case[i] = rec
    tr_cases = set(range(final["case_ranges"]["train"]["start_index"], final["case_ranges"]["train"]["end_index_exclusive"]))
    for cat in sorted(cc):
        for part in ("train_cases", "heldout_cases"):   # heldout = validation + test cases: descriptive only
            idx = [i for i in per_case if cats[i] == cat and ((i in tr_cases) == (part == "train_cases"))]
            for k in OFFSETS:
                for m in MODALITIES:
                    vals = [per_case[i][(k, m)] for i in idx if (k, m) in per_case[i] and per_case[i][(k, m)][0] is not None]
                    if vals:
                        inc.append({"category": cat, "partition": part, "offset_min": k, "modality": m, "n_cases": len(vals),
                                    "root_mean_abs": float(np.mean([v[0] for v in vals])), "other_mean_abs": float(np.mean([v[1] for v in vals]))})
    write_csv(os.path.join(out, "incident_aligned.csv"), inc)
    ratios = {}
    for m in MODALITIES:
        pre = [r["root_mean_abs"] / r["other_mean_abs"] for r in inc if r["partition"] == "train_cases" and r["modality"] == m and r["offset_min"] < 0 and r["other_mean_abs"] > 0]
        post = [r["root_mean_abs"] / r["other_mean_abs"] for r in inc if r["partition"] == "train_cases" and r["modality"] == m and 0 <= r["offset_min"] <= 4 and r["other_mean_abs"] > 0]
        ratios[m] = {"pre_mean_ratio": float(np.mean(pre)) if pre else None, "post_mean_ratio": float(np.mean(post)) if post else None}
    cov = {str(k): int(v) for k, v in sorted(cover.items())}
    write_json(os.path.join(out, "incident_aligned_coverage.json"), {"cases_with_sample_at_offset": cov, "n_cases_aligned": len(per_case), "offsets_minutes": OFFSETS})
    add("F4_incident_alignment", "Root-cause-node deviation relative to other nodes (mean |value| ratio, training cases): " +
        "; ".join(f"{m} {ratios[m]['pre_mean_ratio']:.2f} before vs {ratios[m]['post_mean_ratio']:.2f} after injection" for m in MODALITIES if ratios[m]["pre_mean_ratio"] and ratios[m]["post_mean_ratio"]) +
        ". Service-level cases average over all replicas of the named service.", {"ratios": ratios, "aligned_cases": len(per_case)})

    # 9 variability and outliers (train)
    vrows = []
    for i, n in enumerate(channels):
        v = X[train][:, :, i][:, live[:, i]].astype(np.float64).ravel()
        if v.size == 0 or v.std() == 0:
            vrows.append({"index": i, "name": n, "modality": owner[i], "std": 0.0, "kurtosis": None, "fraction_abs_gt_3": 0.0, "max_abs": float(np.abs(v).max()) if v.size else 0.0, "constant": True})
            continue
        vrows.append({"index": i, "name": n, "modality": owner[i], "std": float(v.std()), "kurtosis": float(stats.kurtosis(v)),
                      "fraction_abs_gt_3": float((np.abs(v) > 3).mean()), "max_abs": float(np.abs(v).max()), "constant": False})
    write_csv(os.path.join(out, "variability_outliers_train.csv"), vrows)
    top = sorted([r for r in vrows if not r["constant"]], key=lambda r: -r["fraction_abs_gt_3"])[:3]
    add("F5_outliers", f"{sum(1 for r in vrows if r['constant'])} channels are constant in the training partition. Heaviest tails: " +
        ", ".join(f"{r['name']} ({r['fraction_abs_gt_3']:.1%} of values beyond |3|)" for r in top) + ".", {"top": [r["name"] for r in top]})

    # 10 train vs validation (approved Model 1 split; diagnostic only, nothing is tuned on validation)
    krows = []
    for i, n in enumerate(channels):
        lv = live[:, i]
        a = X[a_tr][:, :, i][:, lv].ravel()
        b = X[a_va][:, :, i][:, lv].ravel()
        if a.size == 0 or b.size == 0 or (a.std() == 0 and b.std() == 0):
            krows.append({"index": i, "name": n, "modality": owner[i], "ks": 0.0, "p_value": 1.0, "std_mean_shift": 0.0, "train_mean": float(a.mean()) if a.size else None,
                          "val_mean": float(b.mean()) if b.size else None, "flag": False})
            continue
        r = stats.ks_2samp(a, b)
        sdv = a.std() or 1.0
        krows.append({"index": i, "name": n, "modality": owner[i], "ks": float(r.statistic), "p_value": float(r.pvalue),
                      "std_mean_shift": float((b.mean() - a.mean()) / sdv), "train_mean": float(a.mean()), "val_mean": float(b.mean()),
                      "flag": bool(r.statistic >= KS_FLAG)})
    write_csv(os.path.join(out, "train_vs_validation_model1.csv"), krows)
    nf = sum(1 for r in krows if r["flag"])
    worst = max(krows, key=lambda r: r["ks"])
    add("F6_train_vs_validation", f"On the approved Model 1 split, {nf} of {len(channels)} channels differ between training and validation by KS >= {KS_FLAG} "
        f"(largest: {worst['name']}, KS {worst['ks']:.2f}). Diagnostic only: nothing is tuned on validation, and KS on pooled entries is sensitive to the large zero mass.",
        {"flagged": nf, "max_ks": worst["ks"], "max_channel": worst["name"], "train_samples": int(a_tr.sum()), "validation_samples": int(a_va.sum())})

    findings.append({"id": "F7_scope", "finding": "Model-development statistics (scaler, structural masks, histograms, correlations, outliers, incident ratios on train cases) use only the approved Model 1 train period; "
                     "the validation period appears only in the diagnostic train-vs-validation comparison; temporal trends, descriptive stats and held-out-case rows are full-dataset descriptive views and are labelled as such.", "evidence": {}})
    write_json(os.path.join(out, "eda_findings.json"), {"findings": findings, "ks_flag_threshold": KS_FLAG})
    return findings


