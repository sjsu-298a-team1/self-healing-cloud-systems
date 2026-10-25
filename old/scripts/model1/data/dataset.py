"""
Model 1 Phase 1: data loading + windowing pipeline.

Implements exactly the locked protocol in configs/model1/protocol_config.json --
no semantics decided here, only mechanics. Does not train any model and does not
compute or inspect any evaluation metric against real predictions.

Locked parameters consumed (never redefined in this file):
- 55 features:            configs/model1/features.json
- train/val/test splits:  data/model1/manifests/{train,val,test}_cases.json
- normalization:          configs/model1/scaler.json (frozen train-only fit)
- window length:          30 steps (30s at 1 Hz)
- train stride:           5 steps
- eval stride:            1 step
- training region:        t < inject_time (known-normal region) only
- eval region:             full case (both pre- and post-injection)
- missing-value policy:   raw NaN in a locked feature is replaced with that
                           feature's TRAINING-ONLY committed scaler mean
                           BEFORE scaling (see impute_missing_with_training_mean
                           / apply_scaler below), so it becomes exactly 0.0 in
                           standardized space. No forward-fill, backward-fill,
                           interpolation, dropped cases, dropped windows, or
                           scaler refit. Discovered necessary during the first
                           real training attempt (baseline_seed42_h64_z32),
                           which diverged to NaN because raw missing cells
                           propagated through scaling into the network -- this
                           is a preprocessing correction, not a tuning choice.

Usage as a library:
    from dataset import (
        load_features, load_scaler, load_manifest,
        build_train_windows, build_eval_windows,
    )
"""
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_CONFIGS_DIR = os.path.join(REPO_ROOT, "configs", "model1")
DEFAULT_MANIFESTS_DIR = os.path.join(REPO_ROOT, "data", "model1", "manifests")

WINDOW_LENGTH = 30
TRAIN_STRIDE = 5
EVAL_STRIDE = 1


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_features(configs_dir=DEFAULT_CONFIGS_DIR):
    features = load_json(os.path.join(configs_dir, "features.json"))["features"]
    assert len(features) == 55, f"expected 55 locked features, got {len(features)}"
    assert "time" not in features
    return features


def load_scaler(configs_dir=DEFAULT_CONFIGS_DIR):
    return load_json(os.path.join(configs_dir, "scaler.json"))


def load_manifest(split, manifests_dir=DEFAULT_MANIFESTS_DIR):
    assert split in ("train", "val", "test")
    return load_json(os.path.join(manifests_dir, f"{split}_cases.json"))["case_ids"]


def count_missing_cells(data_root, case_ids, features, region="full"):
    """Structural inspection only -- counts raw NaN cells (before imputation)
    in the locked feature columns for the given cases. Does not compute or
    imply any anomaly score, threshold, or model-performance metric; safe to
    call on the test split for this purpose (region counting only).

    region: "full" (entire recorded case) or "pre_fault" (time < inject_time
    rows only, matching what training/model-selection windows actually use).
    Returns (total_missing_cells, per_case_dict).
    """
    assert region in ("full", "pre_fault")
    total = 0
    per_case = {}
    for cid in case_ids:
        df, inject_time = load_case_df(data_root, cid)
        if region == "pre_fault":
            df = df[df["time"] < inject_time]
        n_missing = int(df[features].isna().sum().sum())
        if n_missing:
            per_case[cid] = n_missing
        total += n_missing
    return total, per_case


def load_case_df(data_root, case_id):
    combo, run_id = case_id.split("/")
    path = os.path.join(data_root, combo, run_id, "simple_data.csv")
    inject_path = os.path.join(data_root, combo, run_id, "inject_time.txt")
    df = pd.read_csv(path)
    with open(inject_path) as f:
        inject_time = int(f.read().strip())
    return df, inject_time


def impute_missing_with_training_mean(x, features, scaler):
    """Missing-value policy (discovered necessary during the first real
    training attempt -- baseline_seed42_h64_z32 diverged to NaN because raw
    missing telemetry cells propagated through scaling into the network):

    Replace any raw NaN in x with that column's TRAINING-ONLY committed scaler
    mean (scaler['mean'][feature], from configs/model1/scaler.json -- fit once
    on train-split pre-fault rows, never refit). No forward-fill, backward-fill,
    or neighbor interpolation of any kind -- purely a constant per-feature
    substitution using an already-fixed statistic. Because scaling subtracts
    this same mean, an imputed value always becomes exactly 0.0 in standardized
    space.

    x: (n_rows, n_features) raw array, column order == features.
    Returns (imputed_x, n_imputed_cells).
    """
    mean = np.array([scaler["mean"][f] for f in features])
    x = x.copy()
    nan_mask = np.isnan(x)
    n_imputed = int(nan_mask.sum())
    if n_imputed:
        rows, cols = np.where(nan_mask)
        x[rows, cols] = mean[cols]
    return x, n_imputed


