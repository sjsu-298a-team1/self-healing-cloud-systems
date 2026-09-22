"""
Model 1 dataset inspection, part 2: schema consistency + missingness/constant-column
deep dive for the BARO Online Boutique artifact (fse-ob).

Strictly read-only. Does not modify, impute, delete, or normalize anything under the
BARO data directory. Builds on inspect_dataset.py (run first, or this script will
re-derive everything it needs directly from simple_data.csv).

Usage:
    python3 inspect_schema_and_missingness.py --data-dir <BARO_DATA_DIR> [--out-dir <OUT_DIR>]

    <BARO_DATA_DIR> is the path to BARO's data/fse-ob directory on your machine
    (e.g. the data/fse-ob folder inside a local clone of github.com/phamquiluan/baro).
    <OUT_DIR> defaults to this script's own directory.

Outputs (written to --out-dir):
    column_presence.csv        one row per column: which of the 100 cases has it,
                                broken down by service and fault_type
    constant_columns.csv       one row per (case, constant column) pair
    missing_cells_detail.csv   one row per (case, column) pair with >0 missing,
                                split into pre-fault / post-fault counts
    schema_report.json         rollup answering the questions in this run
"""
import argparse
import glob
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


def parse_case_dir(name):
    for ft in EXPECTED_FAULT_TYPES:
        if name.endswith("_" + ft):
            return name[: -len(ft) - 1], ft
    return None, None


def find_cases(data_root):
    cases = []
    for combo_dir in sorted(glob.glob(os.path.join(data_root, "*"))):
        if not os.path.isdir(combo_dir):
            continue
        combo = os.path.basename(combo_dir)
        service, fault_type = parse_case_dir(combo)
        for run_dir in sorted(glob.glob(os.path.join(combo_dir, "*"))):
            if not os.path.isdir(run_dir):
                continue
            cases.append(
                dict(
                    combo=combo,
                    service=service,
                    fault_type=fault_type,
                    run_id=os.path.basename(run_dir),
                    path=run_dir,
                )
            )
    return cases


