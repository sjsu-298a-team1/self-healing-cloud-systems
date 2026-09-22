"""
Model 1 protocol step 1+2: fixed feature list + deterministic split manifests.

Reads the read-only dataset-inspection outputs (column_presence.csv) plus the BARO
dataset directory itself (to enumerate case folders); does not modify anything
under the BARO clone or dataset.

Split rule (locked decision: 3/1/1 runs per (service, fault_type) combo).

REVISION (see protocol.md changelog): the original version of this script used a
FIXED assignment (run_id 1,2,3 -> train, run_id 4 -> val, run_id 5 -> test) for
every combo. That was replaced because "run 4" and "run 5" are not necessarily
interchangeable with "run 1-3" (e.g. possible run-order/warm-up effects), so
always picking the same run numbers for val/test could quietly bias those splits.
This version instead draws a deterministic SEEDED permutation of {1,2,3,4,5}
independently for each of the 20 combos (seeded off a single global SPLIT_SEED
plus the combo name, so re-running this script is byte-for-byte reproducible),
takes the first 3 as train / next 1 as val / last 1 as test, and records the
seed plus every combo's permutation in configs/split_seed.json for audit.

Usage:
    python3 build_manifests.py --data-dir <BARO_DATA_DIR> --inspection-dir <INSPECTION_DIR>
                                [--configs-dir <CONFIGS_DIR>] [--manifests-dir <MANIFESTS_DIR>]

    <BARO_DATA_DIR> is the path to BARO's data/fse-ob directory.
    <INSPECTION_DIR> is the directory containing column_presence.csv (the
    dataset-inspection output -- e.g. data/model1/dataset_inspection/ once the
    298-33 dataset-inspection PR is merged).
    <CONFIGS_DIR>/<MANIFESTS_DIR> default to this repo's configs/model1/ and
    data/model1/manifests/, resolved relative to this script's own location.
"""
import argparse
import glob
import json
import os
import random

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
DEFAULT_CONFIGS_DIR = os.path.join(REPO_ROOT, "configs", "model1")
DEFAULT_MANIFESTS_DIR = os.path.join(REPO_ROOT, "data", "model1", "manifests")

SPLIT_SEED = 298
RUN_IDS = [1, 2, 3, 4, 5]
N_TRAIN, N_VAL, N_TEST = 3, 1, 1


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Path to BARO's data/fse-ob directory")
    parser.add_argument(
        "--inspection-dir", required=True,
        help="Directory containing column_presence.csv from the dataset-inspection step",
    )
    parser.add_argument("--configs-dir", default=DEFAULT_CONFIGS_DIR,
                         help="Where to write features.json and split_seed.json")
    parser.add_argument("--manifests-dir", default=DEFAULT_MANIFESTS_DIR,
                         help="Where to write the train/val/test manifests and summary CSV")
    return parser.parse_args()

EXCLUDED_COLUMNS = [
    "adservice_error",
    "cartservice_error",
    "checkoutservice_error",
    "frontend_error",
    "frontend-external_error",
    "productcatalogservice_error",
    "istio-init_mem",
]


def load_feature_list(inspection_dir):
    presence = pd.read_csv(os.path.join(inspection_dir, "column_presence.csv"))
    features = sorted(
        presence[(presence["present_in_all"]) & (~presence["is_metadata"])]["column"].tolist()
    )
    assert len(features) == 55, f"expected 55 universal features, got {len(features)}"
    assert "time" not in features
    for c in EXCLUDED_COLUMNS:
        assert c not in features, f"{c} should have been excluded, but is in the feature list"
    return features


def enumerate_cases(data_root):
    cases = []
    for combo_dir in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(combo_dir):
            continue
        combo = os.path.basename(combo_dir)
        for run_dir in sorted(glob.glob(os.path.join(combo_dir, "*"))):
            if not os.path.isdir(run_dir):
                continue
            run_id = int(os.path.basename(run_dir))
            cases.append(dict(combo=combo, run_id=run_id, path=run_dir))
    assert len(cases) == 100, f"expected 100 cases, found {len(cases)}"
    return cases


def seeded_permutation_for_combo(combo):
    """Deterministic permutation of RUN_IDS for one combo.

    Uses a per-combo string seed derived from the single global SPLIT_SEED, so
    (a) every combo gets an independent-looking shuffle rather than the same
    rotation, and (b) the whole thing is 100% reproducible from SPLIT_SEED alone
    -- no state carries over between combos, so combo iteration order can't
    accidentally change the result. Python's random.Random(str) seeding is
    documented as stable across runs/versions (unlike hash()), so this is safe
    to persist and re-derive later.
    """
    rng = random.Random(f"{SPLIT_SEED}-{combo}")
    perm = RUN_IDS.copy()
    rng.shuffle(perm)
    return perm