def apply_scaler(df, features, scaler):
    """Returns (scaled, n_imputed): scaled is an (n_rows, 55) float64 array,
    column order == features (the locked, ordered feature list) -- never a
    different order, never additional columns, using the frozen train-fit
    mean/std. Does not refit anything.

    Missing raw values are imputed with the training-only mean (see
    impute_missing_with_training_mean) BEFORE scaling. Hard postcondition:
    raises ValueError immediately if any non-finite value remains after
    imputation + scaling -- NaN/Inf must never silently reach a PyTorch tensor
    from this function again.
    """
    mean = np.array([scaler["mean"][f] for f in features])
    std = np.array([scaler["std"][f] for f in features])
    x = df[features].to_numpy(dtype=np.float64)
    x, n_imputed = impute_missing_with_training_mean(x, features, scaler)
    scaled = (x - mean) / std
    if not np.isfinite(scaled).all():
        bad_rows, bad_cols = np.where(~np.isfinite(scaled))
        bad_features = sorted({features[c] for c in bad_cols})
        raise ValueError(
            f"Non-finite value(s) remain after imputation+scaling for "
            f"feature(s) {bad_features} ({len(bad_rows)} cell(s)) -- refusing "
            f"to let NaN/Inf reach the model tensor."
        )
    return scaled, n_imputed


def _sliding_windows(x, window_length, stride):
    """x: (n_rows, n_features). Returns (n_windows, window_length, n_features)
    plus the row-index of each window's LAST row (for labeling/time lookups)."""
    n_rows = x.shape[0]
    if n_rows < window_length:
        return np.empty((0, window_length, x.shape[1])), np.empty((0,), dtype=int)
    starts = list(range(0, n_rows - window_length + 1, stride))
    windows = np.stack([x[s : s + window_length] for s in starts], axis=0)
    last_row_idx = np.array([s + window_length - 1 for s in starts], dtype=int)
    return windows, last_row_idx


def _build_known_normal_windows(data_root, case_ids, features, scaler, window_length, stride):
    """Shared implementation: sliding windows built ONLY from the known-normal
    region (time < inject_time) of the given cases, scaled with the frozen
    scaler. Never includes any row with time >= inject_time for any case,
    regardless of which case list (train or val) is passed in."""
    all_windows = []
    metadata = []
    for cid in case_ids:
        df, inject_time = load_case_df(data_root, cid)
        pre = df[df["time"] < inject_time].reset_index(drop=True)
        x, n_imputed_this_case = apply_scaler(pre, features, scaler)
        windows, last_row_idx = _sliding_windows(x, window_length, stride)
        all_windows.append(windows)
        for w_i, last_idx in enumerate(last_row_idx):
            metadata.append(
                dict(
                    case_id=cid,
                    window_index=w_i,
                    start_time=int(pre["time"].iloc[last_idx - window_length + 1]),
                    end_time=int(pre["time"].iloc[last_idx]),
                    # Same value repeated for every window from this case (imputation
                    # happens once on the case's raw rows, before windowing) -- dedupe
                    # by case_id, don't sum across windows, to get a true cell count.
                    n_imputed_cells_this_case=n_imputed_this_case,
                )
            )
    stacked = np.concatenate(all_windows, axis=0) if all_windows else np.empty((0, window_length, len(features)))
    return stacked, metadata


def build_train_windows(data_root, train_cases, features, scaler,
                         window_length=WINDOW_LENGTH, stride=TRAIN_STRIDE):
    """Training windows: pre-fault (time < inject_time) rows of TRAIN-split cases
    only, scaled with the frozen scaler, stride=TRAIN_STRIDE by default. Never
    touches val/test cases, never includes any row with time >= inject_time."""
    return _build_known_normal_windows(data_root, train_cases, features, scaler, window_length, stride)


def build_model_selection_validation_windows(data_root, val_cases, features, scaler,
                                              window_length=WINDOW_LENGTH, stride=EVAL_STRIDE):
    """Model-selection validation windows: pre-fault (time < inject_time) rows of
    VAL-split cases only, stride=EVAL_STRIDE (finer than the train stride) by
    default. Used ONLY for val_reconstruction_loss, early stopping, and
    best-checkpoint selection during Model 1 training -- NEVER for threshold
    selection or any labeled metric (F1, detection delay, pre-fault FPR), and
    NEVER includes any post-injection row. This is a deliberately different,
    more restrictive function from build_eval_windows() (full pre+post
    timeline), which is reserved for the later, separate threshold-selection/
    evaluation phase."""
    return _build_known_normal_windows(data_root, val_cases, features, scaler, window_length, stride)


def build_eval_windows(data_root, case_ids, features, scaler,
                        window_length=WINDOW_LENGTH, stride=EVAL_STRIDE):
    """Evaluation windows: FULL case (pre- and post-injection), scaled with the
    frozen scaler. Each window is labeled per protocol's window_label_rule: the
    post-injection evaluation region iff its LAST timestep's time >= inject_time.
    This label is NOT a confirmed active-fault ground truth (see
    docs/model1/protocol/fault_duration_investigation.md) -- it is the
    post-injection evaluation region label only."""
    all_windows = []
    metadata = []
    for cid in case_ids:
        df, inject_time = load_case_df(data_root, cid)
        x, n_imputed_this_case = apply_scaler(df, features, scaler)
        windows, last_row_idx = _sliding_windows(x, window_length, stride)
        all_windows.append(windows)
        for w_i, last_idx in enumerate(last_row_idx):
            end_time = int(df["time"].iloc[last_idx])
            metadata.append(
                dict(
                    case_id=cid,
                    window_index=w_i,
                    start_time=int(df["time"].iloc[last_idx - window_length + 1]),
                    end_time=end_time,
                    region="post_injection_evaluation_region" if end_time >= inject_time else "known_normal_region",
                    n_imputed_cells_this_case=n_imputed_this_case,
                )
            )
    stacked = np.concatenate(all_windows, axis=0) if all_windows else np.empty((0, window_length, len(features)))
    return stacked, metadata
