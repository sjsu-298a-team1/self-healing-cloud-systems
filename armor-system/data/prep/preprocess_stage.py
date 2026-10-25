"""STEP 5 stage: fit train-only preprocessing, record configuration, counts, and a raw -> prepared example.

Fit sets
  official_train_period   samples <= the ARMOR AD boundary: reference for the unchanged official protocol (no held-out case in it)
  model1_train_period     samples before the approved train|validation boundary: the ONLY fit set for Model 1
Neither fit set ever contains a test sample; the Model 1 fit set contains no validation sample either.
"""
import os

import numpy as np

from . import paths, preprocess as pp
from .common import iso, nearest_index, read_json, root_nodes, write_csv, write_json
from .loader import MODALITIES, category_of

CONFIG_VERSION = "1.1"


def periods(manifest):
    names = [s for s in manifest["case_ranges"]]
    b = [x["boundary_ts"] for x in manifest["sample_time_boundaries"]]
    lo = [-10 ** 18] + b
    hi = b + [10 ** 18]
    return {n: (lo[i], hi[i]) for i, n in enumerate(names)}


def _summ(v):
    return {"mean": float(v.mean()), "std": float(v.std()), "p01": float(np.percentile(v, 1)), "p99": float(np.percentile(v, 99)),
            "zero_fraction": float((v == 0).mean())}


