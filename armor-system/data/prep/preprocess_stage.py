"""STEP 5 stage: fit train-only preprocessing on the approved official train period (and on the proposed
Model 1 alternative train period), then record configuration and results."""
import os

import numpy as np

from . import paths, preprocess as pp
from .common import iso, read_json, write_csv, write_json
from .loader import MODALITIES

CONFIG_VERSION = "1.0"


def periods(manifest):
    names = [s for s in manifest["case_ranges"]]
    b = [x["boundary_ts"] for x in manifest["sample_time_boundaries"]]
    lo = [-10 ** 18] + b
    hi = b + [10 ** 18]
    return {n: (lo[i], hi[i]) for i, n in enumerate(names)}


def _summ(X, mask_entry=None):
    v = X[:, mask_entry] if mask_entry is not None else X.reshape(-1)
    return {"mean": float(v.mean()), "std": float(v.std()), "p01": float(np.percentile(v, 1)), "p99": float(np.percentile(v, 99)),
            "zero_fraction": float((v == 0).mean())}


def run(labels, ts, X, is_test, splits_result):
    out = paths.art("preprocessing")
    schema = read_json(paths.art("inspection", "schema.json"))
    groups, nodes, channels = labels["groups"], labels["nodes"], labels["channels"]
    issues = pp.validate_schema(X, ts, schema) + pp.validate_order(nodes, channels, schema)
    ad_split = splits_result["ad_split"]
    fit_sets = {
        "official_train_period": {"status": "approved_reproduction", "mask": ts <= ad_split,
                                  "definition": "samples with timestamp <= the ARMOR AD split (2022-05-06T16:00:00Z): contains all 126 official train cases and no held-out case"},
    }
    alt = splits_result["alternative"]
    if alt:
        lo, hi = periods(alt)["train"]
        fit_sets["model1_alternative_train_period"] = {"status": "proposed_pending_approval", "mask": (ts >= lo) & (ts < hi),
                                                       "definition": f"samples before the alternative train|validation boundary {iso(hi)}"}
    missing = pp.inspect_missing(X, groups)
    result = {"config_version": CONFIG_VERSION, "schema_issues": issues, "missing_inspection": missing, "fits": {}}
    mask_rows, ba_rows = [], []
    scalers = {}
    for name, fs in fit_sets.items():
        sc = pp.fit_scaler(X, fs["mask"], groups)
        scalers[name] = sc
        np.savez_compressed(os.path.join(out, f"scaler_{name}_v1.npz"), mean=sc["mean"], scale=sc["scale"], constant=sc["constant"],
                            absent_block=sc["absent_block"], absent_entry=sc["absent_entry"])
        Xt, ind = pp.transform(X, sc, groups)
        fit = fs["mask"]
        res = {"status": fs["status"], "definition": fs["definition"], "n_fit_samples": int(fit.sum()),
               "fit_first": iso(ts[fit].min()), "fit_last": iso(ts[fit].max()),
               "structural_absent_blocks": {m: int(sc["absent_block"][:, j].sum()) for j, m in enumerate(MODALITIES)},
               "constant_entries_scale_set_to_1": int(sc["constant"].sum()),
               "observed_all_zero_not_structural_node_modality_rows": int(ind["observed_all_zero_not_structural"].sum()),
               "transformed_finite": bool(np.isfinite(Xt).all()), "scaler_file": f"scaler_{name}_v1.npz"}
        # before/after per modality: fit period vs everything after it
        for j, m in enumerate(MODALITIES):
            idx = np.zeros(X.shape[2], bool)
            idx[groups[m]] = True
            live = ~sc["absent_entry"][:, idx]                        # (46, nm) non-absent entries
            for per, mask in (("fit", fit), ("after_fit", ~fit & (ts > ts[fit].max()))):
                if not mask.any():
                    continue
                for tag, arr in (("before", X), ("after", Xt)):
                    sub = arr[mask][:, :, idx][:, live]
                    ba_rows.append({"fit_set": name, "modality": m, "period": per, "stage": tag, "n_samples": int(mask.sum()), **_summ(sub[None, :] if sub.ndim == 1 else sub.reshape(1, -1))})
        for i, n in enumerate(nodes):
            for j, m in enumerate(MODALITIES):
                mask_rows.append({"fit_set": name, "node": n, "modality": m, "structurally_absent": int(sc["absent_block"][i, j]),
                                  "channels": len(groups[m])})
        result["fits"][name] = res
    write_csv(os.path.join(out, "before_after_summary.csv"), ba_rows)
    write_csv(os.path.join(out, "structural_masks.csv"), mask_rows)

    # windows: ARMOR needs 7 consecutive 60 s samples (6 inputs + next-step target)
    win_rows = []
    for mname, key in (("official_armor_v1", "official"), ("model1_alternative_v1", "alternative")):
        man = splits_result[key]
        if not man:
            continue
        for split, (lo, hi) in periods(man).items():
            pos = np.nonzero((ts >= lo) & (ts < hi))[0]
            allw = pp.make_windows(ts, pos, window=6, horizon=1)
            kept, dropped = pp.protect_boundaries(ts, allw, lo, hi, window=6, horizon=1)
            win_rows.append({"manifest": mname, "split": split, "samples": int(len(pos)), "windows_7_step": int(len(allw)),
                             "kept_inside_period": int(len(kept)), "dropped_crossing_boundary": int(len(dropped))})
    write_csv(os.path.join(out, "window_counts.csv"), win_rows)
    result["windows"] = win_rows
    cfg = {"config_version": CONFIG_VERSION, "input": {"tensor_shape": [46, 130], "dtype": "float32", "channel_order_sha256": schema["channel_order_sha256"],
                                                      "node_order_sha256": schema["node_order_sha256"]},
           "zero_policy": "zero is not missing; only node-modality blocks that are zero in every fit sample are structurally absent",
           "scaler": {"type": "per node-channel standardisation", "std_floor": pp.STD_FLOOR, "constant_scale": 1.0,
                      "structurally_absent_entries": "mean 0, scale 1, output forced to 0", "clipping": "none"},
           "missing_modality_indicators": ["structural_absent (46x3, from fit set)", "observed_all_zero_not_structural (N x 46 x 3, unverified possible dropout)"],
           "windowing": {"window": 6, "horizon": 1, "step_seconds": 60, "bridges_gaps": False, "boundary_protected": True},
           "fit_sets": {k: {"status": v["status"], "definition": v["definition"], "n_fit_samples": int(v["mask"].sum())} for k, v in fit_sets.items()},
           "armor_scaling_note": "ARMOR features are pre-scaled by an unknown recipe that used the full timeline; a train-only second stage cannot undo that."}
    cfg["config_sha256"] = pp.config_hash(cfg)
    write_json(os.path.join(out, "preprocessing_config_v1.json"), cfg)
    result["config_sha256"] = cfg["config_sha256"]
    write_json(os.path.join(out, "preprocessing_results.json"), result)
    return result, scalers
