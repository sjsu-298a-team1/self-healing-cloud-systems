"""Static inspection of the extracted ARMOR D1 release. Writes JSON/CSV evidence.

No pickle is deserialized: pickles are read with pickle_symbolic (opcode-level,
non-executing) and tensor payloads are parsed as raw numbers by torch_blob.
Requires numpy (analysis only). ARMOR code is never imported or run.

Usage:  python3 -I inspect_d1.py [--raw DIR] [--manifest-dir DIR]
"""
import argparse
import csv
import datetime
import hashlib
import json
import os
import sys
from collections import Counter

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d1_checks as ck  # noqa: E402
import pickle_symbolic as ps  # noqa: E402
import torch_blob as tb  # noqa: E402

RAW_DEFAULT = "armor_zenodo_21744694"
FEAT_SHAPE = (46, 130)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def iso(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat(timespec="seconds")


def load_samples(path, keep=True):
    raw = ps.read_symbolic(path, keep_bytes=keep, hash_bytes=not keep)
    if not isinstance(raw, list) or any((not isinstance(s, list)) or len(s) != 3 for s in raw):
        raise ValueError(f"{path}: expected list of [timestamp, graph, tensor] triples")
    return raw


def graph_edges(graph_node, np_):
    state = graph_node.state["_graph"].state.state
    src, dst = (tb.tensor_to_array(t, np_) for t in state[2])
    return src, dst


def sample_arrays(samples):
    ts, feats, topo, ecount = [], [], Counter(), []
    topo_per_sample = []
    for t, g, x in samples:
        ts.append(t)
        feats.append(tb.tensor_to_array(x, np))
        src, dst = graph_edges(g, np)
        key = hashlib.md5(src.tobytes() + dst.tobytes()).hexdigest()
        topo[key] += 1
        topo_per_sample.append(key)
        ecount.append(int(src.shape[0]))
    return ts, np.stack(feats), topo, ecount


def group_stats(X, groups):
    out = {}
    for m, idx in groups.items():
        sub = X[:, :, idx]
        per_channel_zero = (sub == 0).mean(axis=(0, 1))
        row_all_zero = (sub == 0).all(axis=2).mean()
        out[m] = {
            "channels": len(idx),
            "nan": int(np.isnan(sub).sum()),
            "inf": int(np.isinf(sub).sum()),
            "zero_fraction": round(float((sub == 0).mean()), 6),
            "node_sample_rows_all_zero_fraction": round(float(row_all_zero), 6),
            "all_zero_channels": int((per_channel_zero == 1.0).sum()),
            "mostly_zero_channels_gt_90pct": int((per_channel_zero > 0.9).sum()),
            "min": round(float(sub.min()), 4), "max": round(float(sub.max()), 4),
            "mean": round(float(sub.mean()), 4), "std": round(float(sub.std()), 4),
        }
    return out


def scaling_evidence(regions, np_):
    """Per-channel (over samples and nodes) mean/std for candidate fit regions."""
    out = {}
    for name, X in regions.items():
        if X.shape[0] == 0:
            out[name] = {"n_samples": 0}
            continue
        mu = X.astype("float64").mean(axis=(0, 1))
        sd = X.astype("float64").std(axis=(0, 1))
        nonconst = sd > 1e-12
        out[name] = {
            "n_samples": int(X.shape[0]),
            "channel_mean_abs_max": round(float(np_.abs(mu).max()), 5),
            "channel_mean_abs_median": round(float(np_.median(np_.abs(mu))), 5),
            "channel_std_median_nonconstant": round(float(np_.median(sd[nonconst])), 5),
            "channel_std_min_nonconstant": round(float(sd[nonconst].min()), 5),
            "channel_std_max": round(float(sd.max()), 5),
            "constant_channels": int((~nonconst).sum()),
        }
    return out


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.abspath(os.path.join(here, ".."))
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(data_dir, "raw", RAW_DEFAULT))
    ap.add_argument("--manifest-dir", default=os.path.join(data_dir, "manifests", "armor_d1"))
    args = ap.parse_args()
    d1 = os.path.join(args.raw, "extracted", "D1")
    out = args.manifest_dir
    os.makedirs(out, exist_ok=True)

    # ---- inventory ---------------------------------------------------------
    inv = []
    for root, _dirs, files in sorted(os.walk(d1)):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, d1)
            kind = "csv" if fn.endswith(".csv") else "pickle" if fn.endswith(".pkl") else "other"
            inv.append({"path": rel, "bytes": os.path.getsize(p), "format": kind, "sha256": sha256(p)})
    # ---- small, literal inputs --------------------------------------------
    cases = ck.read_cases_csv(os.path.join(d1, "cases", "cases.csv"))
    ad_ts = ps.read_symbolic(os.path.join(d1, "cases", "ad_cases.pkl"))
    node_hash = ps.read_symbolic(os.path.join(d1, "hash_info", "node_hash.pkl"))
    type_hash = ps.read_symbolic(os.path.join(d1, "hash_info", "type_hash.pkl"))
    type_dict = ps.read_symbolic(os.path.join(d1, "hash_info", "type_dict.pkl"))
    channel_names = ps.read_symbolic(os.path.join(d1, "hash_info", "channel_dict.pkl"))
    for name, obj in [("ad_cases", ad_ts), ("node_hash", node_hash), ("type_hash", type_hash),
                      ("type_dict", type_dict), ("channel_dict", channel_names)]:
        refs = ps.global_refs(obj)
        if refs:
            raise SystemExit(f"{name}.pkl references globals {refs}; refusing to treat as literal data")
    cfg_path = os.path.join(args.raw, "ARMOR", "config", "D1.yaml")
    feat_span = ck.parse_feat_span(open(cfg_path).read())
    groups = ck.modality_groups(channel_names, feat_span)

    with open(os.path.join(out, "channel_map.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["index", "name", "modality"])
        owner = {i: m for m, idx in groups["indices"].items() for i in idx}
        for i, n in enumerate(channel_names):
            w.writerow([i, n, owner.get(i, "UNASSIGNED")])
    with open(os.path.join(out, "label_mappings.json"), "w") as fh:
        json.dump({"fine_type_to_category_id": type_hash,
                   "category_id_to_name": {str(k): v for k, v in type_dict.items()},
                   "node_name_to_index": node_hash}, fh, indent=2)

    # ---- sample files ------------------------------------------------------
    train_raw = load_samples(os.path.join(d1, "samples", "train_samples.pkl"), keep=True)
    test_raw = load_samples(os.path.join(d1, "samples", "test_samples.pkl"), keep=True)
    all_raw = load_samples(os.path.join(d1, "samples", "samples.pkl"), keep=True)
    tr_ts, Xtr, tr_topo, tr_edges = sample_arrays(train_raw)
    te_ts, Xte, te_topo, te_edges = sample_arrays(test_raw)
    all_ts, Xall, all_topo, _ = sample_arrays(all_raw)
    by_ts = {t: i for i, t in enumerate(all_ts)}
    identical = (sorted(all_ts) == sorted(tr_ts + te_ts)
                 and all(np.array_equal(Xall[by_ts[t]], x) for t, x in zip(tr_ts, Xtr))
                 and all(np.array_equal(Xall[by_ts[t]], x) for t, x in zip(te_ts, Xte)))
    del all_raw

    train_set, test_set = set(tr_ts), set(te_ts)
    n_cases = len(cases)
    case_ts = [c["timestamp"] for c in cases]
    case_idx = ck.case_split_index(n_cases, 0.6)
    split_ts = ck.ad_split_timestamp(tr_ts, te_ts, 0.6)
    tr_sorted, te_sorted = sorted(tr_ts), sorted(te_ts)
    held_out = case_ts[case_idx:]
    ad_sorted = sorted(ad_ts)

    # per-case window coverage (ARMOR before=59, after=300)
    cov_test = ck.window_counts(case_ts, te_sorted)
    cov_train = ck.window_counts(case_ts, tr_sorted)
    near_tr = ck.samples_within(tr_ts, ad_sorted, 300)
    near_te = ck.samples_within(te_ts, ad_sorted, 300)
    held_win_train = sum(ck.window_counts(held_out, tr_sorted))
    train_after_split = sum(1 for t in tr_ts if t > split_ts)
    eval_total = sum(1 for t in tr_ts + te_ts if t > split_ts)

    # ---- class distributions ----------------------------------------------
    dist = {
        "all": ck.class_counts(cases, type_hash, type_dict),
        "armor_ft_rcl_train_first60pct": ck.class_counts(cases, type_hash, type_dict, 0, case_idx),
        "armor_ft_rcl_test_last40pct": ck.class_counts(cases, type_hash, type_dict, case_idx),
    }
    with open(os.path.join(out, "class_distribution.csv"), "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["scope", "label_kind", "label", "count"])
        for scope, d in dist.items():
            for kind in ("category", "fine"):
                for lab, n in sorted(d[kind].items(), key=lambda kv: (-kv[1], kv[0])):
                    w.writerow([scope, kind, lab, n])
        for scope, lo, hi in (("all", 0, None), ("armor_ft_rcl_train_first60pct", 0, case_idx),
                              ("armor_ft_rcl_test_last40pct", case_idx, None)):
            for k, v in sorted(Counter(c["cmdb_id"] for c in cases[lo:hi]).items(), key=lambda kv: (-kv[1], kv[0])):
                w.writerow([scope, "root_cause_cmdb_id", k, v])
            for k, v in sorted(Counter(c["level"] for c in cases[lo:hi]).items()):
                w.writerow([scope, "failure_level", k, v])


    # ---- additional audits -------------------------------------------------
    allX = np.concatenate([Xtr, Xte])

    def nodechan_scaling(X):
        mu = X.astype("float64").mean(axis=0)
        sd = X.astype("float64").std(axis=0)
        nonconst = sd > 1e-12
        z = nonconst & (np.abs(mu) < 1e-3) & (np.abs(sd - 1) < 1e-3)
        return {"n_samples": int(X.shape[0]), "nonconstant_node_channel_series": int(nonconst.sum()),
                "series_with_mean0_std1_tol1e-3": int(z.sum()),
                "fraction_of_nonconstant": round(float(z.sum() / max(nonconst.sum(), 1)), 4)}

    nodechan = {"train_plus_test": nodechan_scaling(allX), "train_only": nodechan_scaling(Xtr),
                "test_only": nodechan_scaling(Xte), "samples_pkl_full_timeline": nodechan_scaling(Xall)}
    node_names = [n for n, _ in sorted(node_hash.items(), key=lambda kv: kv[1])]
    per_node_zero = {}
    for m in ("trace", "log"):
        idx = groups["indices"][m]
        zero_rows = (Xall[:, :, idx] == 0).all(axis=2).mean(axis=0)
        per_node_zero[m] = {n: round(float(zero_rows[i]), 4) for i, n in enumerate(node_names)}
    always_zero = {m: [n for n, f in per_node_zero[m].items() if f == 1.0] for m in per_node_zero}
    sometimes_zero = {m: {n: f for n, f in per_node_zero[m].items() if 0 < f < 1.0} for m in per_node_zero}

    blocks180 = [Xall[i:i + 180] for i in range(0, len(Xall), 180)]
    block_ev = ck.block_zscore_evidence(blocks180)
    nonconst = block_ev["series_blocks"] - block_ev["constant"]
    block_ev["fraction_of_nonconstant_mean0_std1"] = round(block_ev["mean0_std1"] / max(nonconst, 1), 4)
    block_ev["block_size_samples"] = 180
    block_ev["max_abs_value"] = round(float(np.abs(Xall).max()), 6)
    block_ev["sqrt_179"] = round(float(np.sqrt(179)), 6)
    bounds = ck.segment_bounds(te_sorted)
    offs, uncovered = ck.case_segment_offsets(case_ts, bounds)
    segment_info = {
        "test_segments": len(bounds), "cases_not_inside_any_test_segment": uncovered,
        "cases_per_segment_max": max(Counter(b for b in (next((i for i, bd in enumerate(bounds) if bd[0] <= c <= bd[1]), None) for c in case_ts)).values()),
        "seconds_before_case_in_segment_min_median_max": [min(o[0] for o in offs), sorted(o[0] for o in offs)[len(offs) // 2], max(o[0] for o in offs)],
        "seconds_after_case_in_segment_min_median_max": [min(o[1] for o in offs), sorted(o[1] for o in offs)[len(offs) // 2], max(o[1] for o in offs)],
    }
    extras = sorted(set(ad_ts) - set(case_ts))
    missing_from_ad = sorted(set(case_ts) - set(ad_ts))
    near_case = [min(abs(e - c) for c in case_ts) for e in extras]
    near_ad = [min(abs(c - a) for a in ad_ts) for c in missing_from_ad]
    ad_detail = {
        "extra_ad_timestamps_not_in_cases_csv": len(extras),
        "extra_nearest_case_delta_seconds": sorted(near_case),
        "cases_missing_from_ad_cases": len(missing_from_ad),
        "missing_case_nearest_ad_delta_seconds": sorted(near_ad),
        "extra_ad_timestamps_inside_test_sample_range": sum(1 for e in extras if min(te_ts) <= e <= max(te_ts)),
    }
    gaps = [b - a for a, b in zip(case_ts, case_ts[1:])]
    overlapping_pairs = sum(1 for g in gaps if g < 359)
    cross = 1 if case_ts[case_idx] - case_ts[case_idx - 1] < 359 else 0
    overlap_info = {
        "case_window_seconds": 359, "min_gap_between_consecutive_cases_seconds": min(gaps),
        "consecutive_case_pairs_with_overlapping_windows": overlapping_pairs,
        "train_to_test_boundary_gap_seconds": case_ts[case_idx] - case_ts[case_idx - 1],
        "train_to_test_boundary_windows_overlap": bool(cross),
    }
    budget = {}
    tr_cat = dist["armor_ft_rcl_train_first60pct"]["category"]
    for pct in (10, 25, 50, 100):
        budget[f"{pct}%"] = {"train_cases": round(case_idx * pct / 100),
                             "expected_per_category": {k: round(v * pct / 100, 1) for k, v in sorted(tr_cat.items())},
                             "min_expected_class_count": round(min(tr_cat.values()) * pct / 100, 1)}

    # ---- evidence documents ------------------------------------------------
    allX = np.concatenate([Xtr, Xte])
    first60_mask_tr = np.array([t <= split_ts for t in tr_ts])
    scaling = scaling_evidence({
        "train_samples": Xtr, "test_samples": Xte, "train_plus_test": allX,
        "train_samples_up_to_ad_split_ts": Xtr[first60_mask_tr],
    }, np)

    case_overview = {
        "n_cases": n_cases, "cases_sorted_by_time": case_ts == sorted(case_ts),
        "duplicate_case_timestamps": n_cases - len(set(case_ts)),
        "first_case_utc": iso(case_ts[0]), "last_case_utc": iso(case_ts[-1]),
        "failure_level_counts": dict(Counter(c["level"] for c in cases)),
        "distinct_fine_failure_types": len({c["failure_type"] for c in cases}),
        "distinct_categories": len(set(type_hash.values())),
        "unmapped_failure_types": ck.unmapped_failure_types(cases, type_hash),
        "distinct_root_cause_ids": len({c["cmdb_id"] for c in cases}),
        "root_cause_vs_graph_nodes": ck.exact_root_cause_in_nodes(cases, node_hash),
        "ad_cases_pkl_count": len(ad_ts),
        "ad_cases_not_in_cases_csv": len(set(ad_ts) - set(case_ts)),
        "cases_csv_not_in_ad_cases": len(set(case_ts) - set(ad_ts)),
        "ad_cases_sorted": list(ad_ts) == sorted(ad_ts),
        "case_columns": ["timestamp", "level", "cmdb_id", "failure_type"],
        "has_end_time_or_duration_column": False,
    }
    feature_report = {
        "tensor_shape_per_sample": list(FEAT_SHAPE),
        "tensor_shapes_seen": sorted({tuple(x.shape) for x in (Xtr[0], Xte[0])}),
        "dtype": str(Xtr.dtype),
        "n_nodes": len(node_hash), "n_channels": len(channel_names),
        "modality_groups": {k: v for k, v in groups.items() if k != "names" and k != "indices"},
        "feat_span_config_D1_yaml": feat_span,
        "group_stats_train": group_stats(Xtr, groups["indices"]),
        "group_stats_test": group_stats(Xte, groups["indices"]),
        "scaling_evidence": scaling,
        "scaling_evidence_per_node_channel": nodechan,
        "scaling_evidence_180_sample_blocks": block_ev,
        "structurally_absent_modality_nodes_always_zero": always_zero,
        "partially_zero_modality_nodes": sometimes_zero,
        "nan_total": int(np.isnan(allX).sum()), "inf_total": int(np.isinf(allX).sum()),
        "graph": {
            "train_distinct_topologies": len(tr_topo), "test_distinct_topologies": len(te_topo),
            "shared_topologies_between_train_test": len(set(tr_topo) & set(te_topo)),
            "edges_per_sample_train": sorted(set(tr_edges)), "edges_per_sample_test": sorted(set(te_edges)),
            "edge_dtype": "int64", "directed_edge_arrays": "src,dst (two int64 tensors per graph)",
        },
    }
    split_report = {
        "samples": {
            "train_samples": ck.sampling_profile(tr_ts), "test_samples": ck.sampling_profile(te_ts),
            "samples_pkl": ck.sampling_profile(all_ts),
            "train_test_timestamp_overlap": len(train_set & test_set),
            "samples_pkl_is_exact_union_of_train_and_test_by_timestamp_and_values": bool(identical),
            "timestamp_epoch_unit": "seconds (UTC)", "nominal_step_seconds": 60,
            "train_range_utc": [iso(min(tr_ts)), iso(max(tr_ts))],
            "test_range_utc": [iso(min(te_ts)), iso(max(te_ts))],
        },
        "armor_ad_split_derived_from_code": {
            "formula": "split_ts = sorted(train+test timestamps)[int(0.6*N)]; init=train<=split_ts; eval=all>split_ts",
            "split_ts": split_ts, "split_ts_utc": iso(split_ts),
            "eval_samples": eval_total,
            "ad_ground_truth_events_after_split": sum(1 for t in ad_ts if t > split_ts),
            "ad_ground_truth_events_total": len(ad_ts),
        },
        "armor_ft_rcl_split_derived_from_code": {
            "formula": "cases[:int(0.6*N)] train, cases[int(0.6*N):] test (case order = cases.csv order)",
            "train_cases": case_idx, "test_cases": n_cases - case_idx,
            "first_test_case_ts": case_ts[case_idx], "first_test_case_utc": iso(case_ts[case_idx]),
            "ad_split_ts_minus_first_test_case_ts_seconds": split_ts - case_ts[case_idx],
            "cases_after_ad_split_ts": sum(1 for t in case_ts if t > split_ts),
        },
        "window_capacity": {
            "windows_of_6_steps": {"train_samples": ck.window_capacity(tr_sorted, 6), "test_samples": ck.window_capacity(te_sorted, 6)},
            "armor_series_of_7_steps": {"train_samples": ck.window_capacity(tr_sorted, 7), "test_samples": ck.window_capacity(te_sorted, 7)},
            "note": "windows lie wholly inside runs of consecutive 60 s samples; ARMOR's create_dataloader_AR "
                    "needs window_size+1 = 7 consecutive samples (6 inputs + next-step target, max_gap 60 s)"},
        "case_window_coverage": {
            "window": "[case_ts-59, case_ts+300) seconds",
            "test_samples_cases_with_zero_samples": sum(1 for c in cov_test if c == 0),
            "test_samples_per_case_min_median_max": [min(cov_test), sorted(cov_test)[len(cov_test) // 2], max(cov_test)],
            "train_samples_cases_with_any_sample": sum(1 for c in cov_train if c > 0),
            "train_samples_in_any_case_window_total": sum(cov_train),
            "train_samples_in_heldout_case_windows": held_win_train,
        },
        "pretraining_exposure": {
            "pretrain_set_per_config": "train_samples_num: whole (all of train_samples.pkl)",
            "train_samples_total": len(tr_ts),
            "train_samples_after_ad_split_ts": train_after_split,
            "train_samples_within_300s_of_any_failure_ts": int(sum(near_tr)),
            "train_samples_within_300s_of_a_cases_csv_ts": int(sum(ck.samples_within(tr_ts, sorted(case_ts), 300))),
            "train_samples_within_300s_of_an_ad_event_absent_from_cases_csv": int(sum(ck.samples_within(tr_ts, extras, 300))),
            "test_samples_within_300s_of_any_failure_ts": int(sum(near_te)),
            "train_samples_in_heldout_case_windows": held_win_train,
        },
        "ad_ground_truth_vs_cases_csv": ad_detail,
        "case_to_test_segment": segment_info,
        "case_window_overlap": overlap_info,
        "label_budget_feasibility_first60pct_train_cases": budget,
        "derived_detection_labels_note": "No incident intervals are released: only injection timestamps; "
                                         "any sample-level label is derived (+/-300s tolerance used by ARMOR eval_AD).",
    }
    summary = {
        "generated_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
        "cases": case_overview, "features": feature_report, "split_and_leakage": split_report,
        "class_distribution": dist,
    }
    for name, obj in [("file_inventory.json", inv), ("d1_inspection.json", summary)]:
        with open(os.path.join(out, name), "w") as fh:
            json.dump(obj, fh, indent=2, default=str)
    with open(os.path.join(out, "file_inventory.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["path", "bytes", "format", "sha256"])
        w.writeheader()
        w.writerows(inv)
    os.remove(os.path.join(out, "file_inventory.json"))
    print(json.dumps({"cases": case_overview, "split": split_report["armor_ad_split_derived_from_code"],
                      "ft_split": split_report["armor_ft_rcl_split_derived_from_code"]}, indent=1, default=str))


if __name__ == "__main__":
    main()
