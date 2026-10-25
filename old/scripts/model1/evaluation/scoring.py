"""
Model 1 Phase 5 (validation-only): reconstruction anomaly scoring.

Uses ONLY the frozen epoch-96 checkpoint from the successful training run
(experiments/model1/baseline_seed42_h64_z32_mean_impute). No model parameter
is ever updated here -- this file loads the checkpoint, sets the model to
eval() mode, and scores windows entirely under torch.no_grad().

Anomaly-score rule (recorded here as the explicit Model 1 scoring rule,
consistent with protocol_config.json's window_prediction_rule, which names
"mean squared error over the window" as its example formula but does not pin
down the exact reduction):

    window_score = mean((x - reconstruction)^2)

taken over all 30 timesteps x 55 features of the window (a single scalar per
window). This is exactly torch.nn.functional.mse_loss(recon, x, reduction="mean")
applied per-window -- the same reduction already used as the training loss,
just evaluated per-window instead of per-batch.

Only the 20 VAL cases are used. Never loads data/model1/manifests/test_cases.json.

Usage as a library:
    from scoring import load_frozen_model, build_validation_scores
"""
import argparse
import csv
import os
import sys

import numpy as np
import torch

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "training"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "models", "model1"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))

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
from train import build_model_from_config, load_training_config  # noqa: E402
from metrics import fault_type_of_case  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TRAINING_CONFIG = os.path.join(REPO_ROOT, "configs", "model1", "training_config.json")


def service_of_case(case_id):
    """'cartservice_cpu/3' -> 'cartservice'. Strips the '_<fault_type>' suffix
    identified by metrics.fault_type_of_case, so it stays consistent with the
    same parsing rule used for fault-type stratification."""
    combo = case_id.split("/")[0]
    ft = fault_type_of_case(case_id)
    suffix = "_" + ft
    assert combo.endswith(suffix), f"unexpected combo format: {combo!r}"
    return combo[: -len(suffix)]


def load_frozen_model(checkpoint_path, training_config_path=DEFAULT_TRAINING_CONFIG):
    """Builds the locked architecture from training_config.json, loads the
    given checkpoint's state dict, and returns the model in eval() mode.
    Never touches an optimizer -- there is nothing here that could update a
    parameter."""
    training_config = load_training_config(training_config_path)
    model, model_config = build_model_from_config(training_config)
    state_dict = torch.load(checkpoint_path, map_location="cpu")
    model.load_state_dict(state_dict)
    model.eval()
    return model


def reconstruction_score(x, recon):
    """Pure function: x, recon are numpy arrays of identical shape
    (..., seq_len, n_features) or (seq_len, n_features) for a single window.
    Returns mean((x - recon)^2) reduced over the LAST TWO axes only (so a
    batch of windows yields one scalar score per window, not a single scalar
    for the whole batch)."""
    x = np.asarray(x, dtype=np.float64)
    recon = np.asarray(recon, dtype=np.float64)
    sq_err = (x - recon) ** 2
    if x.ndim == 2:
        return float(sq_err.mean())
    return sq_err.mean(axis=tuple(range(1, x.ndim)))


def score_windows(model, windows, batch_size=256):
    """windows: torch.FloatTensor (N, seq_len, n_features). Returns a numpy
    array of shape (N,) with one reconstruction score per window. Runs
    entirely under torch.no_grad() with the model in eval() mode -- no
    parameter is read-write touched, no gradient is ever computed."""
    assert not model.training, "model must be in eval() mode before scoring"
    n = windows.shape[0]
    scores = np.empty(n, dtype=np.float64)
    with torch.no_grad():
        for start in range(0, n, batch_size):
            batch = windows[start : start + batch_size]
            recon = model(batch)
            batch_scores = reconstruction_score(batch.numpy(), recon.numpy())
            scores[start : start + batch_size] = batch_scores
    return scores


def build_validation_scores(data_dir, checkpoint_path,
                             configs_dir=DEFAULT_CONFIGS_DIR,
                             manifests_dir=DEFAULT_MANIFESTS_DIR,
                             training_config_path=DEFAULT_TRAINING_CONFIG):
    """Full validation-only scoring pipeline:
      - only the 20 VAL cases (never loads test_cases.json)
      - full case timeline (pre- and post-injection), stride=EVAL_STRIDE
      - committed 55-feature order, committed scaler, committed
        training-mean imputation policy (all inside build_eval_windows)
      - frozen epoch-96 checkpoint, eval() mode, no_grad scoring

    Returns (rows, model) where rows is a list of dicts, one per validation
    window, each with: case_id, service, fault_type, window_start_time,
    window_end_time, region ("known_normal_region" or
    "post_injection_evaluation_region"), score. model is returned so callers
    (and tests) can verify its state_dict is unchanged after scoring.
    """
    features = load_features(configs_dir)
    scaler = load_scaler(configs_dir)
    val_cases = load_manifest("val", manifests_dir)
    # Deliberately never: load_manifest("test", ...) -- the test split is not
    # loaded anywhere in this file, in this phase or any other.

    windows_np, window_meta = build_eval_windows(
        data_dir, val_cases, features, scaler, window_length=WINDOW_LENGTH, stride=EVAL_STRIDE
    )
    windows = torch.tensor(windows_np, dtype=torch.float32)

    model = load_frozen_model(checkpoint_path, training_config_path)
    scores = score_windows(model, windows)

    assert len(scores) == len(window_meta) == windows.shape[0]

    rows = []
    for meta, score in zip(window_meta, scores):
        cid = meta["case_id"]
        rows.append(
            dict(
                case_id=cid,
                service=service_of_case(cid),
                fault_type=fault_type_of_case(cid),
                window_index=meta["window_index"],
                window_start_time=meta["start_time"],
                window_end_time=meta["end_time"],
                region=meta["region"],
                score=float(score),
            )
        )
    return rows, model


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
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--training-config", default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--checkpoint", required=True, help="Path to the frozen best.pt checkpoint")
    parser.add_argument("--out", required=True, help="Output path for validation_scores.csv")
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    rows, model = build_validation_scores(
        data_dir, args.checkpoint, args.configs_dir, args.manifests_dir, args.training_config
    )
    write_validation_scores_csv(rows, args.out)

    n_cases = len(set(r["case_id"] for r in rows))
    scores = np.array([r["score"] for r in rows])
    print(f"Scored {len(rows)} validation windows across {n_cases} cases.")
    print(f"Score range: [{scores.min():.6f}, {scores.max():.6f}], mean={scores.mean():.6f}, "
          f"median={np.median(scores):.6f}")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