def build_splits(cases):
    by_combo = {}
    for c in cases:
        by_combo.setdefault(c["combo"], []).append(c["run_id"])

    train, val, test = [], [], []
    permutations = {}
    for combo, run_ids in sorted(by_combo.items()):
        assert sorted(run_ids) == RUN_IDS, f"{combo} does not have exactly runs 1-5: {run_ids}"
        perm = seeded_permutation_for_combo(combo)
        permutations[combo] = perm
        train_runs = perm[:N_TRAIN]
        val_runs = perm[N_TRAIN:N_TRAIN + N_VAL]
        test_runs = perm[N_TRAIN + N_VAL:N_TRAIN + N_VAL + N_TEST]
        train += [f"{combo}/{r}" for r in train_runs]
        val += [f"{combo}/{r}" for r in val_runs]
        test += [f"{combo}/{r}" for r in test_runs]

    return sorted(train), sorted(val), sorted(test), permutations


def main():
    args = parse_args()
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    inspection_dir = os.path.abspath(os.path.expanduser(args.inspection_dir))
    configs_dir = os.path.abspath(os.path.expanduser(args.configs_dir))
    manifests_dir_out = os.path.abspath(os.path.expanduser(args.manifests_dir))
    os.makedirs(configs_dir, exist_ok=True)
    os.makedirs(manifests_dir_out, exist_ok=True)

    features = load_feature_list(inspection_dir)
    features_path = os.path.join(configs_dir, "features.json")
    with open(features_path, "w") as f:
        json.dump(
            dict(
                n_features=len(features),
                features=features,
                excluded_columns=EXCLUDED_COLUMNS,
                excluded_reason="not present in every one of the 100 cases (true schema "
                "gap; see docs/model1/dataset-inspection/findings.md section A.2/3 and B.1)",
                source="data/model1/dataset_inspection/column_presence.csv (present_in_all "
                "== True, is_metadata == False)",
                time_index_excluded=True,
                time_index_note="'time' (unix epoch seconds) and row index are NOT model "
                "features; used only to compute labels/splits/windowing, never fed to the model",
            ),
            f,
            indent=2,
        )
    print(f"Wrote {features_path} ({len(features)} features)")

    cases = enumerate_cases(data_dir)
    train, val, test, permutations = build_splits(cases)

    seed_path = os.path.join(configs_dir, "split_seed.json")
    with open(seed_path, "w") as f:
        json.dump(
            dict(
                split_seed=SPLIT_SEED,
                method="random.Random(f'{SPLIT_SEED}-{combo}').shuffle(run_ids) per combo, "
                "independently for each of the 20 (service, fault_type) combos",
                run_ids=RUN_IDS,
                n_train=N_TRAIN,
                n_val=N_VAL,
                n_test=N_TEST,
                permutation_per_combo=permutations,
                permutation_note="first n_train runs -> train, next n_val -> val, last n_test -> test",
            ),
            f,
            indent=2,
        )
    print(f"Wrote {seed_path}")

    manifests_dir = manifests_dir_out
    for name, ids in [("train", train), ("val", val), ("test", test)]:
        path = os.path.join(manifests_dir, f"{name}_cases.json")
        with open(path, "w") as f:
            json.dump(dict(split=name, n_cases=len(ids), case_ids=ids), f, indent=2)
        print(f"Wrote {path} ({len(ids)} cases)")

    # human-readable summary CSV: one row per case with its assigned split
    rows = []
    split_of = {}
    for cid in train:
        split_of[cid] = "train"
    for cid in val:
        split_of[cid] = "val"
    for cid in test:
        split_of[cid] = "test"
    for c in cases:
        cid = f"{c['combo']}/{c['run_id']}"
        rows.append(dict(case_id=cid, combo=c["combo"], run_id=c["run_id"], split=split_of[cid]))
    summary_df = pd.DataFrame(rows).sort_values(["combo", "run_id"])
    summary_path = os.path.join(manifests_dir, "manifest_summary.csv")
    summary_df.to_csv(summary_path, index=False)
    print(f"Wrote {summary_path}")

    # sanity print: per-combo split counts
    counts = summary_df.groupby(["combo", "split"]).size().unstack(fill_value=0)
    print("\nPer-combo split counts (expect train=3, val=1, test=1 for every combo):")
    print(counts.to_string())
    bad = counts[(counts.get("train", 0) != 3) | (counts.get("val", 0) != 1) | (counts.get("test", 0) != 1)]
    if len(bad):
        raise AssertionError(f"combo(s) with wrong split counts:\n{bad}")
    print("\nAll 20 combos have exactly 3 train / 1 val / 1 test runs.")


if __name__ == "__main__":
    main()
