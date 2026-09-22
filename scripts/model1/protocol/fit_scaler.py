"""
Model 1 protocol step 4: fit normalization stats on TRAIN pre-fault rows only.

This computes per-feature mean/std and saves them as a reusable artifact
(scaler.json). It does NOT train the LSTM autoencoder -- it only fits the
preprocessing statistics the autoencoder will later consume. Reads
simple_data.csv for train-manifest cases only; never touches val or test
cases; never modifies anything under the BARO clone or dataset.

Usage:
    python3 fit_scaler.py --data-dir <BARO_DATA_DIR>
                           [--configs-dir <CONFIGS_DIR>] [--manifests-dir <MANIFESTS_DIR>]

    <BARO_DATA_DIR> is the path to BARO's data/fse-ob directory.
    <CONFIGS_DIR> is read from (features.json) and written to (scaler.json);
    <MANIFESTS_DIR> is read from (train_cases.json). Both default to this
    repo's configs/model1/ and data/model1/manifests/, resolved relative to
    this script's own location.
"""
import argparse
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_CONFIGS_DIR = os.path.join(REPO_ROOT, "configs", "model1")
DEFAULT_MANIFESTS_DIR = os.path.join(REPO_ROOT, "data", "model1", "manifests")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR,
                         help="Directory with features.json; scaler.json is written here")
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR,
                         help="Directory with train_cases.json")
    return parser.parse_args()


def load_case_df(data_root, case_id):
    combo, run_id = case_id.split("/")
    path = os.path.join(data_root, combo, run_id, "simple_data.csv")
    inject_path = os.path.join(data_root, combo, run_id, "inject_time.txt")
    df = pd.read_csv(path)
    with open(inject_path) as f:
        inject_time = int(f.read().strip())
    return df, inject_time


def main():
    args = parse_args()
    data_root = os.path.abspath(os.path.expanduser(args.data_dir))
    configs_dir = os.path.abspath(os.path.expanduser(args.configs_dir))
    manifests_dir = os.path.abspath(os.path.expanduser(args.manifests_dir))

    with open(os.path.join(configs_dir, "features.json")) as f:
        features = json.load(f)["features"]

    with open(os.path.join(manifests_dir, "train_cases.json")) as f:
        train_cases = json.load(f)["case_ids"]

    all_pre_fault_rows = []
    n_rows_per_case = {}
    for cid in train_cases:
        df, inject_time = load_case_df(data_root, cid)
        assert set(features).issubset(set(df.columns)), f"{cid} missing some of the 55 features"
        pre = df[df["time"] < inject_time][features]
        n_rows_per_case[cid] = len(pre)
        all_pre_fault_rows.append(pre)

    stacked = pd.concat(all_pre_fault_rows, axis=0, ignore_index=True)
    means = stacked.mean(numeric_only=True)
    stds = stacked.std(numeric_only=True)

    near_zero_std_features = stds[stds < 1e-8].index.tolist()
    stds_floored = stds.clip(lower=1e-8)

    scaler = dict(
        method="per-feature z-score (StandardScaler)",
        fit_source="pre-fault rows (time < inject_time) of TRAIN-split cases only",
        n_train_cases_used=len(train_cases),
        n_rows_used=int(len(stacked)),
        n_rows_per_case=n_rows_per_case,
        features=features,
        mean=means[features].to_dict(),
        std=stds_floored[features].to_dict(),
        near_zero_std_features=near_zero_std_features,
    )

    out_path = os.path.join(configs_dir, "scaler.json")
    with open(out_path, "w") as f:
        json.dump(scaler, f, indent=2, default=str)

    print(f"Fit scaler on {len(train_cases)} train cases, {len(stacked)} pre-fault rows total")
    if near_zero_std_features:
        print(f"WARNING: near-zero-std features in train pre-fault data: {near_zero_std_features}")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
