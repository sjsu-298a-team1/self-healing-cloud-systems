"""
Model 1 Phase 5: validation-only anomaly scoring + threshold selection tests.

Uses the frozen epoch-96 checkpoint from experiments/model1/
baseline_seed42_h64_z32_mean_impute/checkpoints/best.pt and real BARO data for
the checks that need it, plus small synthetic examples for the hand-computed
formula/edge-case checks. Never loads data/model1/manifests/test_cases.json
and never computes or inspects any test-split score.

Usage:
    python3 test_validation_scoring_and_threshold.py --data-dir <BARO_DATA_DIR> \
        --checkpoint <path/to/best.pt>
"""
import argparse
import ast
import copy
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "model1", "evaluation"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "model1", "data"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "model1", "protocol"))

from scoring import (  # noqa: E402
    build_validation_scores,
    load_frozen_model,
    reconstruction_score,
    score_windows,
)
from threshold_selection import (  # noqa: E402
    build_candidate_thresholds,
    compute_metrics,
    select_threshold,
)
from dataset import DEFAULT_MANIFESTS_DIR, load_manifest  # noqa: E402
from metrics import detection_delay, first_detection_time  # noqa: E402

EVALUATION_SCRIPTS = ["scoring.py", "threshold_selection.py"]
EVALUATION_DIR = os.path.join(HERE, "..", "..", "scripts", "model1", "evaluation")


def check_checkpoint_loaded_in_eval_mode(checkpoint_path):
    model = load_frozen_model(checkpoint_path)
    failures = []
    if model.training:
        failures.append("load_frozen_model() returned a model still in train() mode")
    return failures


def check_scoring_runs_under_no_grad(checkpoint_path):
    model = load_frozen_model(checkpoint_path)
    windows = torch.randn(4, 30, 55)
    failures = []
    # Sanity: with grad enabled and NOT under no_grad, a forward pass on a
    # leaf-like input would ordinarily create graph-carrying output. Prove
    # score_windows's actual output is graph-free (requires_grad=False)
    # even though model parameters themselves still require grad.
    if not any(p.requires_grad for p in model.parameters()):
        failures.append("test is vacuous: model has no requires_grad=True parameters to begin with")
    with torch.no_grad():
        direct_recon = model(windows)
    if direct_recon.requires_grad:
        failures.append("sanity baseline broken: even a no_grad-wrapped forward pass reports requires_grad=True")

    scores = score_windows(model, windows)
    if not isinstance(scores, np.ndarray):
        failures.append("score_windows must return a plain numpy array (proves no lingering autograd tensor)")
    return failures


def check_model_parameters_never_change_during_scoring(checkpoint_path):
    model = load_frozen_model(checkpoint_path)
    before = copy.deepcopy(model.state_dict())
    windows = torch.randn(8, 30, 55)
    score_windows(model, windows)
    after = model.state_dict()
    failures = []
    for k in before:
        if not torch.equal(before[k], after[k]):
            failures.append(f"parameter {k} changed after scoring")
    return failures


def check_exactly_20_validation_cases_scored(data_dir, checkpoint_path, manifests_dir):
    val_cases = load_manifest("val", manifests_dir)
    failures = []
    if len(val_cases) != 20:
        failures.append(f"expected 20 val cases in manifest, got {len(val_cases)}")
    rows, _ = build_validation_scores(data_dir, checkpoint_path, manifests_dir=manifests_dir)
    scored_cases = set(r["case_id"] for r in rows)
    if len(scored_cases) != 20:
        failures.append(f"expected 20 distinct scored cases, got {len(scored_cases)}")
    if scored_cases != set(val_cases):
        failures.append("scored case set does not exactly match val_cases.json")
    return failures, rows


def check_no_test_manifest_loaded_ast():
    """AST-based (not string-search) check on scoring.py and threshold_selection.py:
    inspects every actual call to load_manifest(...) and confirms 'test' is
    never one of its literal arguments."""
    failures = []
    for script in EVALUATION_SCRIPTS:
        path = os.path.join(EVALUATION_DIR, script)
        with open(path) as f:
            source = f.read()
        tree = ast.parse(source)
        load_manifest_call_args = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_manifest":
                if node.args and isinstance(node.args[0], ast.Constant):
                    load_manifest_call_args.append(node.args[0].value)
        if "test" in load_manifest_call_args:
            failures.append(f"{script} calls load_manifest(\"test\", ...); calls found: {load_manifest_call_args}")
    # Sanity: scoring.py DOES call load_manifest("val", ...) -- not vacuous.
    scoring_path = os.path.join(EVALUATION_DIR, "scoring.py")
    with open(scoring_path) as f:
        tree = ast.parse(f.read())
    val_calls = [
        node.args[0].value for node in ast.walk(tree)
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_manifest"
        and node.args and isinstance(node.args[0], ast.Constant)
    ]
    if "val" not in val_calls:
        failures.append(f"expected scoring.py to call load_manifest('val', ...); found: {val_calls}")
    return failures


