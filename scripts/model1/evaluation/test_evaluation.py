"""
Model 1 Phase 7: ONE-TIME held-out test-set evaluation.

This is the first and only place data/model1/manifests/test_cases.json is
ever loaded in the Model 1 codebase. Everything here is fixed by
experiments/model1/final_model_selection.json (frozen BEFORE this file was
written): Candidate B's checkpoint, the S2 (final-timestep MSE) scoring rule,
and the exact validation-selected threshold, used verbatim.

Deliberately does NOT import select_threshold or build_candidate_thresholds
from threshold_selection.py -- no threshold-selection function is invoked on
test scores anywhere in this file. The only threshold_selection.py import is
compute_metrics(rows, threshold), a pure metric computation for an ALREADY
GIVEN threshold; it does not choose a threshold.
"""
import argparse
import csv
import hashlib
import json
import os
import sys
from datetime import datetime, timezone

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dataset import (  # noqa: E402
    DEFAULT_CONFIGS_DIR,
    DEFAULT_MANIFESTS_DIR,
    EVAL_STRIDE,
    WINDOW_LENGTH,
    build_eval_windows,
    load_features,
    load_manifest,
    load_scaler,
)
from scoring import load_frozen_model, service_of_case  # noqa: E402
from scoring_rules import score_S2  # noqa: E402
from threshold_selection import compute_metrics  # noqa: E402  (metric computation only, NOT selection)
from metrics import fault_type_of_case, group_case_ids_by_fault_type  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_FINAL_SELECTION = os.path.join(REPO_ROOT, "experiments", "model1", "final_model_selection.json")
FAULT_TYPES = ("cpu", "mem", "delay", "loss")


def sha256_of_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_final_selection(path=DEFAULT_FINAL_SELECTION):
    with open(path) as f:
        return json.load(f)


def score_test_windows_S2(model, windows, batch_size=256):
    """Runs the frozen model once per batch (eval() + no_grad), scores under
    S2 only -- the frozen scoring rule for this phase. No other rule is
    computed."""
    assert not model.training, "model must be in eval() mode"
    n = windows.shape[0]
    scores = [None] * n
    with torch.no_grad():
        for start in range(0, n, batch_size):
            batch = windows[start : start + batch_size]
            recon = model(batch)
            batch_scores = score_S2(batch.numpy(), recon.numpy())
            for i, s in enumerate(batch_scores):
                scores[start + i] = float(s)
    return scores


def build_test_rows(data_dir, checkpoint_path, training_config_path,
                     configs_dir=DEFAULT_CONFIGS_DIR, manifests_dir=DEFAULT_MANIFESTS_DIR):
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    test_cases = load_manifest("test", manifests_dir)  # the ONLY load_manifest("test", ...) call, ever

    windows_np, window_meta = build_eval_windows(
        data_dir, test_cases, features, scaler, window_length=WINDOW_LENGTH, stride=EVAL_STRIDE
    )
    windows = torch.tensor(windows_np, dtype=torch.float32)

    model = load_frozen_model(checkpoint_path, training_config_path)
    scores = score_test_windows_S2(model, windows)

    rows = []
    for meta, score in zip(window_meta, scores):
        cid = meta["case_id"]
        rows.append(dict(
            case_id=cid,
            service=service_of_case(cid),
            fault_type=fault_type_of_case(cid),
            window_index=meta["window_index"],
            window_start_time=meta["start_time"],
            window_end_time=meta["end_time"],
            region=meta["region"],
            score=score,
        ))
    return rows, model, test_cases


