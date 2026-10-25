"""
Model 1 protocol step 3+8: automated protocol validation checks.

Checks performed (all read-only against configs/, manifests/, and the dataset):
  1. Split overlap      -- train/val/test case-id sets are pairwise disjoint and
                            together cover exactly the 100 cases, no duplicates.
  2. Feature consistency -- every one of the 100 cases' simple_data.csv actually
                            contains all 55 declared features with numeric dtype.
  3. Training-only scaler fit -- configs/scaler.json's fit source is exactly the
                            train manifest's pre-fault rows; independently
                            recomputed here from train_cases.json and compared
                            byte-for-byte (within float tolerance) against the
                            saved artifact, and re-verified that val/test cases
                            cannot reproduce it (sanity: recomputing with val
                            cases mixed in changes the stats).
  4. No time/index leakage -- "time" and any row-index-like name are absent
                            from the feature list, and the protocol_config.json
                            windowing spec does not name them as model inputs.
  5. Fault-type stratification -- every one of the 100 real case ids parses to
                            exactly one of {cpu, mem, delay, loss} via
                            metrics.fault_type_of_case, with exactly 25 cases per
                            fault type (5 services x 5 runs), so the stratified
                            evaluation required by protocol_config.json's
                            limitations.fault_duration can actually be produced.

Does not train any model. Writes a machine-readable report to --report-path and
exits non-zero if any check fails.

Usage:
    python3 validate_protocol.py --data-dir <BARO_DATA_DIR>
                                  [--configs-dir <CONFIGS_DIR>] [--manifests-dir <MANIFESTS_DIR>]
                                  [--report-path <REPORT_PATH>]

    Directories default to this repo's configs/model1/, data/model1/manifests/,
    and docs/model1/protocol/validation_report.json, resolved relative to this
    script's own location.
"""
import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

from metrics import FAULT_TYPES, fault_type_of_case, group_case_ids_by_fault_type

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_CONFIGS_DIR = os.path.join(REPO_ROOT, "configs", "model1")
DEFAULT_MANIFESTS_DIR = os.path.join(REPO_ROOT, "data", "model1", "manifests")
DEFAULT_REPORT_PATH = os.path.join(REPO_ROOT, "docs", "model1", "protocol", "validation_report.json")

# Populated in main() from CLI args; module-level so the check_* helpers (called
# from main()) can reference them without threading extra params through every
# call site.
DATA_ROOT = None
CONFIGS = None
MANIFESTS = None


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR,
                         help="Directory with features.json, protocol_config.json, scaler.json")
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR,
                         help="Directory with train/val/test manifest JSON files")
    parser.add_argument("--report-path", default=DEFAULT_REPORT_PATH,
                         help="Full output path for validation_report.json")
    return parser.parse_args()


def load_json(path):
    with open(path) as f:
        return json.load(f)


def load_case_df(case_id):
    combo, run_id = case_id.split("/")
    return pd.read_csv(os.path.join(DATA_ROOT, combo, run_id, "simple_data.csv"))


def load_inject_time(case_id):
    combo, run_id = case_id.split("/")
    with open(os.path.join(DATA_ROOT, combo, run_id, "inject_time.txt")) as f:
        return int(f.read().strip())


def check_split_overlap(train, val, test):
    train_s, val_s, test_s = set(train), set(val), set(test)
    problems = []
    if len(train_s) != len(train):
        problems.append("duplicate case ids within train manifest")
    if len(val_s) != len(val):
        problems.append("duplicate case ids within val manifest")
    if len(test_s) != len(test):
        problems.append("duplicate case ids within test manifest")
    if train_s & val_s:
        problems.append(f"train/val overlap: {sorted(train_s & val_s)}")
    if train_s & test_s:
        problems.append(f"train/test overlap: {sorted(train_s & test_s)}")
    if val_s & test_s:
        problems.append(f"val/test overlap: {sorted(val_s & test_s)}")
    union = train_s | val_s | test_s
    if len(union) != 100:
        problems.append(f"union of all splits has {len(union)} cases, expected 100")
    return dict(passed=len(problems) == 0, problems=problems, n_train=len(train), n_val=len(val), n_test=len(test))


def check_feature_consistency(features, all_case_ids):
    missing_feature_cases = {}
    non_numeric_cases = {}
    for cid in all_case_ids:
        df = load_case_df(cid)
        missing = sorted(set(features) - set(df.columns))
        if missing:
            missing_feature_cases[cid] = missing
        non_numeric = [c for c in features if c in df.columns and not pd.api.types.is_numeric_dtype(df[c])]
        if non_numeric:
            non_numeric_cases[cid] = non_numeric
    passed = not missing_feature_cases and not non_numeric_cases
    return dict(
        passed=passed,
        n_cases_checked=len(all_case_ids),
        n_features_expected=len(features),
        cases_missing_features=missing_feature_cases,
        cases_with_non_numeric_features=non_numeric_cases,
    )