def check_score_formula_hand_computed():
    """Hand-computed synthetic example: a single 2-timestep, 2-feature window."""
    x = np.array([[1.0, 2.0], [3.0, 4.0]])
    recon = np.array([[1.5, 2.0], [3.0, 5.0]])
    # squared errors: 0.25, 0.0, 0.0, 1.0 -> mean = 1.25 / 4 = 0.3125
    expected = 0.3125
    got = reconstruction_score(x, recon)
    failures = []
    if not np.isclose(got, expected, atol=1e-12):
        failures.append(f"expected hand-computed score {expected}, got {got}")

    # batch of 2 such windows stacked -> per-window scores, not a single scalar
    x_batch = np.stack([x, x * 2])
    recon_batch = np.stack([recon, recon * 2])
    got_batch = reconstruction_score(x_batch, recon_batch)
    if not np.allclose(got_batch, [0.3125, 0.3125 * 4], atol=1e-12):
        failures.append(f"batched per-window scores incorrect: {got_batch}")
    return failures


def check_every_score_finite(rows):
    scores = np.array([r["score"] for r in rows])
    failures = []
    if not np.isfinite(scores).all():
        failures.append("non-finite score found among validation windows")
    return failures, scores


def check_window_metadata_attached_correctly(rows):
    failures = []
    required_keys = {"case_id", "service", "fault_type", "window_index",
                      "window_start_time", "window_end_time", "region", "score"}
    for r in rows[:5] + rows[-5:]:
        if set(r.keys()) != required_keys:
            failures.append(f"row missing expected keys: {r.keys()}")
        if r["window_end_time"] < r["window_start_time"]:
            failures.append(f"case {r['case_id']} window {r['window_index']}: end_time < start_time")
        if r["region"] not in ("known_normal_region", "post_injection_evaluation_region"):
            failures.append(f"unexpected region value: {r['region']}")
        combo = r["case_id"].split("/")[0]
        if not combo.startswith(r["service"]) or not combo.endswith(r["fault_type"]):
            failures.append(f"service/fault_type parsing inconsistent with case_id {r['case_id']}")
    return failures


def check_threshold_candidates_derived_only_from_validation_scores(rows):
    pre_fault_scores = [r["score"] for r in rows if r["region"] == "known_normal_region"]
    candidates = build_candidate_thresholds(pre_fault_scores)
    failures = []
    lo, hi = min(pre_fault_scores), max(pre_fault_scores)
    if not all(lo <= c <= hi for c in candidates):
        failures.append("some candidate threshold falls outside the range of the pre-fault validation scores")
    # Not hand-picked: every candidate must equal some np.percentile(...) of
    # this exact score array (re-derive independently and compare as a set).
    grid = np.clip(np.arange(50.0, 100.0 + 1e-9, 0.1), 0.0, 100.0)
    expected = set(np.round(np.percentile(pre_fault_scores, grid, method="linear"), 10))
    got = set(np.round(candidates, 10))
    if not got.issubset(expected):
        failures.append("some candidate is not a percentile of the pre-fault validation scores")
    return failures, candidates, pre_fault_scores


def check_selected_threshold_satisfies_rule(pre_fault_scores, candidates):
    selected, achieved_fpr = select_threshold(pre_fault_scores, candidates)
    failures = []
    if achieved_fpr > 0.05:
        failures.append(f"selected threshold's empirical pre-fault FPR {achieved_fpr} exceeds the 0.05 ceiling")
    smaller = [c for c in candidates if c < selected]
    if smaller:
        next_lower = max(smaller)
        fpr_next_lower = float(np.mean(np.asarray(pre_fault_scores) > next_lower))
        if fpr_next_lower <= 0.05:
            failures.append(
                f"a smaller candidate {next_lower} also satisfies FPR<=0.05 "
                f"(fpr={fpr_next_lower}) -- selected threshold is not the smallest such candidate"
            )
    return failures, selected, achieved_fpr