def write_scores_csv(rows, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["case_id", "service", "fault_type", "window_index",
                  "window_start_time", "window_end_time", "region", "score"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def write_per_fault_csv(by_fault_type, out_path):
    fieldnames = ["fault_type", "precision", "recall", "f1", "pre_fault_fpr",
                  "median_detection_delay", "n_cases_with_detection", "n_cases_missed", "n_cases"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for ft in FAULT_TYPES:
            m = by_fault_type.get(ft, {})
            row = dict(fault_type=ft)
            row.update({k: m.get(k) for k in fieldnames if k != "fault_type"})
            writer.writerow(row)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--final-selection", default=DEFAULT_FINAL_SELECTION)
    parser.add_argument("--out-dir", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    final_selection = load_final_selection(args.final_selection)

    checkpoint_path = os.path.join(REPO_ROOT, final_selection["checkpoint"]["path"])
    training_config_path = os.path.join(REPO_ROOT, "configs", "model1", "training_config_candidate_B.json")

    computed_sha256 = sha256_of_file(checkpoint_path)
    expected_sha256 = final_selection["checkpoint"]["sha256"]
    if computed_sha256 != expected_sha256:
        raise RuntimeError(
            f"Checkpoint SHA-256 mismatch: expected {expected_sha256}, computed {computed_sha256}. "
            "Refusing to run test evaluation against a checkpoint that does not match the frozen selection."
        )

    threshold = final_selection["threshold"]["value"]  # exact stored value, never recalculated

    rows, model, test_cases = build_test_rows(data_dir, checkpoint_path, training_config_path,
                                               args.configs_dir, args.manifests_dir)

    # --- structural verification (never silently assumed) ---
    n_cases = len(set(r["case_id"] for r in rows))
    n_total = len(rows)
    n_known_normal = sum(1 for r in rows if r["region"] == "known_normal_region")
    n_post_injection = sum(1 for r in rows if r["region"] == "post_injection_evaluation_region")
    windows_per_case = {}
    for r in rows:
        windows_per_case[r["case_id"]] = windows_per_case.get(r["case_id"], 0) + 1

    os.makedirs(args.out_dir, exist_ok=True)
    write_scores_csv(rows, os.path.join(args.out_dir, "test_scores.csv"))

    pooled = compute_metrics(rows, threshold)
    groups = group_case_ids_by_fault_type(sorted(set(r["case_id"] for r in rows)))
    by_fault_type = {}
    for ft, case_ids in groups.items():
        subset = [r for r in rows if r["case_id"] in set(case_ids)]
        if subset:
            by_fault_type[ft] = compute_metrics(subset, threshold)

    targets = dict(f1_min=0.82, median_detection_delay_max_sec=10, pre_fault_fpr_max=0.05)
    targets_met = dict(
        f1=pooled["f1"] >= targets["f1_min"],
        median_detection_delay=pooled["median_detection_delay"] <= targets["median_detection_delay_max_sec"],
        pre_fault_fpr=pooled["pre_fault_fpr"] <= targets["pre_fault_fpr_max"],
    )

    test_metrics = dict(threshold=threshold, pooled=pooled, by_fault_type=by_fault_type,
                         targets=targets, targets_met=targets_met)
    with open(os.path.join(args.out_dir, "test_metrics.json"), "w") as f:
        json.dump(test_metrics, f, indent=2)

    write_per_fault_csv(by_fault_type, os.path.join(args.out_dir, "test_per_fault_metrics.csv"))

    run_metadata = dict(
        evaluation_timestamp_utc=datetime.now(timezone.utc).isoformat(),
        checkpoint_path=final_selection["checkpoint"]["path"],
        checkpoint_sha256=computed_sha256,
        checkpoint_sha256_matches_frozen_selection=True,
        scoring_rule=final_selection["scoring_rule"]["name"],
        threshold_used=threshold,
        threshold_source=final_selection["threshold"]["source"],
        n_test_cases=n_cases,
        n_test_windows_total=n_total,
        n_test_windows_known_normal=n_known_normal,
        n_test_windows_post_injection_evaluation_region=n_post_injection,
        windows_per_case=windows_per_case,
        statement="Threshold came from validation-only selection (Phase 5/6) and was NOT "
                  "recalibrated, recalculated, or otherwise touched using any test-split score. "
                  "This is a read-only evaluation of an already-frozen model/scoring/threshold.",
    )
    with open(os.path.join(args.out_dir, "test_run_metadata.json"), "w") as f:
        json.dump(run_metadata, f, indent=2)

    print(f"Test cases: {n_cases} (expected 20)")
    print(f"Test windows: total={n_total} known_normal={n_known_normal} post_injection={n_post_injection}")
    print(f"Checkpoint SHA-256 matches frozen selection: {computed_sha256 == expected_sha256}")
    print(f"Threshold used (exact, from stored artifact): {threshold!r}")
    print(f"Pooled: {json.dumps(pooled, indent=2)}")
    print(f"Targets met: {json.dumps(targets_met, indent=2)}")


if __name__ == "__main__":
    main()
