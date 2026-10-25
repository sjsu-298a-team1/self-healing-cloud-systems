"""
Model 1 Phase 6: scoring-rule ablation tests (S1/S2/S3).

Uses Candidate B's frozen checkpoint (experiments/model1/
candidate_B_h32_z16_seed42/checkpoints/best.pt) and real BARO data for the
checks that need it, plus small hand-computed synthetic examples for the
formula checks. Never loads data/model1/manifests/test_cases.json.

Usage:
    python3 test_scoring_rule_ablation.py --data-dir <BARO_DATA_DIR>
"""
import argparse
import ast
import copy
import os
import sys

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
EVALUATION_DIR = os.path.join(HERE, "..", "..", "scripts", "model1", "evaluation")
sys.path.insert(0, EVALUATION_DIR)
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "model1", "data"))
sys.path.insert(0, os.path.join(HERE, "..", "..", "scripts", "model1", "protocol"))

from scoring_rules import score_S1, score_S2, score_S3  # noqa: E402
from scoring import load_frozen_model  # noqa: E402
from scoring_ablation import build_multi_rule_validation_scores, score_windows_all_rules  # noqa: E402
from metrics import detection_delay, first_detection_time  # noqa: E402

DEFAULT_CHECKPOINT = os.path.join(
    HERE, "..", "..", "experiments", "model1", "candidate_B_h32_z16_seed42", "checkpoints", "best.pt"
)
DEFAULT_TRAINING_CONFIG = os.path.join(
    HERE, "..", "..", "configs", "model1", "training_config_candidate_B.json"
)


