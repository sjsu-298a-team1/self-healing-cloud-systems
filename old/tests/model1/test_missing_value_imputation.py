"""
Model 1 Phase 4A: missing-value imputation tests.

Verifies the training-mean imputation policy adopted after run
baseline_seed42_h64_z32 diverged to NaN: raw missing values in a locked
feature are replaced with that feature's TRAINING-ONLY committed scaler mean
before scaling (so they become exactly 0.0 in standardized space), with no
forward/backward-fill or interpolation, no dropped cases/windows, and no
scaler refit.

Uses real BARO data (to exercise the actual code path against the actual
known-missing cells) but never computes or inspects any anomaly
score/threshold/performance metric -- including for the test split, which is
inspected here only for structural missing-cell counts, exactly as permitted.

Usage:
    python3 test_missing_value_imputation.py --data-dir <BARO_DATA_DIR>
"""
import argparse
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "data"))

from dataset import (  # noqa: E402
    DEFAULT_CONFIGS_DIR,
    DEFAULT_MANIFESTS_DIR,
    apply_scaler,
    build_model_selection_validation_windows,
    build_train_windows,
    count_missing_cells,
    impute_missing_with_training_mean,
    load_case_df,
    load_features,
    load_manifest,
    load_scaler,
)

# Known from data/model1/dataset_inspection/missing_cells_detail.csv: these are
# the only two cases with missing values in LOCKED feature columns, and both
# are in the train split. All of their missing cells fall in the pre-fault
# region (n_missing_pre_fault == n_missing for every row in that CSV).
KNOWN_CASE_WITH_MISSING = "currencyservice_cpu/1"
KNOWN_MISSING_FEATURES = ["adservice_cpu", "cartservice_cpu", "paymentservice_cpu",
                          "productcatalogservice_cpu", "shippingservice_cpu"]


def check_missing_replaced_with_committed_mean(data_dir, configs_dir):
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    df, inject_time = load_case_df(data_dir, KNOWN_CASE_WITH_MISSING)
    pre = df[df["time"] < inject_time].reset_index(drop=True)

    raw = pre[features].to_numpy(dtype=np.float64)
    nan_positions = np.argwhere(np.isnan(raw))
    failures = []
    if len(nan_positions) == 0:
        return [f"expected known missing cells in {KNOWN_CASE_WITH_MISSING}, found none -- fixture assumption invalid"]

    imputed, n_imputed = impute_missing_with_training_mean(raw, features, scaler)
    if n_imputed != len(nan_positions):
        failures.append(f"expected {len(nan_positions)} imputed cells, function reported {n_imputed}")

    for r, c in nan_positions:
        expected_mean = scaler["mean"][features[c]]
        if imputed[r, c] != expected_mean:
            failures.append(f"cell ({r},{c}) feature={features[c]}: expected {expected_mean}, got {imputed[r, c]}")
    return failures


def check_imputed_values_become_zero_after_scaling(data_dir, configs_dir):
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    df, inject_time = load_case_df(data_dir, KNOWN_CASE_WITH_MISSING)
    pre = df[df["time"] < inject_time].reset_index(drop=True)

    raw = pre[features].to_numpy(dtype=np.float64)
    nan_positions = np.argwhere(np.isnan(raw))
    scaled, n_imputed = apply_scaler(pre, features, scaler)

    failures = []
    for r, c in nan_positions:
        if not np.isclose(scaled[r, c], 0.0, atol=1e-9):
            failures.append(f"cell ({r},{c}) feature={features[c]}: expected 0.0 after scaling, got {scaled[r, c]}")
    return failures


def check_non_missing_values_scale_unchanged(data_dir, configs_dir):
    """Non-missing cells must scale exactly as (x - mean) / std, unaffected by
    the imputation change (imputation only touches NaN cells)."""
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    df, inject_time = load_case_df(data_dir, KNOWN_CASE_WITH_MISSING)
    pre = df[df["time"] < inject_time].reset_index(drop=True)

    raw = pre[features].to_numpy(dtype=np.float64)
    mean = np.array([scaler["mean"][f] for f in features])
    std = np.array([scaler["std"][f] for f in features])
    expected_direct = (raw - mean) / std  # will be NaN at missing cells -- that's fine, we skip those

    scaled, _ = apply_scaler(pre, features, scaler)

    non_missing_mask = ~np.isnan(raw)
    failures = []
    if not np.allclose(scaled[non_missing_mask], expected_direct[non_missing_mask], rtol=1e-10, atol=1e-12):
        failures.append("non-missing cells differ from direct (x-mean)/std computation")
    return failures


def check_scaler_not_refit(data_dir, configs_dir, manifests_dir):
    scaler_path = os.path.join(configs_dir, "scaler.json")
    with open(scaler_path) as f:
        before = f.read()
    # Exercise the pipeline (which reads but must never write scaler.json)
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    train_cases = load_manifest("train", manifests_dir)[:2]
    for cid in train_cases:
        df, inject_time = load_case_df(data_dir, cid)
        apply_scaler(df[df["time"] < inject_time], features, scaler)
    with open(scaler_path) as f:
        after = f.read()
    return [] if before == after else ["configs/model1/scaler.json changed on disk after running the pipeline"]


