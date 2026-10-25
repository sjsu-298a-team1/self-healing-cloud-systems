"""
Model 1 Phase 6: validation-only scoring-rule ablation pipeline.

Uses the FROZEN Candidate B (h32/z16) checkpoint only -- no model is trained
here. Builds the full validation timeline exactly once (same 20 val cases,
stride=1, same 55 features, same scaler/imputation) and runs the frozen
checkpoint's forward pass exactly once per window batch, in eval() mode under
torch.no_grad(); the SAME (x, reconstruction) pair is then scored under all
three predeclared rules (S1/S2/S3 from scoring_rules.py), so the only thing
that varies across S1/S2/S3 is the scoring reduction itself.

Never loads data/model1/manifests/test_cases.json.

Usage as a library:
    from scoring_ablation import build_multi_rule_validation_scores
"""
import argparse
import csv
import os
import sys

import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
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
from scoring_rules import SCORING_RULES  # noqa: E402

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))
from metrics import fault_type_of_case  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TRAINING_CONFIG = os.path.join(REPO_ROOT, "configs", "model1", "training_config_candidate_B.json")


def score_windows_all_rules(model, windows, batch_size=256):
    """Runs the frozen model exactly once per batch (eval() + no_grad), then
    applies every rule in SCORING_RULES to the same (x, recon) pair. Returns
    a dict {rule_name: np.ndarray of shape (N,)}."""
    assert not model.training, "model must be in eval() mode before scoring"
    n = windows.shape[0]
    scores = {name: [None] * n for name in SCORING_RULES}
    with torch.no_grad():
        for start in range(0, n, batch_size):
            batch = windows[start : start + batch_size]
            recon = model(batch)
            x_np = batch.numpy()
            recon_np = recon.numpy()
            for name, rule in SCORING_RULES.items():
                batch_scores = rule["fn"](x_np, recon_np)
                for i, s in enumerate(batch_scores):
                    scores[name][start + i] = float(s)
    return {name: vals for name, vals in scores.items()}


def build_multi_rule_validation_scores(data_dir, checkpoint_path,
                                        configs_dir=DEFAULT_CONFIGS_DIR,
                                        manifests_dir=DEFAULT_MANIFESTS_DIR,
                                        training_config_path=DEFAULT_TRAINING_CONFIG):
    """Returns (rows_by_rule, model): rows_by_rule[name] is a list of dicts
    (case_id, service, fault_type, window_index, window_start_time,
    window_end_time, region, score) for that scoring rule, all built from the
    SAME windows and the SAME frozen forward pass. model is returned so
    callers/tests can verify its state_dict is unchanged after scoring."""
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    val_cases = load_manifest("val", manifests_dir)
    # Deliberately never: load_manifest("test", ...).

    windows_np, window_meta = build_eval_windows(
        data_dir, val_cases, features, scaler, window_length=WINDOW_LENGTH, stride=EVAL_STRIDE
    )
    windows = torch.tensor(windows_np, dtype=torch.float32)

    model = load_frozen_model(checkpoint_path, training_config_path)
    scores_by_rule = score_windows_all_rules(model, windows)

    rows_by_rule = {name: [] for name in SCORING_RULES}
    for name, scores in scores_by_rule.items():
        for meta, score in zip(window_meta, scores):
            cid = meta["case_id"]
            rows_by_rule[name].append(
                dict(
                    case_id=cid,
                    service=service_of_case(cid),
                    fault_type=fault_type_of_case(cid),
                    window_index=meta["window_index"],
                    window_start_time=meta["start_time"],
                    window_end_time=meta["end_time"],
                    region=meta["region"],
                    score=score,
                )
            )
    return rows_by_rule, model


def write_validation_scores_csv(rows, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["case_id", "service", "fault_type", "window_index",
                  "window_start_time", "window_end_time", "region", "score"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True)
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--training-config", default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument("--out-dir", required=True, help="Base dir; writes <out-dir>/<rule>/validation_scores.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    rows_by_rule, model = build_multi_rule_validation_scores(
        data_dir, args.checkpoint, args.configs_dir, args.manifests_dir, args.training_config
    )
    for name, rows in rows_by_rule.items():
        out_path = os.path.join(args.out_dir, name, "validation_scores.csv")
        write_validation_scores_csv(rows, out_path)
        n_cases = len(set(r["case_id"] for r in rows))
        print(f"{name}: scored {len(rows)} windows across {n_cases} cases -> {out_path}")


if __name__ == "__main__":
    main()