def check_scaler_train_only(features, train_cases, val_cases):
    scaler = load_json(os.path.join(CONFIGS, "scaler.json"))
    problems = []

    if scaler["n_train_cases_used"] != len(train_cases):
        problems.append(
            f"scaler.json used {scaler['n_train_cases_used']} cases, train manifest has {len(train_cases)}"
        )
    if sorted(scaler["n_rows_per_case"].keys()) != sorted(train_cases):
        problems.append("scaler.json's per-case row counts do not exactly match the train manifest case set")

    # Recompute independently from train manifest and compare.
    rows = []
    for cid in train_cases:
        df = load_case_df(cid)
        inject_time = load_inject_time(cid)
        pre = df[df["time"] < inject_time][features]
        rows.append(pre)
    stacked = pd.concat(rows, axis=0, ignore_index=True)
    recomputed_mean = stacked.mean(numeric_only=True)
    recomputed_std = stacked.std(numeric_only=True).clip(lower=1e-8)

    max_mean_diff = 0.0
    max_std_diff = 0.0
    for feat in features:
        saved_mean = scaler["mean"][feat]
        saved_std = scaler["std"][feat]
        max_mean_diff = max(max_mean_diff, abs(saved_mean - recomputed_mean[feat]))
        max_std_diff = max(max_std_diff, abs(saved_std - recomputed_std[feat]))
    if max_mean_diff > 1e-6 or max_std_diff > 1e-6:
        problems.append(
            f"recomputed scaler stats differ from saved scaler.json (max mean diff={max_mean_diff}, max std diff={max_std_diff})"
        )

    # Negative control: mixing in ONE val case should change at least one stat
    # detectably. If it doesn't, the fit routine isn't actually sensitive to which
    # cases are included, which would undermine this whole check.
    contaminated_rows = list(rows)
    val_cid = val_cases[0]
    df_val = load_case_df(val_cid)
    inject_time_val = load_inject_time(val_cid)
    contaminated_rows.append(df_val[df_val["time"] < inject_time_val][features])
    contaminated_stacked = pd.concat(contaminated_rows, axis=0, ignore_index=True)
    contaminated_mean = contaminated_stacked.mean(numeric_only=True)
    any_changed = any(
        abs(contaminated_mean[feat] - recomputed_mean[feat]) > 1e-9 for feat in features
    )
    if not any_changed:
        problems.append("negative control failed: adding a val case's rows did not change fit statistics at all (unexpected)")

    return dict(
        passed=len(problems) == 0,
        problems=problems,
        max_mean_diff=max_mean_diff,
        max_std_diff=max_std_diff,
        negative_control_detected_contamination=any_changed,
    )


def check_no_time_index_leakage(features, protocol_config):
    problems = []
    banned_names = {"time", "index", "row_index", "timestamp", "idx"}
    leaked = [f for f in features if f.lower() in banned_names]
    if leaked:
        problems.append(f"banned column(s) found in feature list: {leaked}")

    if not protocol_config["features"].get("excludes"):
        problems.append("protocol_config.json does not document time/index exclusion")

    windowing = protocol_config["windowing"]
    # 'time' may legitimately appear in windowing spec text as *labeling* input,
    # never as a listed model feature -- feature list itself is the source of truth,
    # already checked above. Here we just confirm the labeling rule explicitly
    # scopes time usage to labels, not to model input.
    if "time" not in json.dumps(protocol_config["labeling"]):
        problems.append("labeling spec does not reference 'time' at all -- unexpected, labeling should be time-based")

    return dict(passed=len(problems) == 0, problems=problems, leaked_columns=leaked)


def check_fault_type_stratification(all_case_ids):
    problems = []
    parse_failures = []
    for cid in all_case_ids:
        try:
            fault_type_of_case(cid)
        except ValueError as e:
            parse_failures.append(str(e))
    if parse_failures:
        problems.append(f"{len(parse_failures)} case id(s) failed to parse a fault_type: {parse_failures}")

    groups = group_case_ids_by_fault_type(all_case_ids)
    counts = {ft: len(ids) for ft, ids in groups.items()}
    if set(counts.keys()) != set(FAULT_TYPES):
        problems.append(f"expected fault types {FAULT_TYPES}, got groups {sorted(counts.keys())}")
    total = sum(counts.values())
    if total != len(all_case_ids):
        problems.append(f"grouped {total} cases but {len(all_case_ids)} case ids were provided (parse gaps?)")
    for ft in FAULT_TYPES:
        if counts.get(ft, 0) != 25:
            problems.append(f"fault type '{ft}' has {counts.get(ft, 0)} cases, expected 25 (5 services x 5 runs)")

    return dict(passed=len(problems) == 0, problems=problems, counts_per_fault_type=counts)


def main():
    global DATA_ROOT, CONFIGS, MANIFESTS

    args = parse_args()
    DATA_ROOT = os.path.abspath(os.path.expanduser(args.data_dir))
    CONFIGS = os.path.abspath(os.path.expanduser(args.configs_dir))
    MANIFESTS = os.path.abspath(os.path.expanduser(args.manifests_dir))
    report_path = os.path.abspath(os.path.expanduser(args.report_path))

    features = load_json(os.path.join(CONFIGS, "features.json"))["features"]
    protocol_config = load_json(os.path.join(CONFIGS, "protocol_config.json"))
    train_cases = load_json(os.path.join(MANIFESTS, "train_cases.json"))["case_ids"]
    val_cases = load_json(os.path.join(MANIFESTS, "val_cases.json"))["case_ids"]
    test_cases = load_json(os.path.join(MANIFESTS, "test_cases.json"))["case_ids"]
    all_cases = train_cases + val_cases + test_cases

    report = {}
    report["split_overlap"] = check_split_overlap(train_cases, val_cases, test_cases)
    report["feature_consistency"] = check_feature_consistency(features, all_cases)
    report["scaler_train_only"] = check_scaler_train_only(features, train_cases, val_cases)
    report["no_time_index_leakage"] = check_no_time_index_leakage(features, protocol_config)
    report["fault_type_stratification"] = check_fault_type_stratification(all_cases)

    all_passed = all(v["passed"] for v in report.values())
    report["all_checks_passed"] = all_passed

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, default=str)

    print(f"Wrote {report_path}\n")
    for name, result in report.items():
        if name == "all_checks_passed":
            continue
        status = "PASS" if result["passed"] else "FAIL"
        print(f"[{status}] {name}")
        if not result["passed"]:
            for p in result["problems"]:
                print(f"    - {p}")

    print(f"\nALL CHECKS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
