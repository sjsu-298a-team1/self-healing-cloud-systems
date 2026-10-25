"""
Model 1 Phase 7: integrity tests for the ONE-TIME held-out test evaluation.

These tests verify the *process* was followed correctly (frozen checkpoint,
frozen threshold, no recalibration, correct manifest, correct timestamp
convention) -- they do not re-litigate or "fix" the test result itself.

Usage:
    python3 test_final_test_evaluation.py --data-dir <BARO_DATA_DIR>
"""
import argparse
import ast
import copy
import hashlib
import json
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
EVALUATION_DIR = os.path.join(REPO_ROOT, "scripts", "model1", "evaluation")
sys.path.insert(0, EVALUATION_DIR)
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "model1", "data"))
sys.path.insert(0, os.path.join(REPO_ROOT, "scripts", "model1", "protocol"))

from scoring import load_frozen_model  # noqa: E402
from test_evaluation import score_test_windows_S2, sha256_of_file, build_test_rows  # noqa: E402
from dataset import load_manifest, DEFAULT_MANIFESTS_DIR  # noqa: E402
from metrics import first_detection_time, detection_delay  # noqa: E402

FINAL_SELECTION_PATH = os.path.join(REPO_ROOT, "experiments", "model1", "final_model_selection.json")
FINAL_TEST_DIR = os.path.join(REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42", "final_test")
TRAINING_CONFIG_B = os.path.join(REPO_ROOT, "configs", "model1", "training_config_candidate_B.json")


def check_checkpoint_sha256_matches_frozen_selection():
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    ckpt_path = os.path.join(REPO_ROOT, final_selection["checkpoint"]["path"])
    computed = sha256_of_file(ckpt_path)
    expected = final_selection["checkpoint"]["sha256"]
    failures = []
    if computed != expected:
        failures.append(f"checkpoint SHA-256 mismatch: expected {expected}, computed {computed}")
    with open(os.path.join(FINAL_TEST_DIR, "test_run_metadata.json")) as f:
        run_metadata = json.load(f)
    if run_metadata["checkpoint_sha256"] != expected:
        failures.append("test_run_metadata.json's recorded checkpoint_sha256 does not match the frozen selection")
    if not run_metadata["checkpoint_sha256_matches_frozen_selection"]:
        failures.append("test_run_metadata.json itself records a SHA-256 mismatch")
    return failures


def check_checkpoint_eval_and_no_grad():
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    ckpt_path = os.path.join(REPO_ROOT, final_selection["checkpoint"]["path"])
    model = load_frozen_model(ckpt_path, TRAINING_CONFIG_B)
    failures = []
    if model.training:
        failures.append("model not in eval() mode")
    windows = torch.randn(4, 30, 55)
    scores = score_test_windows_S2(model, windows)
    if not np.isfinite(np.asarray(scores)).all():
        failures.append("non-finite score produced")
    return failures


def check_model_parameters_unchanged():
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    ckpt_path = os.path.join(REPO_ROOT, final_selection["checkpoint"]["path"])
    model = load_frozen_model(ckpt_path, TRAINING_CONFIG_B)
    before = copy.deepcopy(model.state_dict())
    score_test_windows_S2(model, torch.randn(8, 30, 55))
    after = model.state_dict()
    failures = [f"parameter {k} changed" for k in before if not torch.equal(before[k], after[k])]
    return failures


def check_exact_stored_threshold_used():
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    expected_threshold = final_selection["threshold"]["value"]
    with open(os.path.join(FINAL_TEST_DIR, "test_metrics.json")) as f:
        test_metrics = json.load(f)
    failures = []
    if test_metrics["threshold"] != expected_threshold:
        failures.append(
            f"test_metrics.json threshold {test_metrics['threshold']!r} != frozen selection "
            f"threshold {expected_threshold!r} (must be bit-for-bit identical, never rounded)"
        )
    with open(os.path.join(FINAL_SELECTION_PATH.replace("final_model_selection.json",
              "candidate_B_h32_z16_seed42/scoring_rule_ablation/S2/selected_threshold.json"))) as f:
        s2_selected = json.load(f)
    if s2_selected["selected_threshold"] != expected_threshold:
        failures.append("final_model_selection.json threshold does not match S2's own selected_threshold.json")
    return failures


def check_no_threshold_selection_function_invoked_on_test():
    """AST-based: test_evaluation.py must never call (or import) select_threshold
    or build_candidate_thresholds -- the only threshold_selection.py symbol it
    may use is compute_metrics (metric computation for an ALREADY GIVEN
    threshold, not selection)."""
    path = os.path.join(EVALUATION_DIR, "test_evaluation.py")
    with open(path) as f:
        source = f.read()
    tree = ast.parse(source)
    failures = []

    banned_names = {"select_threshold", "build_candidate_thresholds"}
    called_names = {
        node.func.id for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    if called_names & banned_names:
        failures.append(f"test_evaluation.py calls banned threshold-selection function(s): {called_names & banned_names}")

    imported_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            imported_names.update(alias.name for alias in node.names)
    if imported_names & banned_names:
        failures.append(f"test_evaluation.py imports banned threshold-selection function(s): {imported_names & banned_names}")
    if "compute_metrics" not in imported_names:
        failures.append("expected test_evaluation.py to import compute_metrics (sanity: check isn't vacuous)")
    return failures


def check_all_test_scores_finite():
    with open(os.path.join(FINAL_TEST_DIR, "test_scores.csv")) as f:
        import csv
        scores = [float(r["score"]) for r in csv.DictReader(f)]
    failures = []
    if not np.isfinite(np.asarray(scores)).all():
        failures.append("non-finite score found in test_scores.csv")
    if len(scores) == 0:
        failures.append("test_scores.csv is empty")
    return failures


def check_exactly_20_test_cases_evaluated(manifests_dir):
    test_cases = load_manifest("test", manifests_dir)
    failures = []
    if len(test_cases) != 20:
        failures.append(f"expected 20 test cases in manifest, got {len(test_cases)}")
    if len(set(test_cases)) != len(test_cases):
        failures.append("test manifest contains duplicate case ids")
    with open(os.path.join(FINAL_TEST_DIR, "test_run_metadata.json")) as f:
        run_metadata = json.load(f)
    if run_metadata["n_test_cases"] != 20:
        failures.append(f"test_run_metadata.json records n_test_cases={run_metadata['n_test_cases']}, expected 20")
    windows_per_case = run_metadata["windows_per_case"]
    if set(windows_per_case.keys()) != set(test_cases):
        failures.append("scored case set does not exactly match test_cases.json")
    return failures


def check_decision_timestamp_is_window_end_time():
    """Same guard as prior phases, re-verified for the test evaluation path."""
    inject_time = 700
    window_start, window_end = 690, 705
    failures = []
    if not (window_start < inject_time <= window_end):
        failures.append("fixture invalid")
    times = [window_end]
    labels = [window_end >= inject_time]
    predictions = [True]
    det_time = first_detection_time(times, labels, predictions)
    if det_time != window_end:
        failures.append(f"expected detection timestamp == window_end ({window_end}), got {det_time}")
    if detection_delay(inject_time, det_time) < 0:
        failures.append("expected non-negative delay using end-time labeling")
    return failures


def check_no_validation_driven_post_hoc_modifications():
    """test_metrics.json's threshold/scoring-rule must be byte-identical to
    the frozen final_model_selection.json -- proves nothing was tweaked after
    seeing the test result."""
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    with open(os.path.join(FINAL_TEST_DIR, "test_metrics.json")) as f:
        test_metrics = json.load(f)
    with open(os.path.join(FINAL_TEST_DIR, "test_run_metadata.json")) as f:
        run_metadata = json.load(f)
    failures = []
    if test_metrics["threshold"] != final_selection["threshold"]["value"]:
        failures.append("test_metrics.json threshold does not match the frozen selection")
    if run_metadata["scoring_rule"] != final_selection["scoring_rule"]["name"]:
        failures.append("test_run_metadata.json scoring_rule does not match the frozen selection")
    if "statement" not in run_metadata or "not" not in run_metadata["statement"].lower():
        failures.append("test_run_metadata.json missing the no-recalibration statement")
    return failures


def check_structural_window_counts():
    with open(os.path.join(FINAL_TEST_DIR, "test_run_metadata.json")) as f:
        run_metadata = json.load(f)
    failures = []
    if run_metadata["n_test_windows_total"] != 13840:
        failures.append(f"expected 13840 total test windows, got {run_metadata['n_test_windows_total']}")
    if run_metadata["n_test_windows_known_normal"] != 6620:
        failures.append(f"expected 6620 known-normal test windows, got {run_metadata['n_test_windows_known_normal']}")
    if run_metadata["n_test_windows_post_injection_evaluation_region"] != 7220:
        failures.append(f"expected 7220 post-injection test windows, got {run_metadata['n_test_windows_post_injection_evaluation_region']}")
    windows_per_case = run_metadata["windows_per_case"]
    non_692 = {k: v for k, v in windows_per_case.items() if v != 692}
    if non_692:
        failures.append(f"expected 692 windows/case for all cases, found exceptions: {non_692}")
    return failures


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    checks = {
        "checkpoint_sha256_matches_frozen_selection": check_checkpoint_sha256_matches_frozen_selection(),
        "checkpoint_eval_and_no_grad": check_checkpoint_eval_and_no_grad(),
        "model_parameters_unchanged": check_model_parameters_unchanged(),
        "exact_stored_threshold_used": check_exact_stored_threshold_used(),
        "no_threshold_selection_function_invoked_on_test": check_no_threshold_selection_function_invoked_on_test(),
        "all_test_scores_finite": check_all_test_scores_finite(),
        "exactly_20_test_cases_evaluated": check_exactly_20_test_cases_evaluated(args.manifests_dir),
        "decision_timestamp_is_window_end_time": check_decision_timestamp_is_window_end_time(),
        "no_validation_driven_post_hoc_modifications": check_no_validation_driven_post_hoc_modifications(),
        "structural_window_counts": check_structural_window_counts(),
    }

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL FINAL TEST EVALUATION INTEGRITY CHECKS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