def run(labels, ts, X, is_test, splits_result):
    out = paths.art("preprocessing")
    schema = read_json(paths.art("inspection", "schema.json"))
    groups, nodes, channels, cases = labels["groups"], labels["nodes"], labels["channels"], labels["cases"]
    issues = pp.validate_schema(X, ts, schema) + pp.validate_order(nodes, channels, schema)
    ad_split = splits_result["ad_split"]
    final = splits_result["final"]
    lo, hi = periods(final)["train"]
    fit_sets = {
        "official_train_period": {"status": "approved_reproduction", "mask": ts <= ad_split,
                                  "definition": "samples with timestamp <= the ARMOR AD split (2022-05-06T16:00:00Z); reference for the unchanged official protocol; contains no held-out case"},
        "model1_train_period": {"status": "approved", "mask": (ts >= lo) & (ts < hi),
                                "definition": f"samples before the approved train|validation boundary {iso(hi)}; the only fit set for Model 1 (no validation or test sample)"},
    }
    missing = pp.inspect_missing(X, groups)
    result = {"config_version": CONFIG_VERSION, "schema_issues": issues, "missing_inspection": missing, "fits": {}}
    mask_rows, ba_rows, scalers = [], [], {}
    for name, fs in fit_sets.items():
        sc = pp.fit_scaler(X, fs["mask"], groups)
        scalers[name] = sc
        np.savez_compressed(os.path.join(out, f"scaler_{name}_v1.npz"), mean=sc["mean"], scale=sc["scale"], constant=sc["constant"],
                            absent_block=sc["absent_block"], absent_entry=sc["absent_entry"])
        Xt, ind = pp.transform(X, sc, groups)
        fit = fs["mask"]
        result["fits"][name] = {
            "status": fs["status"], "definition": fs["definition"], "n_fit_samples": int(fit.sum()),
            "fit_first": iso(ts[fit].min()), "fit_last": iso(ts[fit].max()),
            "structural_absent_blocks": {m: int(sc["absent_block"][:, j].sum()) for j, m in enumerate(MODALITIES)},
            "constant_entries_scale_set_to_1": int(sc["constant"].sum()),
            "observed_all_zero_not_structural_node_modality_rows": int(ind["observed_all_zero_not_structural"].sum()),
            "transformed_finite": bool(np.isfinite(Xt).all()), "scaler_file": f"scaler_{name}_v1.npz"}
        for j, m in enumerate(MODALITIES):
            idx = np.zeros(X.shape[2], bool)
            idx[groups[m]] = True
            live = ~sc["absent_entry"][:, idx]
            for per, mask in (("fit", fit), ("after_fit", ~fit & (ts > ts[fit].max()))):
                if not mask.any():
                    continue
                for tag, arr in (("before", X), ("after", Xt)):
                    sub = arr[mask][:, :, idx][:, live].reshape(-1)
                    ba_rows.append({"fit_set": name, "modality": m, "period": per, "stage": tag, "n_samples": int(mask.sum()), **_summ(sub)})
        for i, n in enumerate(nodes):
            for j, m in enumerate(MODALITIES):
                mask_rows.append({"fit_set": name, "node": n, "modality": m, "structurally_absent": int(sc["absent_block"][i, j]), "channels": len(groups[m])})
    write_csv(os.path.join(out, "before_after_summary.csv"), ba_rows)
    write_csv(os.path.join(out, "structural_masks.csv"), mask_rows)

    # ---- counting units: cases, samples (minutes), 7-step windows, AD events -------------------------------
    case_ts = np.asarray([c["timestamp"] for c in cases])
    ad = np.asarray(sorted(labels["ad"]))
    win_rows, unit_rows = [], []
    for mname, man in (("official_armor_v1", splits_result["official"]), (final["name"], final)):
        for split, (plo, phi) in periods(man).items():
            pos = np.nonzero((ts >= plo) & (ts < phi))[0]
            allw = pp.make_windows(ts, pos, window=6, horizon=1)
            kept, dropped = pp.protect_boundaries(ts, allw, plo, phi, window=6, horizon=1)
            win_rows.append({"manifest": mname, "split": split, "samples": int(len(pos)), "windows_7_step": int(len(allw)),
                             "kept_inside_period": int(len(kept)), "dropped_crossing_boundary": int(len(dropped))})
            ad_in = ad[(ad >= plo) & (ad < phi)]
            unit_rows.append({"manifest": mname, "split": split, "cases": man["case_ranges"][split]["n_cases"], "samples_minutes": int(len(pos)),
                              "windows_7_step_kept": int(len(kept)), "ad_events_in_period_any": int(len(ad_in)),
                              "ad_events_scored_after_ad_boundary": int((ad_in > ad_split).sum()),
                              "injection_cases_scored_after_ad_boundary": int(((case_ts >= plo) & (case_ts < phi) & (case_ts > ad_split)).sum())})
    write_csv(os.path.join(out, "window_counts.csv"), win_rows)
    write_csv(os.path.join(out, "split_counts_by_unit.csv"), unit_rows)
    write_json(os.path.join(out, "counting_units.json"), {
        "case": "one fault injection record in cases.csv (210 in total)",
        "sample": "one minute of precomputed features for all 46 nodes: a 46 x 130 tensor with one timestamp (7,200 in total)",
        "window": "7 consecutive one-minute samples (6 inputs + the next step as target) lying wholly inside one split period; counted on the contiguous 7,200-sample timeline",
        "ad_event": "one timestamp in ad_cases.pkl (224; 98 after the AD boundary are scored by ARMOR)",
        "note": "cases, samples, windows and events are different units and are never added together"})
    result["windows"] = win_rows
    result["counts_by_unit"] = unit_rows

    # ---- raw -> validated -> transformed -> prepared example (one Model 1 training case) --------------------
    sc1 = scalers["model1_train_period"]
    tr_cases = range(*[final["case_ranges"]["train"][k] for k in ("start_index", "end_index_exclusive")])
    ex = None
    for i in tr_cases:
        c = cases[i]
        ridx, how = root_nodes(c["cmdb_id"], nodes)
        j0 = nearest_index(ts, c["timestamp"], 30)
        if not ridx or j0 is None or how != "exact" or labels["type_dict"][labels["type_hash"][c["failure_type"]]] != "Node Memory":
            continue
        start = j0 - 3
        try:
            prep = pp.prepare_window(X, ts, sc1, groups, start)
        except ValueError:
            continue
        if ts[start] < lo or ts[start + 6] >= hi:
            continue
        node = ridx[0]
        raw_win = X[start:start + 7, node]
        nz_cols = np.nonzero(np.abs(raw_win).max(axis=0) > 0)[0]
        cols = nz_cols[np.argsort(-np.abs(raw_win[:, nz_cols]).max(axis=0))[:5]]
        owner = {k: m for m, idx in groups.items() for k in idx}
        ex = {"case_index": i, "category": category_of(c, labels), "failure_type": c["failure_type"], "cmdb_id": c["cmdb_id"], "node": nodes[node],
              "split": "train", "case_timestamp": c["timestamp"], "window_first_utc": iso(ts[start]), "window_last_utc": iso(ts[start + 6]),
              "channels_shown": [{"name": channels[k], "modality": owner[int(k)]} for k in cols],
              "stages": [
                  {"stage": "raw", "what": "feature tensor as released (float32)", "shape": [7, 46, 130], "node_excerpt": raw_win[:, cols].round(4).tolist()},
                  {"stage": "validated", "what": "schema, dtype, finiteness, ARMOR bound, consecutive 60 s timestamps", "issues": pp.validate_schema(X[start:start + 7], ts[start:start + 7], schema), "shape": [7, 46, 130]},
                  {"stage": "transformed", "what": "(x - mean) / scale with the Model 1 train-period scaler; structurally absent entries forced to 0",
                   "shape": [7, 46, 130], "node_excerpt": ((np.concatenate([prep["inputs"], prep["target"][None]]))[:, node][:, cols]).round(4).tolist()},
                  {"stage": "prepared", "what": "model-ready window", "arrays": {"inputs": list(prep["inputs"].shape), "target": list(prep["target"].shape),
                                                                                  "structural_absent": list(prep["structural_absent"].shape),
                                                                                  "observed_all_zero_not_structural": list(prep["observed_all_zero_not_structural"].shape)},
                   "dtype": str(prep["inputs"].dtype), "timestamps": [int(t) for t in prep["timestamps"]],
                   "structural_absent_nodes_trace": int(prep["structural_absent"][:, 1].sum()), "structural_absent_nodes_log": int(prep["structural_absent"][:, 2].sum())}]}
        break
    if ex is None:
        raise RuntimeError("no training case suitable for the prepared example")
    write_json(os.path.join(out, "prepared_example.json"), ex)

    cfg = {"config_version": CONFIG_VERSION, "input": {"tensor_shape": [46, 130], "dtype": "float32", "channel_order_sha256": schema["channel_order_sha256"],
                                                      "node_order_sha256": schema["node_order_sha256"]},
           "zero_policy": "zero is not missing; only node-modality blocks that are zero in every fit sample are structurally absent",
           "scaler": {"type": "per node-channel standardisation", "std_floor": pp.STD_FLOOR, "constant_scale": 1.0,
                      "structurally_absent_entries": "mean 0, scale 1, output forced to 0", "clipping": "none",
                      "model1_fit_set": "model1_train_period", "feature_selection": "none (all 130 channels kept; nothing selected on validation or test)"},
           "missing_modality_indicators": ["structural_absent (46x3, from the fit set)", "observed_all_zero_not_structural (N x 46 x 3, unverified possible dropout)"],
           "windowing": {"window": 6, "horizon": 1, "step_seconds": 60, "bridges_gaps": False, "boundary_protected": True},
           "fit_sets": {k: {"status": v["status"], "definition": v["definition"], "n_fit_samples": int(v["mask"].sum())} for k, v in fit_sets.items()},
           "armor_scaling_note": "ARMOR features are pre-scaled by an unknown recipe that used the full timeline; a train-only second stage cannot undo that."}
    cfg["config_sha256"] = pp.config_hash(cfg)
    write_json(os.path.join(out, "preprocessing_config_v1.json"), cfg)
    result["config_sha256"] = cfg["config_sha256"]
    write_json(os.path.join(out, "preprocessing_results.json"), result)
    return result, scalers
