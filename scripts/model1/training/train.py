"""
Model 1 Phase 3: reproducible training pipeline.

IMPORTANT: importing/running this module's plumbing (via tests, with synthetic
or tiny data) does not constitute "real training" -- the real 4,020-window
training run against actual BARO telemetry is a separate, later action, not
performed by writing or testing this file.

Never loads data/model1/manifests/test_cases.json anywhere. The test split is
reserved for a later, separate evaluation phase after the reconstruction model
is frozen.

Usage (NOT invoked against real data in this phase):
    python3 train.py --data-dir <BARO_DATA_DIR> --run-id <RUN_ID>
"""
import argparse
import json
import os
import platform
import random
import sys
import time

import numpy as np
import torch
from torch import nn

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "models", "model1"))

from dataset import (  # noqa: E402
    DEFAULT_CONFIGS_DIR,
    DEFAULT_MANIFESTS_DIR,
    EVAL_STRIDE,
    TRAIN_STRIDE,
    WINDOW_LENGTH,
    build_model_selection_validation_windows,
    build_train_windows,
    load_features,
    load_manifest,
    load_scaler,
)
from lstm_autoencoder import LSTMAutoencoder, LSTMAutoencoderConfig, count_trainable_parameters  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_TRAINING_CONFIG = os.path.join(REPO_ROOT, "configs", "model1", "training_config.json")
DEFAULT_EXPERIMENTS_DIR = os.path.join(REPO_ROOT, "experiments", "model1")


