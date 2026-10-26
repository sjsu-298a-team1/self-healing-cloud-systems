"""STEP 3: reproducible inspection evidence from the actual D1 files (no hardcoded counts)."""
import hashlib
import os
from collections import Counter

import numpy as np

from . import paths
from .common import iso, nearest_index, read_json, root_nodes, sha256_file, write_csv, write_json
from .loader import MODALITIES, category_of
import d1_checks as ck  # noqa: E402


def run(labels, ts, X, is_test):
    out = paths.art("inspection")
    cases, nodes, channels, groups = labels["cases"], labels["nodes"], labels["channels"], labels["groups"]
    owner = {i: m for m, idx in groups.items() for i in idx}
    cats = [category_of(c, labels) for c in cases]

    # --- schema (stable feature ordering) ---
    schema = {
        "schema_version": "1.0",
        "tensor_shape_per_sample": [len(nodes), len(channels)],
        "dtype": str(X.dtype),
        "node_order": nodes,
        "channel_order": [{"index": i, "name": n, "modality": owner[i]} for i, n in enumerate(channels)],
        "modality_index_ranges": {m: groups[m] for m in MODALITIES},
        "feat_span_from_ARMOR_config": labels["feat_span"],
        "channel_order_sha256": hashlib.sha256("\n".join(channels).encode()).hexdigest(),
        "node_order_sha256": hashlib.sha256("\n".join(nodes).encode()).hexdigest(),
        "category_ids": {str(k): v for k, v in labels["type_dict"].items()},
        "fine_type_to_category_id": labels["type_hash"],
    }
    write_json(os.path.join(out, "schema.json"), schema)

    # --- per-channel descriptive statistics (full dataset, descriptive only) ---
    flat = X.reshape(-1, X.shape[2])
    rows = []
    for i, n in enumerate(channels):
        v = flat[:, i]
        rows.append({"index": i, "name": n, "modality": owner[i], "mean": float(v.mean()), "std": float(v.std()),
                     "min": float(v.min()), "max": float(v.max()), "zero_fraction": float((v == 0).mean()),
                     "constant_over_all_samples": bool(v.min() == v.max())})
    write_csv(os.path.join(out, "channel_statistics_full_dataset.csv"), rows)

    # --- timestamps and sampling ---
    d = np.diff(ts)
    days = Counter(iso(t)[:10] for t in ts)
    sampling = {"count": int(len(ts)), "first": iso(ts[0]), "last": iso(ts[-1]), "first_epoch": int(ts[0]), "last_epoch": int(ts[-1]),
                "step_seconds_counts": {str(k): int(v) for k, v in Counter(d.tolist()).most_common(6)},
                "nominal_step_seconds": 60, "samples_per_utc_day": dict(sorted(days.items())),
                "is_sorted": bool((d > 0).all()), "unique": bool(len(set(ts.tolist())) == len(ts))}
    cut = [0] + [int(i) + 1 for i in np.nonzero(d > 3600)[0]] + [len(ts)]
    sampling["collection_days"] = [{"start": iso(ts[a]), "end": iso(ts[b - 1]), "samples": int(b - a),
                                    "test_file_samples": int(is_test[a:b].sum())} for a, b in zip(cut, cut[1:])]
    sampling["collection_day_note"] = "each run of contiguous 60 s samples starts at 16:00:00Z (= 00:00 at UTC+8, inferred from the timestamps, not documented)"
    case_ts = np.asarray([c["timestamp"] for c in cases])
    cases_info = {"count": len(cases), "first": iso(case_ts.min()), "last": iso(case_ts.max()),
                  "min_gap_s": int(np.diff(case_ts).min()), "median_gap_s": float(np.median(np.diff(case_ts)))}

    # --- class distribution ---
    dist = Counter(cats)
    fine = Counter(c["failure_type"] for c in cases)
    lvl = Counter(c["level"] for c in cases)
    # --- roots ---
    res = Counter(root_nodes(c["cmdb_id"], nodes)[1] for c in cases)

    # --- representative records: one case per category, root-cause node, sample nearest the injection time ---
    reps = []
    for cat in sorted(dist):
        i = next(k for k, c in enumerate(cats) if cats[k] == cat)
        c = cases[i]
        ridx, how = root_nodes(c["cmdb_id"], nodes)
        j = nearest_index(ts, c["timestamp"], 30)
        if j is None or not ridx:
            continue
        node = ridx[0]
        vec = X[j, node, :]
        nz = np.nonzero(vec)[0]
        top = nz[np.argsort(-np.abs(vec[nz]))[:8]]
        reps.append({"case_index": i, "category": cat, "failure_type": c["failure_type"], "level": c["level"],
                     "cmdb_id": c["cmdb_id"], "case_timestamp": c["timestamp"], "case_utc": iso(c["timestamp"]),
                     "root_resolution": how, "node": nodes[node], "sample_timestamp": int(ts[j]),
                     "sample_offset_s": int(ts[j]) - c["timestamp"], "sample_source_file": "test_samples" if is_test[j] else "train_samples",
                     "nonzero_channels_of_130": int(len(nz)),
                     "top_abs_channels": [{"channel": channels[k], "modality": owner[int(k)], "value": float(vec[k])} for k in top],
                     "full_vector": [float(x) for x in vec]})
    write_json(os.path.join(out, "representative_records.json"), reps)

    # --- sizes ---
    inv = []
    inv_path = os.path.join(paths.MANIFESTS_298_43, "file_inventory.csv")
    if os.path.exists(inv_path):
        import csv
        with open(inv_path, newline="") as fh:
            inv = list(csv.DictReader(fh))
    summary = {
        "generated_from": "armor-system/data/raw/armor_zenodo_21744694/extracted/D1 (via data/processed cache)",
        "provenance_reference": "armor-system/data/manifests/armor_d1/provenance.json and checksums.json (Linear 298-43, PR #34)",
        "counts": {"cases": len(cases), "samples": int(len(ts)), "train_file_samples": int((~is_test).sum()),
                   "test_file_samples": int(is_test.sum()), "nodes": len(nodes), "channels": len(channels)},
        "modality_channel_counts": {m: len(groups[m]) for m in MODALITIES},
        "size": {"tensor_bytes_float32": int(X.nbytes), "values": int(X.size),
                 "d1_files": [{"path": r["path"], "bytes": int(r["bytes"])} for r in inv]},
        "dtype": str(X.dtype), "sampling": sampling, "cases": cases_info,
        "classes": {"category_counts": dict(sorted(dist.items())), "fine_type_counts": dict(sorted(fine.items(), key=lambda kv: -kv[1])),
                    "level_counts": dict(lvl), "n_categories": len(dist), "n_fine_types": len(fine)},
        "root_cause_resolution_to_graph_nodes": dict(res),
        "numeric_health": {"nan": int(np.isnan(X).sum()), "inf": int(np.isinf(X).sum()), "max_abs": float(np.abs(X).max()),
                           "sqrt_179": float(np.sqrt(179)), "zero_fraction": float((X == 0).mean()),
                           "constant_channels_over_all_samples": int(sum(r["constant_over_all_samples"] for r in rows))},
        "ground_truth": {
            "available": ["injection timestamp", "failure level", "root-cause instance (cmdb_id)", "fine failure type"],
            "not_available": ["incident end time or duration", "anomaly onset time", "raw telemetry (only precomputed features)"],
            "cases_csv_authoritative_for_supervised_labels": True,
            "ad_cases_pkl": "224 events; 21 AD-only and 7 case-only events are unexplained (originated in the ART release)",
            "reference": "armor-system/docs/d1_validation_report.md section 9",
        },
    }
    rec_path = os.path.join(paths.MANIFESTS_298_43, "label_reconciliation.json")
    if os.path.exists(rec_path):
        summary["label_reconciliation"] = read_json(rec_path)
    write_json(os.path.join(out, "inspection_summary.json"), summary)
    return summary
