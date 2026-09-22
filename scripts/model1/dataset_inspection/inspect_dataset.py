"""
Model 1 dataset inspection/validation for the BARO Online Boutique artifact.

Read-only inspection of a local checkout of BARO's data/fse-ob directory (the
dataset artifact from Zenodo record 11046533 / github.com/phamquiluan/baro). Does
not modify any file under the BARO clone or dataset.

Loads simple_data.csv per case (not the raw data.csv) because BARO's own
reproducibility.py globs for simple_data.csv -- that is the file the paper's
pipeline actually treats as the canonical multivariate metrics table.

Usage:
    python3 inspect_dataset.py --data-dir <BARO_DATA_DIR> [--out-dir <OUT_DIR>]

    <BARO_DATA_DIR> is the path to BARO's data/fse-ob directory on your machine
    (e.g. the data/fse-ob folder inside a local clone of github.com/phamquiluan/baro).
    <OUT_DIR> defaults to this script's own directory.

Outputs (written to --out-dir, not into the BARO clone):
    case_summary.csv       one row per of the 100 run/case folders
    column_stats.csv       one row per metric column, aggregated across all cases
    dataset_summary.json   machine-readable rollup of every check below
"""
import argparse
import glob
import hashlib
import json
import os
from collections import defaultdict

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

EXPECTED_FAULT_TYPES = {"cpu", "mem", "delay", "loss"}


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir", required=True,
        help="Path to BARO's data/fse-ob directory (Online Boutique artifact)",
    )
    parser.add_argument(
        "--out-dir", default=HERE,
        help="Directory to write outputs to (default: this script's directory)",
    )
    return parser.parse_args()


def parse_case_dir(case_dir_name):
    # e.g. "cartservice_cpu" -> service="cartservice", fault_type="cpu"
    for ft in EXPECTED_FAULT_TYPES:
        suffix = "_" + ft
        if case_dir_name.endswith(suffix):
            return case_dir_name[: -len(suffix)], ft
    return None, None


def find_cases(data_root):
    cases = []
    for combo_dir in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(combo_dir):
            continue
        combo_name = os.path.basename(combo_dir)
        service, fault_type = parse_case_dir(combo_name)
        for run_dir in sorted(glob.glob(os.path.join(combo_dir, "*"))):
            if not os.path.isdir(run_dir):
                continue
            run_id = os.path.basename(run_dir)
            cases.append(
                dict(
                    combo=combo_name,
                    service=service,
                    fault_type=fault_type,
                    run_id=run_id,
                    path=run_dir,
                )
            )
    return cases