def check_no_fill_or_interpolation_logic():
    """Static/code-inspection check: no forward-fill, backward-fill, or
    interpolation function is used anywhere in dataset.py."""
    dataset_py_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "data", "dataset.py"
    )
    with open(dataset_py_path) as f:
        source = f.read()
    banned_substrings = ["ffill", "bfill", "fillna(method", "interpolate(", ".pad(", "fillna(0"]
    failures = [f"banned fill/interpolation call found: '{s}'" for s in banned_substrings if s in source]
    return failures


def check_window_counts_unchanged(data_dir, configs_dir, manifests_dir):
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    train_cases = load_manifest("train", manifests_dir)
    val_cases = load_manifest("val", manifests_dir)

    train_windows, _ = build_train_windows(data_dir, train_cases, features, scaler)
    val_windows, _ = build_model_selection_validation_windows(data_dir, val_cases, features, scaler)

    failures = []
    if train_windows.shape != (4020, 30, 55):
        failures.append(f"expected train windows shape (4020, 30, 55), got {train_windows.shape}")
    if val_windows.shape != (6620, 30, 55):
        failures.append(f"expected val windows shape (6620, 30, 55), got {val_windows.shape}")
    if not np.isfinite(train_windows).all():
        failures.append("train window tensor contains non-finite values")
    if not np.isfinite(val_windows).all():
        failures.append("validation window tensor contains non-finite values")
    return failures, train_windows.shape, val_windows.shape


def check_manifests_and_features_unchanged(configs_dir, manifests_dir):
    features = load_features(configs_dir)
    train_cases = load_manifest("train", manifests_dir)
    val_cases = load_manifest("val", manifests_dir)
    test_cases = load_manifest("test", manifests_dir)

    failures = []
    if len(features) != 55:
        failures.append(f"expected 55 features, got {len(features)}")
    if (len(train_cases), len(val_cases), len(test_cases)) != (60, 20, 20):
        failures.append(f"expected (60,20,20) case counts, got {(len(train_cases), len(val_cases), len(test_cases))}")
    all_cases = set(train_cases) | set(val_cases) | set(test_cases)
    if len(all_cases) != 100 or len(train_cases) + len(val_cases) + len(test_cases) != 100:
        failures.append("manifests are not disjoint / do not cover exactly 100 cases")
    return failures


def report_imputed_cell_counts(data_dir, configs_dir, manifests_dir):
    features = load_features(configs_dir)
    train_cases = load_manifest("train", manifests_dir)
    val_cases = load_manifest("val", manifests_dir)
    test_cases = load_manifest("test", manifests_dir)

    # Pre-fault-only counts -- matches what training/model-selection windows
    # actually consume for train/val. Full-case counts also reported for
    # completeness (test split isn't windowed at all in this phase).
    train_pre, train_pre_detail = count_missing_cells(data_dir, train_cases, features, region="pre_fault")
    val_pre, val_pre_detail = count_missing_cells(data_dir, val_cases, features, region="pre_fault")
    test_full, test_full_detail = count_missing_cells(data_dir, test_cases, features, region="full")
    test_pre, _ = count_missing_cells(data_dir, test_cases, features, region="pre_fault")

    print("=== Imputed cell counts (structural inspection only -- no test-set metric computed) ===")
    print(f"  train split (pre-fault region, the region actually used):      {train_pre} cells  {train_pre_detail}")
    print(f"  validation split (pre-fault region, the region actually used): {val_pre} cells  {val_pre_detail}")
    print(f"  test split (pre-fault region):                                 {test_pre} cells")
    print(f"  test split (full case, not windowed in this phase):            {test_full} cells  {test_full_detail}")
    return dict(train_pre=train_pre, val_pre=val_pre, test_pre=test_pre, test_full=test_full)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    args = parser.parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))

    imputed_counts = report_imputed_cell_counts(data_dir, args.configs_dir, args.manifests_dir)
    print()

    window_count_failures, train_shape, val_shape = check_window_counts_unchanged(
        data_dir, args.configs_dir, args.manifests_dir
    )
    print(f"Train tensor shape: {train_shape}")
    print(f"Validation tensor shape: {val_shape}\n")

    checks = {
        "missing_replaced_with_committed_mean": check_missing_replaced_with_committed_mean(data_dir, args.configs_dir),
        "imputed_values_become_zero_after_scaling": check_imputed_values_become_zero_after_scaling(data_dir, args.configs_dir),
        "non_missing_values_scale_unchanged": check_non_missing_values_scale_unchanged(data_dir, args.configs_dir),
        "scaler_not_refit": check_scaler_not_refit(data_dir, args.configs_dir, args.manifests_dir),
        "no_fill_or_interpolation_logic": check_no_fill_or_interpolation_logic(),
        "window_counts_and_finiteness_unchanged": window_count_failures,
        "manifests_and_features_unchanged": check_manifests_and_features_unchanged(args.configs_dir, args.manifests_dir),
    }

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL MISSING-VALUE IMPUTATION TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
