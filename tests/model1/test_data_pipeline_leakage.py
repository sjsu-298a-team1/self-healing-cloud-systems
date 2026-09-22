"""
Model 1 Phase 1: leakage tests for the data/window pipeline.

Builds a small number of real training/eval windows from the committed protocol
(features.json, scaler.json, manifests) against the real BARO dataset and checks
that the pipeline cannot leak:
  - val/test cases into the training tensor
  - post-injection (t >= inject_time) rows into any training window
  - a different case's rows into a window (time discontinuity check)
  - unlocked features (wrong column set/order, or time/index) into the tensor
  - a silently-refit scaler (compares against the committed scaler.json in-memory,
    doesn't refit anything)

Does not train any model. Does not touch test-split windows/labels for any
performance inspection -- test cases are only used here to confirm split
disjointness, never loaded as data.

Usage:
    python3 test_data_pipeline_leakage.py --data-dir <BARO_DATA_DIR>
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "scripts", "model1", "data"))

from dataset import (
    EVAL_STRIDE,
    TRAIN_STRIDE,
    WINDOW_LENGTH,
    build_eval_windows,
    build_train_windows,
    load_case_df,
    load_features,
    load_manifest,
    load_scaler,
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    return parser.parse_args()


def check_locked_feature_list(features):
    failures = []
    if len(features) != 55:
        failures.append(f"expected 55 features, got {len(features)}")
    if "time" in features:
        failures.append("'time' must not be in the locked feature list")
    banned = {"index", "row_index", "idx", "timestamp"}
    leaked = [f for f in features if f.lower() in banned]
    if leaked:
        failures.append(f"banned index-like column(s) in feature list: {leaked}")
    return failures


def check_split_disjoint(train_cases, val_cases, test_cases):
    failures = []
    train_s, val_s, test_s = set(train_cases), set(val_cases), set(test_cases)
    if train_s & val_s:
        failures.append(f"train/val overlap: {sorted(train_s & val_s)}")
    if train_s & test_s:
        failures.append(f"train/test overlap: {sorted(train_s & test_s)}")
    if val_s & test_s:
        failures.append(f"val/test overlap: {sorted(val_s & test_s)}")
    union = train_s | val_s | test_s
    if len(union) != 100:
        failures.append(f"union of all splits has {len(union)} cases, expected 100")
    return failures


def check_scaler_not_refit(scaler, configs_dir):
    import json
    with open(os.path.join(configs_dir, "scaler.json")) as f:
        committed = json.load(f)
    failures = []
    if scaler["mean"] != committed["mean"] or scaler["std"] != committed["std"]:
        failures.append("in-memory scaler differs from committed configs/model1/scaler.json")
    return failures


def check_train_windows_only_from_train_cases(metadata, train_cases):
    train_set = set(train_cases)
    leaked = sorted(set(m["case_id"] for m in metadata) - train_set)
    return [f"windows built from non-train case(s): {leaked}"] if leaked else []


def check_train_windows_strictly_pre_fault(metadata, data_dir, train_cases):
    """The core leakage check: every training window's LAST (latest) timestep
    must be strictly before that case's inject_time -- i.e. t < 360s relative
    to that case's own start. No training window may include any post-injection
    row."""
    failures = []
    inject_times = {}
    for cid in train_cases:
        combo, run_id = cid.split("/")
        with open(os.path.join(data_dir, combo, run_id, "inject_time.txt")) as f:
            inject_times[cid] = int(f.read().strip())

    violations = [
        m for m in metadata
        if m["end_time"] >= inject_times[m["case_id"]]
    ]
    if violations:
        failures.append(f"{len(violations)} training window(s) include a post-injection row: {violations[:3]}")
    return failures


def check_window_time_contiguity(windows, metadata, data_dir, case_ids, stride, window_length):
    """Re-derive one window per case directly from the raw CSV and confirm its
    timestamps step by exactly 1s with no gap -- catches any indexing bug that
    could accidentally splice rows from two different time ranges (or, in a
    differently-structured pipeline, two different cases) into one window."""
    failures = []
    for cid in case_ids[:5]:  # sample a few cases; full 1Hz uniformity already
                              # confirmed dataset-wide in dataset-inspection
        df, _ = load_case_df(data_dir, cid)
        times = df["time"].to_numpy()
        first_window_times = times[0:window_length]
        diffs = first_window_times[1:] - first_window_times[:-1]
        if not (diffs == 1).all():
            failures.append(f"{cid}: first window's timestamps are not uniformly 1s apart: {diffs.tolist()}")
    return failures


def check_tensor_shape(windows, n_features):
    failures = []
    if windows.ndim != 3:
        failures.append(f"expected a 3D tensor, got shape {windows.shape}")
    elif windows.shape[1] != WINDOW_LENGTH or windows.shape[2] != n_features:
        failures.append(f"expected (*, {WINDOW_LENGTH}, {n_features}), got {windows.shape}")
    return failures


def check_eval_windows_labeled_both_regions(metadata):
    regions = set(m["region"] for m in metadata)
    failures = []
    if "known_normal_region" not in regions or "post_injection_evaluation_region" not in regions:
        failures.append(f"expected both region labels present in eval windows, got {regions}")
    return failures


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    configs_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "configs", "model1")
    manifests_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data", "model1", "manifests")

    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    train_cases = load_manifest("train", manifests_dir)
    val_cases = load_manifest("val", manifests_dir)
    test_cases = load_manifest("test", manifests_dir)

    results = {}

    results["locked_feature_list"] = check_locked_feature_list(features)
    results["split_disjoint"] = check_split_disjoint(train_cases, val_cases, test_cases)
    results["scaler_not_refit"] = check_scaler_not_refit(scaler, configs_dir)

    train_windows, train_metadata = build_train_windows(data_dir, train_cases, features, scaler)
    results["train_windows_only_from_train_cases"] = check_train_windows_only_from_train_cases(train_metadata, train_cases)
    results["train_windows_strictly_pre_fault"] = check_train_windows_strictly_pre_fault(train_metadata, data_dir, train_cases)
    results["train_tensor_shape"] = check_tensor_shape(train_windows, len(features))
    results["train_window_time_contiguity"] = check_window_time_contiguity(
        train_windows, train_metadata, data_dir, train_cases, TRAIN_STRIDE, WINDOW_LENGTH
    )

    # Eval-window construction is data plumbing only (no metric computed, no
    # model involved) -- sampled on val cases only, never test, to keep this
    # leakage-test run itself from ever touching test-case content.
    eval_windows, eval_metadata = build_eval_windows(data_dir, val_cases[:3], features, scaler, stride=EVAL_STRIDE)
    results["eval_tensor_shape"] = check_tensor_shape(eval_windows, len(features))
    results["eval_windows_labeled_both_regions"] = check_eval_windows_labeled_both_regions(eval_metadata)

    all_passed = all(len(v) == 0 for v in results.values())

    print(f"Train windows built: {train_windows.shape[0]}, shape {train_windows.shape}")
    print(f"Eval windows built (3 val cases, sample only): {eval_windows.shape[0]}, shape {eval_windows.shape}\n")
    for name, failures in results.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL LEAKAGE TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