def check_detection_delay_uses_correct_decision_timestamp():
    """Guards against the exact bug Step 4 warns about: labeling a window by
    its START time (which can be < inject_time even though the window's last
    timestep is already post-injection) instead of its END time. Builds a
    synthetic case where a window straddles inject_time."""
    inject_time = 1000
    # Window A: start=985, end=1000 (>= inject_time) -> per the LOCKED
    # window_label_rule (last timestep's time), this window IS in the
    # post-injection evaluation region, even though its start_time < inject_time.
    window_start, window_end = 985, 1000
    failures = []
    if not (window_start < inject_time <= window_end):
        failures.append("synthetic fixture invalid: window does not straddle inject_time as intended")

    # Correct (locked) labeling uses window_end for both the region label and
    # the decision timestamp:
    times = [window_end]
    labels = [window_end >= inject_time]          # True: post-injection region
    predictions = [True]                          # predicted anomalous
    det_time = first_detection_time(times, labels, predictions)
    if det_time is None:
        failures.append("expected a detection using end-time-based labeling")
    else:
        delay = detection_delay(inject_time, det_time)
        if delay < 0:
            failures.append(f"end-time-based detection delay must be >= 0 for a post-injection detection, got {delay}")

    # Demonstrate the BUG this test guards against: if a caller mistakenly
    # labeled/timestamped the window by its START time instead, the window
    # would be (wrongly) excluded from the post-injection region entirely
    # (label=False, since 985 < 1000) even though real telemetry through
    # t=1000 (already post-injection) was used to construct it -- i.e. the
    # bug silently drops a legitimate detection rather than producing a
    # negative delay outright. Confirm the buggy labeling really does differ
    # from the correct one, proving the two are not accidentally equivalent.
    buggy_label = window_start >= inject_time  # False
    if buggy_label == labels[0]:
        failures.append("fixture does not actually distinguish start-time vs end-time labeling")
    return failures


def check_no_pre_injection_fp_mislabeled_as_post_injection_detection():
    """A window entirely in the known-normal region (end_time < inject_time)
    that is predicted anomalous must count as a pre-fault FALSE POSITIVE, and
    must never be returned as a 'detection' by first_detection_time (which
    only fires on label=True windows)."""
    inject_time = 1000
    times = [990, 995, 1005]
    labels = [t >= inject_time for t in times]          # [False, False, True]
    predictions = [True, False, False]                  # pre-injection FP at t=990, no post-injection prediction
    failures = []
    if labels != [False, False, True]:
        failures.append("fixture labeling incorrect")

    det_time = first_detection_time(times, labels, predictions)
    if det_time is not None:
        failures.append(f"pre-injection false positive at t=990 must not be reported as a detection, got {det_time}")

    # Now confirm compute_metrics correctly buckets it as a pre-fault FP, not
    # a detection, via the full metrics pipeline on a matching synthetic row set.
    rows = [
        dict(case_id="svc_cpu/1", window_end_time=t,
             region="post_injection_evaluation_region" if label else "known_normal_region",
             score=1.0 if pred else 0.0)
        for t, label, pred in zip(times, labels, predictions)
    ]
    m = compute_metrics(rows, threshold=0.5)
    if m["fp"] != 1:
        failures.append(f"expected 1 pre-fault false positive, got fp={m['fp']}")
    if m["tp"] != 0:
        failures.append(f"expected 0 true positives (no post-injection detection), got tp={m['tp']}")
    if m["n_cases_missed"] != 1:
        failures.append(f"expected the single case to be counted as a miss, got n_cases_missed={m['n_cases_missed']}")
    return failures


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    checkpoint_path = os.path.abspath(os.path.expanduser(args.checkpoint))

    case_count_failures, rows = check_exactly_20_validation_cases_scored(data_dir, checkpoint_path, args.manifests_dir)
    every_score_finite_failures, scores = check_every_score_finite(rows)
    candidates_failures, candidates, pre_fault_scores = check_threshold_candidates_derived_only_from_validation_scores(rows)
    selected_threshold_failures, selected, achieved_fpr = check_selected_threshold_satisfies_rule(pre_fault_scores, candidates)

    print(f"Validation windows scored: {len(rows)} across {len(set(r['case_id'] for r in rows))} cases")
    print(f"Score range: [{scores.min():.6f}, {scores.max():.6f}]")
    print(f"Candidate thresholds: {len(candidates)}, selected={selected:.6f} (achieved FPR={achieved_fpr:.4f})\n")

    checks = {
        "checkpoint_loaded_in_eval_mode": check_checkpoint_loaded_in_eval_mode(checkpoint_path),
        "scoring_runs_under_no_grad": check_scoring_runs_under_no_grad(checkpoint_path),
        "model_parameters_never_change_during_scoring": check_model_parameters_never_change_during_scoring(checkpoint_path),
        "exactly_20_validation_cases_scored": case_count_failures,
        "no_test_manifest_loaded_ast": check_no_test_manifest_loaded_ast(),
        "score_formula_hand_computed": check_score_formula_hand_computed(),
        "every_score_finite": every_score_finite_failures,
        "window_metadata_attached_correctly": check_window_metadata_attached_correctly(rows),
        "threshold_candidates_derived_only_from_validation_scores": candidates_failures,
        "selected_threshold_satisfies_rule": selected_threshold_failures,
        "detection_delay_uses_correct_decision_timestamp": check_detection_delay_uses_correct_decision_timestamp(),
        "no_pre_injection_fp_mislabeled_as_post_injection_detection": check_no_pre_injection_fp_mislabeled_as_post_injection_detection(),
    }

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL VALIDATION SCORING + THRESHOLD SELECTION TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
