"""
Model 1 Phase 1 driver: build the training-window tensor and report on it.

Does NOT train any model. Does NOT build or inspect test-split windows or any
evaluation metric. Only constructs the tensor the LSTM autoencoder will later
consume for training, using exactly the locked protocol, and reports its shape
and a few sanity facts so a human can confirm the pipeline before Phase 2
(model implementation) begins.

Does not persist the tensor itself (would be a large, trivially-reproducible
generated artifact -- see repo convention of not committing those). Writes a
small JSON summary instead.

Usage:
    python3 build_train_windows.py --data-dir <BARO_DATA_DIR> [--out <SUMMARY_PATH>]
"""
import argparse
import json
import os

import numpy as np

from dataset import (
    DEFAULT_CONFIGS_DIR,
    DEFAULT_MANIFESTS_DIR,
    TRAIN_STRIDE,
    WINDOW_LENGTH,
    build_train_windows,
    load_features,
    load_manifest,
    load_scaler,
)

HERE = os.path.dirname(os.path.abspath(__file__))


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR)
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR)
    parser.add_argument("--out", default=os.path.join(HERE, "train_window_summary.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))

    features = load_features(args.configs_dir)
    scaler = load_scaler(args.configs_dir)
    train_cases = load_manifest("train", args.manifests_dir)

    print(f"Loaded {len(features)} locked features")
    print(f"Loaded {len(train_cases)} train-split cases from manifest")

    windows, metadata = build_train_windows(
        data_dir, train_cases, features, scaler,
        window_length=WINDOW_LENGTH, stride=TRAIN_STRIDE,
    )

    print(f"Built {windows.shape[0]} training windows")
    print(f"Tensor shape: {windows.shape}  (n_windows, window_length={WINDOW_LENGTH}, n_features={len(features)})")

    # Sanity facts (also independently re-checked by tests/model1/test_data_pipeline_leakage.py)
    cases_used = sorted(set(m["case_id"] for m in metadata))
    windows_per_case = {}
    for m in metadata:
        windows_per_case[m["case_id"]] = windows_per_case.get(m["case_id"], 0) + 1

    inject_times = {}
    for cid in train_cases:
        combo, run_id = cid.split("/")
        with open(os.path.join(data_dir, combo, run_id, "inject_time.txt")) as f:
            inject_times[cid] = int(f.read().strip())
    all_end_times_pre_fault = all(m["end_time"] < inject_times[m["case_id"]] for m in metadata)

    summary = dict(
        n_features=len(features),
        n_train_cases_loaded=len(train_cases),
        n_train_cases_with_windows=len(cases_used),
        n_training_windows=int(windows.shape[0]),
        tensor_shape=list(windows.shape),
        window_length=WINDOW_LENGTH,
        train_stride=TRAIN_STRIDE,
        windows_per_case_min=min(windows_per_case.values()) if windows_per_case else None,
        windows_per_case_max=max(windows_per_case.values()) if windows_per_case else None,
        all_windows_strictly_pre_fault=all_end_times_pre_fault,
    )
    with open(args.out, "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nWrote {args.out}")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