def inspect_case(case):
    path = case["path"]
    sd_path = os.path.join(path, "simple_data.csv")
    inject_path = os.path.join(path, "inject_time.txt")

    result = dict(case)
    result["simple_data_exists"] = os.path.exists(sd_path)
    result["inject_time_exists"] = os.path.exists(inject_path)
    if not result["simple_data_exists"]:
        return result, None

    df = pd.read_csv(sd_path)
    n_rows, n_cols = df.shape
    result["n_rows"] = n_rows
    result["n_cols"] = n_cols
    result["n_metric_cols"] = n_cols - 1  # exclude "time"
    # SHA-256 over the exact ordered column list (JSON array, stable separators) --
    # deterministic across processes/machines, unlike Python's randomized str hash().
    result["columns_hash"] = hashlib.sha256(
        json.dumps(list(df.columns), separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # timestamp checks
    time_col = df["time"]
    result["time_dtype"] = str(time_col.dtype)
    result["time_min"] = int(time_col.min())
    result["time_max"] = int(time_col.max())
    result["time_span_sec"] = int(time_col.max() - time_col.min())
    diffs = time_col.diff().dropna()
    result["sampling_interval_mode_sec"] = float(diffs.mode().iloc[0]) if len(diffs) else None
    result["sampling_interval_min_sec"] = float(diffs.min()) if len(diffs) else None
    result["sampling_interval_max_sec"] = float(diffs.max()) if len(diffs) else None
    result["n_non_uniform_gaps"] = int((diffs != diffs.mode().iloc[0]).sum()) if len(diffs) else None

    # missing values
    result["n_missing_cells"] = int(df.isna().sum().sum())
    result["cols_with_missing"] = int((df.isna().sum() > 0).sum())

    # duplicate rows / timestamps
    result["n_duplicate_rows"] = int(df.duplicated().sum())
    result["n_duplicate_timestamps"] = int(time_col.duplicated().sum())

    # constant / near-constant metric columns
    metric_cols = [c for c in df.columns if c != "time"]
    stds = df[metric_cols].std(numeric_only=True)
    means = df[metric_cols].mean(numeric_only=True).abs().replace(0, np.nan)
    coef_var = stds / means
    result["n_constant_cols"] = int((stds == 0).sum())
    result["n_near_constant_cols"] = int(((coef_var < 0.01) & (stds != 0)).sum())
    result["constant_col_names"] = ",".join(sorted(stds[stds == 0].index.tolist()))

    # inject_time position relative to data span
    if result["inject_time_exists"]:
        with open(inject_path) as f:
            inject_time = int(f.read().strip())
        result["inject_time"] = inject_time
        in_range = result["time_min"] <= inject_time <= result["time_max"]
        result["inject_time_in_range"] = bool(in_range)
        if in_range and result["time_span_sec"] > 0:
            result["inject_time_frac"] = (inject_time - result["time_min"]) / result["time_span_sec"]
        else:
            result["inject_time_frac"] = None
        result["n_rows_pre_fault"] = int((time_col < inject_time).sum())
        result["n_rows_post_fault"] = int((time_col >= inject_time).sum())

    return result, df


def main():
    args = parse_args()
    data_root = os.path.abspath(os.path.expanduser(args.data_dir))
    out_dir = os.path.abspath(os.path.expanduser(args.out_dir))
    os.makedirs(out_dir, exist_ok=True)

    cases = find_cases(data_root)
    print(f"Found {len(cases)} case directories under {data_root}")

    case_rows = []
    all_columns_seen = defaultdict(int)
    column_frames = []  # (case_id, df) for cross-case column stats
    reference_columns = None
    column_mismatches = []

    for case in cases:
        row, df = inspect_case(case)
        case_rows.append(row)
        if df is not None:
            cols = tuple(df.columns)
            all_columns_seen[cols] += 1
            if reference_columns is None:
                reference_columns = cols
            elif cols != reference_columns:
                column_mismatches.append(f"{case['combo']}/{case['run_id']}")
            column_frames.append((f"{case['combo']}/{case['run_id']}", df))

    case_df = pd.DataFrame(case_rows)
    case_csv_path = os.path.join(out_dir, "case_summary.csv")
    case_df.to_csv(case_csv_path, index=False)
    print(f"Wrote {case_csv_path} ({len(case_df)} rows)")

    # --- per-metric aggregate stats across all cases (scale check) ---
    metric_stats = defaultdict(lambda: dict(mins=[], maxs=[], means=[], stds=[], n_present=0))
    for case_id, df in column_frames:
        for c in df.columns:
            if c == "time":
                continue
            s = df[c]
            metric_stats[c]["n_present"] += 1
            metric_stats[c]["mins"].append(s.min())
            metric_stats[c]["maxs"].append(s.max())
            metric_stats[c]["means"].append(s.mean())
            metric_stats[c]["stds"].append(s.std())

    col_rows = []
    for c, d in metric_stats.items():
        col_rows.append(
            dict(
                column=c,
                n_cases_present=d["n_present"],
                global_min=float(np.nanmin(d["mins"])),
                global_max=float(np.nanmax(d["maxs"])),
                mean_of_means=float(np.nanmean(d["means"])),
                mean_of_stds=float(np.nanmean(d["stds"])),
            )
        )
    col_df = pd.DataFrame(col_rows).sort_values("column")
    col_csv_path = os.path.join(out_dir, "column_stats.csv")
    col_df.to_csv(col_csv_path, index=False)
    print(f"Wrote {col_csv_path} ({len(col_df)} rows)")

    # --- rollup summary ---
    fault_type_counts = case_df["fault_type"].value_counts().to_dict()
    service_counts = case_df["service"].value_counts().to_dict()

    summary = dict(
        data_root=data_root,
        n_cases_found=len(cases),
        n_cases_expected=100,
        combo_dirs=sorted(set(case_df["combo"])),
        n_combo_dirs=case_df["combo"].nunique(),
        services=sorted(set(case_df["service"].dropna())),
        n_services=case_df["service"].nunique(),
        fault_types=sorted(set(case_df["fault_type"].dropna())),
        fault_type_counts=fault_type_counts,
        service_counts=service_counts,
        runs_per_combo=case_df.groupby("combo")["run_id"].nunique().to_dict(),
        all_simple_data_present=bool(case_df["simple_data_exists"].all()),
        all_inject_time_present=bool(case_df["inject_time_exists"].all()),
        n_metric_cols_values=sorted(set(case_df["n_metric_cols"].dropna().astype(int))),
        column_set_consistent=len(all_columns_seen) == 1,
        n_distinct_column_sets=len(all_columns_seen),
        column_mismatch_cases=column_mismatches,
        n_rows_values=sorted(set(case_df["n_rows"].dropna().astype(int))),
        time_span_sec_values=sorted(set(case_df["time_span_sec"].dropna().astype(int))),
        sampling_interval_mode_values=sorted(set(case_df["sampling_interval_mode_sec"].dropna())),
        cases_with_non_uniform_gaps=int((case_df["n_non_uniform_gaps"].fillna(0) > 0).sum()),
        total_missing_cells=int(case_df["n_missing_cells"].sum()),
        cases_with_missing=int((case_df["n_missing_cells"].fillna(0) > 0).sum()),
        cases_with_duplicate_rows=int((case_df["n_duplicate_rows"].fillna(0) > 0).sum()),
        cases_with_duplicate_timestamps=int((case_df["n_duplicate_timestamps"].fillna(0) > 0).sum()),
        cases_with_constant_cols=int((case_df["n_constant_cols"].fillna(0) > 0).sum()),
        max_constant_cols_in_a_case=int(case_df["n_constant_cols"].max()),
        cases_with_near_constant_cols=int((case_df["n_near_constant_cols"].fillna(0) > 0).sum()),
        all_inject_time_in_range=bool(case_df["inject_time_in_range"].fillna(False).all()),
        inject_time_frac_min=float(case_df["inject_time_frac"].min()),
        inject_time_frac_max=float(case_df["inject_time_frac"].max()),
        inject_time_frac_mean=float(case_df["inject_time_frac"].mean()),
        n_rows_pre_fault_min=int(case_df["n_rows_pre_fault"].min()),
        n_rows_post_fault_min=int(case_df["n_rows_post_fault"].min()),
        global_metric_min=float(col_df["global_min"].min()),
        global_metric_max=float(col_df["global_max"].max()),
        scale_ratio_max_over_min_abs=float(
            col_df["global_max"].abs().max() / max(col_df["global_min"].abs().replace(0, np.nan).min(), 1e-12)
        ),
    )

    summary_path = os.path.join(out_dir, "dataset_summary.json")
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)
    print(f"Wrote {summary_path}")

    print("\n--- Key rollup numbers ---")
    for k in [
        "n_cases_found",
        "n_combo_dirs",
        "n_services",
        "fault_types",
        "n_metric_cols_values",
        "column_set_consistent",
        "n_rows_values",
        "time_span_sec_values",
        "sampling_interval_mode_values",
        "total_missing_cells",
        "cases_with_duplicate_rows",
        "cases_with_duplicate_timestamps",
        "cases_with_constant_cols",
        "all_inject_time_in_range",
        "inject_time_frac_min",
        "inject_time_frac_max",
    ]:
        print(f"{k}: {summary[k]}")


if __name__ == "__main__":
    main()