def set_seeds(seed: int):
    """Deterministic seeding for Python random, NumPy, and PyTorch (CPU and,
    if available, CUDA). This seed is independent of configs/model1/split_seed.json
    (which governs the data split, not training)."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_training_config(path=DEFAULT_TRAINING_CONFIG):
    with open(path) as f:
        return json.load(f)


def build_model_from_config(training_config):
    m = training_config["model"]
    model_config = LSTMAutoencoderConfig(
        input_size=m["input_size"],
        sequence_length=m["sequence_length"],
        hidden_size=m["hidden_size"],
        latent_size=m["latent_size"],
        num_layers=m["num_layers"],
        dropout=m["dropout"],
    )
    return LSTMAutoencoder(model_config), model_config


def train_one_epoch(model, windows, optimizer, batch_size, generator):
    """windows: torch.Tensor (N, seq_len, n_features). Returns average
    reconstruction MSE loss over the epoch. Updates model parameters."""
    model.train()
    n = windows.shape[0]
    perm = torch.randperm(n, generator=generator)
    total_loss = 0.0
    n_batches = 0
    for start in range(0, n, batch_size):
        idx = perm[start : start + batch_size]
        batch = windows[idx]
        optimizer.zero_grad()
        recon = model(batch)
        loss = nn.functional.mse_loss(recon, batch)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()
        n_batches += 1
    return total_loss / max(n_batches, 1)


def evaluate_loss(model, windows, batch_size=256):
    """windows: torch.Tensor (N, seq_len, n_features). Returns average
    reconstruction MSE loss. Does NOT update model parameters (no_grad,
    model in eval mode) -- this is a pure validation-loss computation, not a
    threshold/F1/FPR/detection-delay calculation of any kind."""
    model.eval()
    n = windows.shape[0]
    total_loss = 0.0
    n_batches = 0
    with torch.no_grad():
        for start in range(0, n, batch_size):
            batch = windows[start : start + batch_size]
            recon = model(batch)
            loss = nn.functional.mse_loss(recon, batch)
            total_loss += loss.item()
            n_batches += 1
    return total_loss / max(n_batches, 1)


class BestCheckpointTracker:
    """Tracks the best (lowest) validation loss seen so far and whether the
    current epoch is a new best. Selection is based ONLY on validation
    reconstruction loss -- no labeled/threshold-derived metric is involved."""

    def __init__(self):
        self.best_val_loss = float("inf")
        self.best_epoch = None

    def update(self, epoch, val_loss):
        is_best = val_loss < self.best_val_loss
        if is_best:
            self.best_val_loss = val_loss
            self.best_epoch = epoch
        return is_best


class EarlyStopper:
    """Stops training after `patience_epochs` consecutive epochs with no
    improvement in validation loss. Based only on validation reconstruction
    loss, per the locked early-stopping policy."""

    def __init__(self, patience_epochs):
        self.patience_epochs = patience_epochs
        self.epochs_since_improvement = 0

    def step(self, is_best):
        if is_best:
            self.epochs_since_improvement = 0
        else:
            self.epochs_since_improvement += 1
        return self.epochs_since_improvement >= self.patience_epochs


def run_training_loop(train_windows, val_windows, training_config, run_dir, run_id, extra_metadata=None):
    """Core training loop, reusable by both main() (real BARO windows) and
    tests (synthetic windows) -- contains all parameter updates, checkpoint
    selection, early stopping, and output-file writing. Takes tensors directly;
    does no data loading itself, so it cannot load the test manifest.

    Returns (model, history, checkpoint_tracker) for direct inspection in tests.
    """
    model, model_config = build_model_from_config(training_config)
    optimizer = torch.optim.Adam(model.parameters(), lr=training_config["optimizer"]["learning_rate"])
    generator = torch.Generator().manual_seed(training_config["seed"]["value"])

    checkpoint_tracker = BestCheckpointTracker()
    early_stopper = EarlyStopper(training_config["early_stopping"]["patience_epochs"])
    history = []

    checkpoints_dir = os.path.join(run_dir, "checkpoints")
    os.makedirs(checkpoints_dir, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    start_time = time.time()

    for epoch in range(1, training_config["max_epochs"] + 1):
        train_loss = train_one_epoch(model, train_windows, optimizer, training_config["batch_size"], generator)
        val_loss = evaluate_loss(model, val_windows)
        is_best = checkpoint_tracker.update(epoch, val_loss)
        history.append(dict(epoch=epoch, train_loss=train_loss, val_loss=val_loss, is_best=is_best))

        if is_best:
            torch.save(model.state_dict(), os.path.join(checkpoints_dir, "best.pt"))

        if early_stopper.step(is_best):
            print(f"Early stopping at epoch {epoch} (no val improvement for "
                  f"{training_config['early_stopping']['patience_epochs']} epochs)")
            break

    runtime_sec = time.time() - start_time

    with open(os.path.join(run_dir, "config_snapshot.json"), "w") as f:
        json.dump(
            dict(training_config=training_config, n_trainable_parameters=count_trainable_parameters(model)),
            f, indent=2,
        )
    with open(os.path.join(run_dir, "training_history.json"), "w") as f:
        json.dump(history, f, indent=2)
    with open(os.path.join(run_dir, "run_metadata.json"), "w") as f:
        json.dump(
            dict(
                run_id=run_id,
                n_train_windows=int(train_windows.shape[0]),
                n_val_windows=int(val_windows.shape[0]),
                best_epoch=checkpoint_tracker.best_epoch,
                best_val_loss=checkpoint_tracker.best_val_loss,
                epochs_run=len(history),
                runtime_sec=runtime_sec,
                device=device,
                python_version=platform.python_version(),
                torch_version=torch.__version__,
                platform=platform.platform(),
                **(extra_metadata or {}),
            ),
            f, indent=2,
        )

    return model, history, checkpoint_tracker


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--training-config", default=DEFAULT_TRAINING_CONFIG)
    parser.add_argument("--experiments-dir", default=DEFAULT_EXPERIMENTS_DIR)
    parser.add_argument("--run-id", required=True, help="Name for this run's experiments/model1/<run_id>/ directory")
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    training_config = load_training_config(args.training_config)

    set_seeds(training_config["seed"]["value"])

    features = load_features(args.configs_dir)
    scaler = load_scaler(args.configs_dir)
    train_cases = load_manifest("train", args.manifests_dir)
    val_cases = load_manifest("val", args.manifests_dir)
    # Deliberately never: load_manifest("test", ...) -- the test split is not
    # loaded anywhere in this file, in this phase or any other.

    train_windows_np, _ = build_train_windows(
        data_dir, train_cases, features, scaler, window_length=WINDOW_LENGTH, stride=TRAIN_STRIDE
    )
    # Model-selection validation windows: known-normal (time < inject_time) rows
    # of val-split cases ONLY, stride=EVAL_STRIDE (finer than the train stride).
    # Used ONLY for val_reconstruction_loss / early stopping / best-checkpoint
    # selection below -- this is a ONE-CLASS normal-behavior reconstruction
    # model, so model-selection must never see post-injection windows. This is
    # NOT the full pre+post eval-window construction (build_eval_windows /
    # protocol_config.json windowing.eval_windows_source) used later for
    # threshold selection -- that full timeline is a separate, later phase and
    # is never built or touched anywhere in this training path.
    val_windows_np, _ = build_model_selection_validation_windows(
        data_dir, val_cases, features, scaler, window_length=WINDOW_LENGTH, stride=EVAL_STRIDE
    )

    train_windows = torch.tensor(train_windows_np, dtype=torch.float32)
    val_windows = torch.tensor(val_windows_np, dtype=torch.float32)

    run_dir = os.path.join(args.experiments_dir, args.run_id)
    model, history, checkpoint_tracker = run_training_loop(
        train_windows, val_windows, training_config, run_dir, args.run_id,
        extra_metadata=dict(n_train_cases=len(train_cases), n_val_cases=len(val_cases)),
    )

    print(f"Run complete: {len(history)} epochs, best val_loss={checkpoint_tracker.best_val_loss:.6f} "
          f"at epoch {checkpoint_tracker.best_epoch}. Outputs in {run_dir}")


if __name__ == "__main__":
    main()