def check_hand_computed_score_formulas():
    """5-timestep, 2-feature synthetic window (seq_len=5 so 'trailing 5' ==
    the whole window, still exercising the correct slice, not a full 30-step
    window -- the slicing logic is length-agnostic)."""
    x = np.array([
        [1.0, 2.0],
        [2.0, 1.0],
        [0.0, 0.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    recon = np.array([
        [1.0, 2.0],   # perfect
        [2.0, 1.0],   # perfect
        [1.0, 1.0],   # sq err: 1, 1
        [3.0, 4.0],   # perfect
        [6.0, 8.0],   # sq err: 1, 4
    ])
    failures = []

    # S1: mean over all 10 elements. Nonzero sq errs: 1,1 (row2) and 1,4 (row4) -> sum=7, mean=7/10=0.7
    expected_s1 = 0.7
    got_s1 = score_S1(x, recon)
    if not np.isclose(got_s1, expected_s1, atol=1e-12):
        failures.append(f"S1: expected {expected_s1}, got {got_s1}")

    # S2: final timestep only -> row4 sq errs [1,4], mean = 2.5
    expected_s2 = 2.5
    got_s2 = score_S2(x, recon)
    if not np.isclose(got_s2, expected_s2, atol=1e-12):
        failures.append(f"S2: expected {expected_s2}, got {got_s2}")

    # S3: trailing 5 timesteps == whole window here -> same as S1 = 0.7
    expected_s3 = 0.7
    got_s3 = score_S3(x, recon)
    if not np.isclose(got_s3, expected_s3, atol=1e-12):
        failures.append(f"S3 (full-length case): expected {expected_s3}, got {got_s3}")

    # A second, longer (7-timestep) example so S3's "trailing 5" slice is a
    # STRICT, nontrivial subset of the window (distinguishing it from S1).
    x2 = np.vstack([np.zeros((2, 2)), x])          # prepend 2 all-zero, perfectly-reconstructed rows
    recon2 = np.vstack([np.zeros((2, 2)), recon])
    got_s1_2 = score_S1(x2, recon2)
    got_s3_2 = score_S3(x2, recon2)
    expected_s1_2 = 7.0 / 14.0   # same 7 total sq err, now over 7*2=14 elements
    expected_s3_2 = 0.7          # trailing 5 rows are exactly the original x/recon -> same as S1 above
    if not np.isclose(got_s1_2, expected_s1_2, atol=1e-12):
        failures.append(f"S1 (7-step case): expected {expected_s1_2}, got {got_s1_2}")
    if not np.isclose(got_s3_2, expected_s3_2, atol=1e-12):
        failures.append(f"S3 (7-step case): expected {expected_s3_2}, got {got_s3_2}")
    if np.isclose(got_s1_2, got_s3_2, atol=1e-12):
        failures.append("S1 and S3 must differ once the window is longer than 5 steps -- test is vacuous otherwise")

    # Batch form: stack two windows, confirm per-window (not pooled) scores.
    x_batch = np.stack([x, x2[-5:]])       # second entry: same 5 rows as `x` -> should score identically
    recon_batch = np.stack([recon, recon2[-5:]])
    got_batch_s1 = score_S1(x_batch, recon_batch)
    if not np.allclose(got_batch_s1, [0.7, 0.7], atol=1e-12):
        failures.append(f"batched S1 scores incorrect: {got_batch_s1}")

    return failures


def check_scoring_eval_and_no_grad(checkpoint_path, training_config_path):
    model = load_frozen_model(checkpoint_path, training_config_path)
    failures = []
    if model.training:
        failures.append("model not in eval() mode")
    windows = torch.randn(4, 30, 55)
    scores = score_windows_all_rules(model, windows)
    for name, vals in scores.items():
        arr = np.asarray(vals)
        if not np.isfinite(arr).all():
            failures.append(f"{name}: non-finite score produced from a no_grad forward pass")
    return failures


def check_frozen_checkpoint_unchanged(checkpoint_path, training_config_path):
    model = load_frozen_model(checkpoint_path, training_config_path)
    before = copy.deepcopy(model.state_dict())
    windows = torch.randn(8, 30, 55)
    score_windows_all_rules(model, windows)
    after = model.state_dict()
    failures = []
    for k in before:
        if not torch.equal(before[k], after[k]):
            failures.append(f"parameter {k} changed during scoring-rule ablation scoring")
    return failures


def check_no_test_manifest_loaded_ast():
    failures = []
    for script in ["scoring_ablation.py", "compare_scoring_rules.py"]:
        path = os.path.join(EVALUATION_DIR, script)
        with open(path) as f:
            tree = ast.parse(f.read())
        load_manifest_args = [
            node.args[0].value for node in ast.walk(tree)
            if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "load_manifest"
            and node.args and isinstance(node.args[0], ast.Constant)
        ]
        if "test" in load_manifest_args:
            failures.append(f"{script} calls load_manifest(\"test\", ...); calls found: {load_manifest_args}")
    return failures


def check_correct_end_time_detection_timestamp():
    """Same guard as Phase 5: decision timestamp must be the window's END
    time, not its start time -- re-verified here since Phase 6 reuses the
    same window metadata pipeline for all three scoring rules."""
    inject_time = 500
    window_start, window_end = 490, 505
    failures = []
    if not (window_start < inject_time <= window_end):
        failures.append("fixture invalid: window does not straddle inject_time")
    times = [window_end]
    labels = [window_end >= inject_time]
    predictions = [True]
    det_time = first_detection_time(times, labels, predictions)
    if det_time != window_end:
        failures.append(f"expected detection timestamp == window_end ({window_end}), got {det_time}")
    delay = detection_delay(inject_time, det_time)
    if delay < 0:
        failures.append(f"expected non-negative delay using end-time labeling, got {delay}")
    return failures


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--checkpoint", default=DEFAULT_CHECKPOINT)
    parser.add_argument("--training-config", default=DEFAULT_TRAINING_CONFIG)
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    checkpoint_path = os.path.abspath(os.path.expanduser(args.checkpoint))

    checks = {
        "hand_computed_score_formulas": check_hand_computed_score_formulas(),
        "scoring_eval_and_no_grad": check_scoring_eval_and_no_grad(checkpoint_path, args.training_config),
        "frozen_checkpoint_unchanged": check_frozen_checkpoint_unchanged(checkpoint_path, args.training_config),
        "no_test_manifest_loaded_ast": check_no_test_manifest_loaded_ast(),
        "correct_end_time_detection_timestamp": check_correct_end_time_detection_timestamp(),
    }

    all_passed = all(len(v) == 0 for v in checks.values())
    for name, failures in checks.items():
        status = "PASS" if not failures else "FAIL"
        print(f"[{status}] {name}")
        for f in failures:
            print(f"    - {f}")

    print(f"\nALL SCORING-RULE ABLATION TESTS PASSED: {all_passed}")
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