def main():
    args = parse_args()
    data_root = os.path.abspath(os.path.expanduser(args.data_dir))
    out_dir = os.path.abspath(os.path.expanduser(args.out_dir))
    os.makedirs(out_dir, exist_ok=True)

    cases = find_cases(data_root)
    n_cases = len(cases)
    print(f"Found {n_cases} cases under {data_root}")

    # --- load all simple_data.csv frames + inject_time, keyed by case id ---
    loaded = {}
    for case in cases:
        cid = f"{case['combo']}/{case['run_id']}"
        sd_path = os.path.join(case["path"], "simple_data.csv")
        inj_path = os.path.join(case["path"], "inject_time.txt")
        if not os.path.exists(sd_path):
            continue
        df = pd.read_csv(sd_path)
        inject_time = None
        if os.path.exists(inj_path):
            with open(inj_path) as f:
                inject_time = int(f.read().strip())
        loaded[cid] = dict(case=case, df=df, inject_time=inject_time)

    # =========================================================
    # 1. union / intersection of columns; presence matrix
    # =========================================================
    all_cols = set()
    col_case_presence = defaultdict(set)  # column -> set of case ids that have it
    for cid, rec in loaded.items():
        cols = set(rec["df"].columns)
        all_cols |= cols
        for c in cols:
            col_case_presence[c].add(cid)

    union_cols = sorted(all_cols)
    intersection_cols = sorted(c for c in all_cols if len(col_case_presence[c]) == n_cases)
    varying_cols = sorted(c for c in all_cols if len(col_case_presence[c]) != n_cases)

    print(f"Union columns: {len(union_cols)}")
    print(f"Intersection columns (present in all {n_cases} cases): {len(intersection_cols)}")
    print(f"Varying-presence columns: {len(varying_cols)}")

    # metadata vs telemetry: "time" is the only non-metric column in simple_data.csv
    metadata_cols = [c for c in union_cols if c == "time"]
    telemetry_union = [c for c in union_cols if c != "time"]
    telemetry_intersection = [c for c in intersection_cols if c != "time"]

    # presence table broken down by service / fault_type for each varying column
    presence_rows = []
    for c in union_cols:
        present_ids = col_case_presence[c]
        n_present = len(present_ids)
        present_services = sorted({loaded[cid]["case"]["service"] for cid in present_ids})
        present_faults = sorted({loaded[cid]["case"]["fault_type"] for cid in present_ids})
        missing_ids = sorted(set(loaded.keys()) - present_ids)
        presence_rows.append(
            dict(
                column=c,
                is_metadata=(c == "time"),
                n_cases_present=n_present,
                n_cases_total=n_cases,
                present_in_all=(n_present == n_cases),
                services_present=",".join(present_services),
                fault_types_present=",".join(present_faults),
                missing_from_cases=",".join(missing_ids) if n_present != n_cases else "",
            )
        )
    presence_df = pd.DataFrame(presence_rows).sort_values(["present_in_all", "column"])
    presence_df.to_csv(os.path.join(out_dir, "column_presence.csv"), index=False)

    # For varying columns: check whether they are genuinely absent from the file
    # (not just present-but-all-NaN under a different guise)
    varying_detail = []
    for c in varying_cols:
        present_ids = col_case_presence[c]
        missing_ids = sorted(set(loaded.keys()) - present_ids)
        varying_detail.append(
            dict(
                column=c,
                n_present=len(present_ids),
                n_missing=len(missing_ids),
                missing_cases=missing_ids,
            )
        )

    # =========================================================
    # 2. constant / near-constant columns, broken down
    # =========================================================
    constant_rows = []
    for cid, rec in loaded.items():
        df = rec["df"]
        case = rec["case"]
        metric_cols = [c for c in df.columns if c != "time"]
        stds = df[metric_cols].std(numeric_only=True)
        means = df[metric_cols].mean(numeric_only=True)
        const_cols = stds[stds == 0].index.tolist()
        for c in const_cols:
            constant_rows.append(
                dict(
                    case=cid,
                    service=case["service"],
                    fault_type=case["fault_type"],
                    run_id=case["run_id"],
                    column=c,
                    constant_value=float(means[c]) if pd.notna(means[c]) else None,
                )
            )
    constant_df = pd.DataFrame(constant_rows)
    constant_df.to_csv(os.path.join(out_dir, "constant_columns.csv"), index=False)

    const_col_summary = {}
    if len(constant_df):
        for c, grp in constant_df.groupby("column"):
            const_col_summary[c] = dict(
                n_cases=len(grp),
                services=sorted(grp["service"].unique().tolist()),
                fault_types=sorted(grp["fault_type"].unique().tolist()),
                fraction_of_all_cases=len(grp) / n_cases,
                always_same_value=bool(grp["constant_value"].nunique(dropna=False) <= 1),
                example_value=float(grp["constant_value"].iloc[0]) if pd.notna(grp["constant_value"].iloc[0]) else None,
            )

    # columns constant in EVERY case (candidates for outright removal)
    cols_constant_everywhere = sorted(
        c for c, d in const_col_summary.items() if d["n_cases"] == n_cases
    )
    # columns constant only for specific fault types (may be legitimately informative
    # elsewhere, e.g. a metric that's flat under CPU faults but moves under DELAY faults)
    cols_constant_sometimes = sorted(
        c for c, d in const_col_summary.items() if 0 < d["n_cases"] < n_cases
    )

    # =========================================================
    # 3. missing cells: which column, which case, pre/post fault split
    # =========================================================
    missing_rows = []
    total_missing = 0
    missing_pre_total = 0
    missing_post_total = 0
    for cid, rec in loaded.items():
        df = rec["df"]
        inject_time = rec["inject_time"]
        na_counts = df.isna().sum()
        na_cols = na_counts[na_counts > 0]
        if len(na_cols) == 0:
            continue
        time_col = df["time"]
        for col, n_na in na_cols.items():
            mask = df[col].isna()
            if inject_time is not None:
                n_pre = int((mask & (time_col < inject_time)).sum())
                n_post = int((mask & (time_col >= inject_time)).sum())
            else:
                n_pre = n_post = None
            missing_rows.append(
                dict(
                    case=cid,
                    service=rec["case"]["service"],
                    fault_type=rec["case"]["fault_type"],
                    column=col,
                    n_missing=int(n_na),
                    n_missing_pre_fault=n_pre,
                    n_missing_post_fault=n_post,
                    first_missing_row_idx=int(np.argmax(mask.values)) if mask.any() else None,
                    last_missing_row_idx=int(len(mask) - 1 - np.argmax(mask.values[::-1])) if mask.any() else None,
                )
            )
            total_missing += int(n_na)
            if n_pre is not None:
                missing_pre_total += n_pre
                missing_post_total += n_post

    missing_df = pd.DataFrame(missing_rows)
    missing_df.to_csv(os.path.join(out_dir, "missing_cells_detail.csv"), index=False)

    missing_by_column = {}
    if len(missing_df):
        for c, grp in missing_df.groupby("column"):
            missing_by_column[c] = dict(
                n_cases_affected=len(grp),
                total_missing=int(grp["n_missing"].sum()),
                total_missing_pre_fault=int(grp["n_missing_pre_fault"].sum()),
                total_missing_post_fault=int(grp["n_missing_post_fault"].sum()),
            )

    # is missingness systematic (same rows/positions across cases) or scattered?
    # check: for each affected column, are the missing row indices clustered at the
    # start of the series (e.g. warm-up before metric collection begins)?
    positional_pattern = {}
    for c, grp in (missing_df.groupby("column") if len(missing_df) else []):
        first_idxs = grp["first_missing_row_idx"].dropna().tolist()
        positional_pattern[c] = dict(
            first_missing_row_idx_values=sorted(set(int(x) for x in first_idxs)),
        )

    # =========================================================
    # rollup
    # =========================================================
    report = dict(
        n_cases=n_cases,
        union_column_count=len(union_cols),
        intersection_column_count=len(intersection_cols),
        telemetry_union_count=len(telemetry_union),
        telemetry_intersection_count=len(telemetry_intersection),
        metadata_columns=metadata_cols,
        varying_columns=varying_detail,
        cols_constant_everywhere=cols_constant_everywhere,
        cols_constant_sometimes=cols_constant_sometimes,
        constant_column_summary=const_col_summary,
        total_missing_cells=total_missing,
        missing_pre_fault_total=missing_pre_total,
        missing_post_fault_total=missing_post_total,
        missing_by_column=missing_by_column,
        missing_positional_pattern=positional_pattern,
    )
    with open(os.path.join(out_dir, "schema_report.json"), "w") as f:
        json.dump(report, f, indent=2, default=str)

    # =========================================================
    # console summary
    # =========================================================
    print("\n=== Column presence ===")
    print(f"Union: {len(union_cols)} columns (incl. time)")
    print(f"Intersection (present in all {n_cases} cases): {len(intersection_cols)} columns")
    print(f"Telemetry-only union: {len(telemetry_union)}, telemetry-only intersection: {len(telemetry_intersection)}")
    print("Varying columns (not present in all cases):")
    for d in varying_detail:
        print(f"  {d['column']}: present in {d['n_present']}/{n_cases} cases; missing from {d['n_missing']} cases")

    print("\n=== Constant columns ===")
    print(f"Columns constant in EVERY case ({len(cols_constant_everywhere)}): {cols_constant_everywhere}")
    print(f"Columns constant in SOME cases only ({len(cols_constant_sometimes)}):")
    for c in cols_constant_sometimes:
        d = const_col_summary[c]
        print(f"  {c}: constant in {d['n_cases']}/{n_cases} cases, fault_types={d['fault_types']}, services={d['services']}")

    print("\n=== Missing cells ===")
    print(f"Total missing cells: {total_missing} (pre-fault: {missing_pre_total}, post-fault: {missing_post_total})")
    for c, d in missing_by_column.items():
        print(f"  {c}: {d['total_missing']} missing across {d['n_cases_affected']} cases "
              f"(pre={d['total_missing_pre_fault']}, post={d['total_missing_post_fault']})")


if __name__ == "__main__":
    main()
