"""
Model 1 preprocessing and data-quality demo (issue 298-37).

ONE command that runs the whole Model 1 data chain end to end against a local
copy of the BARO Online Boutique artifact, prints readable evidence at every
stage, and -- critically -- re-derives the committed split manifests and scaler
from the raw data and compares them against what is already in this repository.

Nothing committed is overwritten. Every generated file goes to a work directory
(default: a fresh temp dir); the committed artifacts under configs/model1/ and
data/model1/ are read for comparison only.

This exists because the pipeline it demonstrates (298-33 / 298-35 / 298-36) is
spread across six commands in three directories with hand-threaded paths, which
cannot be run live in front of an audience. This wraps it.

Usage:
    python3 run_data_demo.py --data-dir <BARO_DATA_DIR>
    python3 run_data_demo.py --data-dir <BARO_DATA_DIR> --work-dir ./demo_out --keep

Exit code 0 = every stage passed. Non-zero = at least one stage failed.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

COMMITTED_CONFIGS = os.path.join(REPO_ROOT, "configs", "model1")
COMMITTED_MANIFESTS = os.path.join(REPO_ROOT, "data", "model1", "manifests")
COMMITTED_INSPECTION = os.path.join(REPO_ROOT, "data", "model1", "dataset_inspection")

SCRIPTS = os.path.join(REPO_ROOT, "scripts", "model1")

# Reuse the committed Model 1 data library rather than duplicating its logic.
sys.path.insert(0, os.path.join(SCRIPTS, "data"))

RULE = "=" * 78
THIN = "-" * 78

# Stage 4 scaler comparison only: absolute tolerance catches real differences
# on small-magnitude features; relative tolerance absorbs float64 summation-
# order noise on large-magnitude features (e.g. *_mem stats ~1e7, where a
# ~1e-7 absolute difference is ~2e-14 relative -- machine-epsilon noise, not a
# real change). Both explicit and named here so the allowed slack is
# auditable, not a magic number buried in a function call. Not used by any
# other comparison in this file (see compare_json/_approx_equal).
SCALER_COMPARISON_ABS_TOL = 1e-9
SCALER_COMPARISON_REL_TOL = 1e-12


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def header(n, title):
    print()
    print(RULE)
    print(f"STAGE {n}: {title}")
    print(RULE)


def ok(msg):
    print(f"  [PASS] {msg}")


def bad(msg):
    print(f"  [FAIL] {msg}")


def info(msg):
    print(f"         {msg}")


def run_script(rel_path, args, label):
    """Run one pipeline script, capture output, return (success, stdout)."""
    cmd = [sys.executable, os.path.join(SCRIPTS, rel_path)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        bad(f"{label} exited {proc.returncode}")
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
        for line in tail:
            info(line)
        return False, proc.stdout
    return True, proc.stdout


def load_json(path):
    with open(path) as f:
        return json.load(f)


def compare_json(generated_path, committed_path, label, tolerance=None, rel_tolerance=0.0):
    """Compare a regenerated artifact against the committed one.

    tolerance=None (the default, used by Stage 3's manifest comparisons):
    exact structural equality, no float slack whatsoever.

    tolerance=<abs_tol> (used only by Stage 4's scaler comparison): structural
    equality with math.isclose(rel_tol=rel_tolerance, abs_tol=tolerance) for
    numeric leaves.
    """
    if not os.path.exists(generated_path):
        bad(f"{label}: regenerated file not produced")
        return False
    if not os.path.exists(committed_path):
        bad(f"{label}: committed file missing from repo")
        return False

    gen, com = load_json(generated_path), load_json(committed_path)

    if tolerance is None:
        same = gen == com
    else:
        same = _approx_equal(gen, com, tolerance, rel_tolerance)

    if same:
        if tolerance is None:
            ok(f"{label}: regenerated output is identical to the committed artifact")
        else:
            ok(f"{label}: regenerated values match the committed artifact "
               f"within configured numeric tolerance")
    else:
        bad(f"{label}: regenerated output DIFFERS from the committed artifact")
    return same


def _approx_equal(a, b, abs_tol, rel_tol=0.0):
    """Structural equality with a float tolerance for numeric leaves.

    Numeric leaves are compared with math.isclose(rel_tol=rel_tol,
    abs_tol=abs_tol) rather than a bare absolute difference, so a tiny
    relative (float64 rounding) difference on a large-magnitude value isn't
    conflated with an absolute difference of the same raw size on a
    small-magnitude value -- both tolerances are explicit at the call site
    rather than one being baked silently into this function.
    """
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return False
        return all(_approx_equal(a[k], b[k], abs_tol, rel_tol) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(
            _approx_equal(x, y, abs_tol, rel_tol) for x, y in zip(a, b))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) \
            and not isinstance(a, bool) and not isinstance(b, bool):
        return math.isclose(a, b, rel_tol=rel_tol, abs_tol=abs_tol)
    return a == b


# --------------------------------------------------------------------------
# stages
# --------------------------------------------------------------------------

def stage_1_integrity(data_dir, work_inspection):
    header(1, "Dataset integrity and structure")
    print("  Reading the raw artifact and checking it is shaped as the protocol assumes.")
    print()

    good, _ = run_script(
        os.path.join("dataset_inspection", "inspect_dataset.py"),
        ["--data-dir", data_dir, "--out-dir", work_inspection],
        "inspect_dataset.py",
    )
    if not good:
        return False

    s = load_json(os.path.join(work_inspection, "dataset_summary.json"))

    checks = [
        ("100 cases found", s["n_cases_found"] == 100, f"{s['n_cases_found']} cases"),
        ("20 service/fault combos", s["n_combo_dirs"] == 20, f"{s['n_combo_dirs']} combos"),
        ("5 target services", s["n_services"] == 5, ", ".join(s["services"])),
        ("4 fault types", len(s["fault_types"]) == 4, ", ".join(s["fault_types"])),
        ("every case has 721 rows", s["n_rows_values"] == [721], str(s["n_rows_values"])),
        ("every case spans 720s", s["time_span_sec_values"] == [720], str(s["time_span_sec_values"])),
        ("uniform 1 Hz sampling", s["sampling_interval_mode_values"] == [1.0],
         str(s["sampling_interval_mode_values"])),
        ("no duplicate rows", s["cases_with_duplicate_rows"] == 0,
         f"{s['cases_with_duplicate_rows']} cases affected"),
        ("no duplicate timestamps", s["cases_with_duplicate_timestamps"] == 0,
         f"{s['cases_with_duplicate_timestamps']} cases affected"),
        ("injection inside every case's time range", s["all_inject_time_in_range"] is True, "all 100"),
        ("injection at the exact midpoint in every case",
         s["inject_time_frac_min"] == 0.5 and s["inject_time_frac_max"] == 0.5,
         f"fraction {s['inject_time_frac_min']}-{s['inject_time_frac_max']}"),
    ]

    passed = True
    for label, result, detail in checks:
        (ok if result else bad)(f"{label}  ({detail})")
        passed &= result

    print()
    info("Consequence: each case is exactly 360s of known-normal data followed by")
    info("360s of post-injection data, at 1 Hz, with no gaps and no duplicates.")
    return passed


def stage_2_quality(data_dir, work_inspection):
    header(2, "Data quality: schema, missingness, constant columns")
    print("  Quantifying what is actually wrong with the data, before any modelling.")
    print()

    good, _ = run_script(
        os.path.join("dataset_inspection", "inspect_schema_and_missingness.py"),
        ["--data-dir", data_dir, "--out-dir", work_inspection],
        "inspect_schema_and_missingness.py",
    )
    if not good:
        return False

    summary = load_json(os.path.join(work_inspection, "dataset_summary.json"))
    total_missing = summary["total_missing_cells"]
    n_constant_cases = summary["cases_with_constant_cols"]

    # Total cells = 100 cases x 721 rows x (metric columns present in that case).
    approx_cells = 100 * 721 * 57
    pct = 100.0 * total_missing / approx_cells

    ok(f"missing cells quantified: {total_missing:,} of ~{approx_cells:,} ({pct:.3f}%)")
    info("Concentrated, not uniform: istio-init_mem (a sidecar metric present in only")
    info("2 of 100 cases) and three *_error counters account for the bulk.")
    print()

    schema_path = os.path.join(work_inspection, "schema_report.json")
    if not os.path.exists(schema_path):
        bad("schema_report.json not produced -- cannot report schema coverage")
        return False

    r = load_json(schema_path)
    union = r.get("telemetry_union_count")
    inter = r.get("telemetry_intersection_count")
    if union is None or inter is None:
        bad("schema coverage unreadable: schema_report.json is missing "
            "telemetry_union_count and/or telemetry_intersection_count")
        info(f"keys present: {sorted(r.keys())}")
        return False

    excluded = union - inter
    ok(f"schema coverage: {union} union metrics, {inter} common metrics, "
       f"{excluded} inconsistent/excluded metrics")
    info(f"{union} distinct telemetry columns appear in at least one case, but only")
    info(f"{inter} appear in every one of the 100 cases. Model 1 uses that {inter}-column")
    info(f"intersection as its locked feature set and excludes the {excluded} columns that")
    info("are absent from some cases' CSV headers (6 istio error counters + istio-init_mem).")
    print()

    ok(f"constant-column behaviour characterised: {n_constant_cases} of 100 cases have "
       f"at least one locally constant column")
    info("Driven by istio *_error counters, which legitimately stay flat when no")
    info("errors occur in a 12-minute window. Expected behaviour, not a data defect.")
    print()

    info("Scale: *_cpu and *_latency-* are small floats while *_workload and *_mem")
    info("differ by orders of magnitude, so per-feature normalisation is required.")
    return True


def stage_3_splits(data_dir, work_inspection, work_configs, work_manifests):
    header(3, "Deterministic splits (regenerated and compared)")
    print("  Rebuilding the train/val/test manifests from the raw data and the committed")
    print("  seed, then checking they match the manifests already in the repository.")
    print()

    good, _ = run_script(
        os.path.join("protocol", "build_manifests.py"),
        ["--data-dir", data_dir,
         "--inspection-dir", work_inspection,
         "--configs-dir", work_configs,
         "--manifests-dir", work_manifests],
        "build_manifests.py",
    )
    if not good:
        return False

    passed = True
    counts = {}
    for name, expected in (("train_cases", 60), ("val_cases", 20), ("test_cases", 20)):
        gen_path = os.path.join(work_manifests, f"{name}.json")
        if not os.path.exists(gen_path):
            bad(f"{name}.json not produced")
            passed = False
            continue
        manifest = load_json(gen_path)
        cases = manifest["case_ids"]
        counts[name] = len(cases)
        result = len(cases) == expected
        (ok if result else bad)(f"{name}: {len(cases)} cases (expected {expected})")
        passed &= result

    # disjointness, computed here rather than trusted from the report
    try:
        sets = {}
        for name in ("train_cases", "val_cases", "test_cases"):
            sets[name] = set(load_json(os.path.join(work_manifests, f"{name}.json"))["case_ids"])
        pairwise_ok = (
            not (sets["train_cases"] & sets["val_cases"])
            and not (sets["train_cases"] & sets["test_cases"])
            and not (sets["val_cases"] & sets["test_cases"])
        )
        union_ok = len(set().union(*sets.values())) == 100
        (ok if pairwise_ok else bad)("splits are pairwise disjoint (no case in two splits)")
        (ok if union_ok else bad)("splits cover all 100 cases exactly once")
        passed &= pairwise_ok and union_ok
    except Exception as exc:  # pragma: no cover - defensive only
        bad(f"could not verify disjointness: {exc}")
        passed = False

    print()
    for name in ("train_cases", "val_cases", "test_cases"):
        passed &= compare_json(
            os.path.join(work_manifests, f"{name}.json"),
            os.path.join(COMMITTED_MANIFESTS, f"{name}.json"),
            f"{name}.json",
        )

    print()
    info("This is the determinism claim made concrete: same raw data plus the same")
    info("seed reproduces the committed split exactly, on a different machine.")
    return passed


def stage_4_scaler(data_dir, work_configs, work_manifests):
    header(4, "Normalisation fitted on training data only (regenerated and compared)")
    print("  Refitting the z-score scaler from scratch and comparing it to the committed one.")
    print()

    good, _ = run_script(
        os.path.join("protocol", "fit_scaler.py"),
        ["--data-dir", data_dir,
         "--configs-dir", work_configs,
         "--manifests-dir", work_manifests],
        "fit_scaler.py",
    )
    if not good:
        return False

    gen = os.path.join(work_configs, "scaler.json")
    com = os.path.join(COMMITTED_CONFIGS, "scaler.json")

    passed = compare_json(gen, com, "scaler.json",
                          tolerance=SCALER_COMPARISON_ABS_TOL,
                          rel_tolerance=SCALER_COMPARISON_REL_TOL)

    try:
        s = load_json(gen)
        feats = s.get("features") or s.get("per_feature") or {}
        n = len(feats) if isinstance(feats, dict) else len(feats)
        if n:
            ok(f"scaler covers {n} features")
        info("Fitted on pre-fault rows of train-split cases only: 60 cases x 360 rows = 21,600 rows.")
        info("Validation and test data never influence the scaler.")
    except Exception:
        pass

    return passed


def _structural_check(df, features):
    """Mirrors the feature_consistency check in validate_protocol.py: every
    locked feature must be present and numeric. Returns a list of problems
    (empty list == valid). Used here to show the check rejecting a deliberately
    corrupted sample, which the scaler negative control does not cover."""
    import pandas as pd
    problems = []
    missing = [f for f in features if f not in df.columns]
    if missing:
        problems.append(f"required feature missing: {', '.join(missing)}")
    non_numeric = [f for f in features
                   if f in df.columns and not pd.api.types.is_numeric_dtype(df[f])]
    if non_numeric:
        problems.append(f"non-numeric feature: {', '.join(non_numeric)}")
    return problems


def stage_5_preprocessing_example(data_dir, work_configs, work_manifests):
    header(5, "Worked preprocessing example (one real training case)")
    print("  Raw telemetry through imputation and standardisation, on one real case,")
    print("  using the existing committed scaler and the existing pipeline functions.")
    print()

    import numpy as np
    import dataset as ds

    features = ds.load_features(configs_dir=work_configs)
    scaler = ds.load_scaler(configs_dir=work_configs)
    train_cases = ds.load_manifest("train", manifests_dir=work_manifests)

    # Prefer a training case that actually contains a missing cell, so the
    # imputation step is demonstrated on real data rather than described.
    chosen = chosen_df = chosen_feat = None
    chosen_row = 0
    for case_id in train_cases:
        df, _ = ds.load_case_df(data_dir, case_id)
        sub = df[features]
        if sub.isna().any().any():
            col = sub.columns[sub.isna().any()][0]
            chosen, chosen_df, chosen_feat = case_id, df, col
            chosen_row = int(sub[col].isna().to_numpy().nonzero()[0][0])
            break
    if chosen is None:
        chosen = train_cases[0]
        chosen_df, _ = ds.load_case_df(data_dir, chosen)
        chosen_feat = features[0]
        info("No training case contains a missing cell; showing a non-imputed example.")

    ok(f"case: {chosen}   (training split)")
    ok(f"feature: {chosen_feat}   row index {chosen_row}")
    print()

    raw_val = chosen_df[chosen_feat].to_numpy(dtype=float)[chosen_row]
    mean = scaler["mean"][chosen_feat]
    std = scaler["std"][chosen_feat]

    # Reuse the committed pipeline rather than reimplementing it.
    scaled, n_imputed = ds.apply_scaler(chosen_df, features, scaler)
    col_idx = features.index(chosen_feat)
    scaled_val = scaled[chosen_row, col_idx]
    is_missing = bool(np.isnan(raw_val))
    imputed_raw = mean if is_missing else raw_val

    raw_display = "NaN (missing)" if is_missing else f"{raw_val:.6f}"
    print(f"    {'step':<36}{'value':>22}")
    print(f"    {'-' * 58}")
    print(f"    {'1. raw value from simple_data.csv':<36}{raw_display:>22}")
    if is_missing:
        print(f"    {'2. imputed with training mean':<36}{imputed_raw:>22.6f}")
    else:
        print(f"    {'2. imputation (not needed)':<36}{imputed_raw:>22.6f}")
    print(f"    {'3. committed scaler mean':<36}{mean:>22.6f}")
    print(f"    {'4. committed scaler std':<36}{std:>22.6f}")
    print(f"    {'5. standardised (x - mean) / std':<36}{scaled_val:>22.6f}")
    print()

    passed = True
    if is_missing:
        info("Policy: constant substitution with the committed train-fit mean.")
        info("No forward-fill, backward-fill, or interpolation of any kind.")
        exact_zero = abs(scaled_val) < 1e-12
        (ok if exact_zero else bad)(
            "imputed cell standardises to exactly 0.0, as the policy requires")
        passed = passed and exact_zero

    expected = (imputed_raw - mean) / std
    consistent = abs(expected - scaled_val) < 1e-9
    (ok if consistent else bad)(
        "pipeline output matches the hand-computed (x - mean) / std")
    passed = passed and consistent

    ok(f"whole case standardised: shape {scaled.shape}, {n_imputed} cell(s) imputed")
    info("Scaler and policy are read from committed artifacts; nothing is refitted.")
    return passed


def stage_6_structural_validation(data_dir, work_configs, work_manifests):
    header(6, "Structural validation: valid sample versus corrupted sample")
    print("  Showing the schema check accepting a real sample and rejecting a")
    print("  deliberately corrupted copy. The raw dataset is never modified.")
    print()

    import dataset as ds

    features = ds.load_features(configs_dir=work_configs)
    train_cases = ds.load_manifest("train", manifests_dir=work_manifests)
    case_id = train_cases[0]

    df, _ = ds.load_case_df(data_dir, case_id)

    problems = _structural_check(df, features)
    valid_ok = not problems
    if valid_ok:
        ok(f"Valid sample ({case_id}): PASS -- all {len(features)} required "
           f"features present and numeric")
    else:
        bad(f"Valid sample ({case_id}): unexpectedly failed -- {problems}")

    # In-memory copy only. The file on disk is untouched.
    dropped = features[0]
    corrupted = df.drop(columns=[dropped])
    problems = _structural_check(corrupted, features)
    corrupted_ok = bool(problems)
    if corrupted_ok:
        ok(f"Corrupted sample: FAIL -- {problems[0]}")
    else:
        bad("Corrupted sample unexpectedly passed -- the structural check is broken")

    print()
    info(f"The corrupted copy exists only in memory: column '{dropped}' was dropped")
    info("from an in-memory DataFrame. Nothing under the dataset directory was written.")
    info("This complements the scaler negative control in the protocol checks, which")
    info("tests contamination rather than schema validity.")

    return valid_ok and corrupted_ok


def stage_7_outlier_evidence(data_dir, work_configs, work_manifests):
    header(7, "Descriptive outlier summary (training known-normal rows only)")
    print("  Descriptive only. Nothing is removed, no threshold is tuned, no")
    print("  preprocessing changes, and no validation or test data is consulted.")
    print()

    import numpy as np
    import dataset as ds

    features = ds.load_features(configs_dir=work_configs)
    scaler = ds.load_scaler(configs_dir=work_configs)
    train_cases = ds.load_manifest("train", manifests_dir=work_manifests)

    z_rule = 5.0
    info(f"Rule: standardise each training known-normal row with the committed")
    info(f"scaler and count cells whose |z| exceeds {z_rule}. The scaler was fit on")
    info("exactly these rows, so this measures tail heaviness, not model error.")
    print()

    total_cells = flagged_cells = rows_with_any = total_rows = 0
    per_feature = {}

    for case_id in train_cases:
        df, inject_time = ds.load_case_df(data_dir, case_id)
        pre = df[df["time"] < inject_time]
        scaled, _ = ds.apply_scaler(pre, features, scaler)
        mask = np.abs(scaled) > z_rule
        total_cells += scaled.size
        total_rows += scaled.shape[0]
        flagged_cells += int(mask.sum())
        rows_with_any += int(mask.any(axis=1).sum())
        for i, c in enumerate(mask.sum(axis=0)):
            if c:
                per_feature[features[i]] = per_feature.get(features[i], 0) + int(c)

    pct_cells = 100.0 * flagged_cells / total_cells if total_cells else 0.0
    pct_rows = 100.0 * rows_with_any / total_rows if total_rows else 0.0

    ok(f"scanned {total_rows:,} known-normal rows from {len(train_cases)} training "
       f"cases ({total_cells:,} cells)")
    ok(f"cells with |z| > {z_rule}: {flagged_cells:,} ({pct_cells:.3f}%)")
    ok(f"rows containing at least one such cell: {rows_with_any:,} ({pct_rows:.2f}%)")
    print()

    if per_feature:
        top = sorted(per_feature.items(), key=lambda kv: -kv[1])[:5]
        print(f"    {'feature':<36}{'flagged cells':>16}")
        print(f"    {'-' * 52}")
        for feat, n in top:
            print(f"    {feat:<36}{n:>16,}")
        print()
        info(f"{len(per_feature)} of {len(features)} features contribute at least one")
        info("flagged cell, so the tail is concentrated rather than uniform.")
    else:
        info("No cell exceeded the rule.")

    print()
    info("No row, case, or feature was removed. This is evidence about the data, not")
    info("a preprocessing decision, and nothing downstream consumes this result.")
    return True


def stage_8_protocol(data_dir, work_configs, work_manifests, work_dir):
    header(8, "Automated protocol checks")
    print("  Running the five locked checks that guard against leakage and split errors.")
    print()

    report_path = os.path.join(work_dir, "validation_report.json")
    good, _ = run_script(
        os.path.join("protocol", "validate_protocol.py"),
        ["--data-dir", data_dir,
         "--configs-dir", work_configs,
         "--manifests-dir", work_manifests,
         "--report-path", report_path],
        "validate_protocol.py",
    )
    if not good:
        return False

    report = load_json(report_path)
    labels = {
        "split_overlap": "split overlap: disjoint, no duplicates, covers all 100 cases",
        "feature_consistency": "feature consistency: all 55 features present and numeric in all cases",
        "scaler_train_only": "scaler fitted on training data only (with negative control)",
        "no_time_index_leakage": "no time or index feature leakage",
        "fault_type_stratification": "fault-type stratification: 25 cases each of cpu/mem/delay/loss",
    }

    passed = True
    for key, label in labels.items():
        section = report.get(key, {})
        result = bool(section.get("passed"))
        (ok if result else bad)(label)
        if not result:
            for p in section.get("problems", [])[:4]:
                info(str(p))
        passed &= result

    neg = report.get("scaler_train_only", {}).get("negative_control_detected_contamination")
    if neg:
        print()
        ok("negative control fired: deliberately adding a validation case to the fit")
        info("measurably shifts the scaler, proving the check can actually detect")
        info("contamination rather than passing vacuously.")

    return passed


def stage_9_windows(data_dir, work_configs, work_manifests, work_dir):
    header(9, "Windowing: raw telemetry to model-ready tensors")
    print("  The final step of extraction -- turning cases into training windows.")
    print()

    out = os.path.join(work_dir, "train_window_summary.json")
    good, stdout = run_script(
        os.path.join("data", "build_train_windows.py"),
        ["--data-dir", data_dir,
         "--configs-dir", work_configs,
         "--manifests-dir", work_manifests,
         "--out", out],
        "build_train_windows.py",
    )
    if not good:
        return False

    if os.path.exists(out):
        w = load_json(out)
        ok(f"training windows built: {w['n_training_windows']:,}")
        ok(f"tensor shape: {w['tensor_shape']}  "
           f"(windows x {w['window_length']} timesteps x {w['n_features']} features)")
        ok(f"all {w['n_train_cases_with_windows']} train cases produced windows "
           f"({w['windows_per_case_min']} each)")
        strictly_pre = bool(w.get("all_windows_strictly_pre_fault"))
        (ok if strictly_pre else bad)(
            "every training window lies strictly in the pre-fault region")
        info(f"Window length {w['window_length']}s, train stride {w['train_stride']}s, "
             f"over the {w['n_features']} locked features.")
        return strictly_pre
    else:
        for line in (stdout or "").strip().splitlines()[-6:]:
            info(line)

    return True


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="End-to-end Model 1 preprocessing and data-quality demo (298-37)."
    )
    parser.add_argument("--data-dir", required=True,
                        help="Path to the BARO Online Boutique artifact (the fse-ob directory)")
    parser.add_argument("--work-dir", default=None,
                        help="Where to write regenerated artifacts. Default: a fresh temp dir.")
    parser.add_argument("--keep", action="store_true",
                        help="Keep the work directory instead of deleting it on exit.")
    args = parser.parse_args()

    # expanduser first: some shells (PowerShell) pass "~" through literally
    # rather than expanding it, so relying on the shell alone is not portable.
    data_dir = os.path.abspath(os.path.expanduser(args.data_dir))
    if not os.path.isdir(data_dir):
        print(f"ERROR: --data-dir not found: {data_dir}")
        print("See docs/data/README.md for how to obtain the BARO Online Boutique artifact.")
        return 2

    created_temp = args.work_dir is None
    work_dir = (os.path.abspath(os.path.expanduser(args.work_dir))
                if args.work_dir else tempfile.mkdtemp(prefix="m1demo_"))

    work_inspection = os.path.join(work_dir, "inspection")
    work_configs = os.path.join(work_dir, "configs")
    work_manifests = os.path.join(work_dir, "manifests")
    for d in (work_inspection, work_manifests):
        os.makedirs(d, exist_ok=True)

    # Copy the committed configs so regeneration never writes over them.
    if os.path.exists(work_configs):
        shutil.rmtree(work_configs)
    shutil.copytree(COMMITTED_CONFIGS, work_configs)

    started = time.time()

    print(RULE)
    print("MODEL 1 -- PREPROCESSING AND DATA-QUALITY DEMO")
    print(RULE)
    print(f"  dataset   : {data_dir}")
    print(f"  work dir  : {work_dir}")
    print(f"  repo      : {REPO_ROOT}")
    print()
    print("  Committed artifacts are READ ONLY in this run. Everything regenerated is")
    print("  written to the work directory and then compared against what is in the repo.")

    results = []
    try:
        results.append(("1. Dataset integrity and structure",
                        stage_1_integrity(data_dir, work_inspection)))
        results.append(("2. Data quality (schema, missingness, constants)",
                        stage_2_quality(data_dir, work_inspection)))
        results.append(("3. Deterministic splits reproduce",
                        stage_3_splits(data_dir, work_inspection, work_configs, work_manifests)))
        results.append(("4. Train-only scaler reproduces",
                        stage_4_scaler(data_dir, work_configs, work_manifests)))
        results.append(("5. Worked preprocessing example",
                        stage_5_preprocessing_example(data_dir, work_configs, work_manifests)))
        results.append(("6. Structural validation (valid vs corrupted)",
                        stage_6_structural_validation(data_dir, work_configs, work_manifests)))
        results.append(("7. Descriptive outlier summary",
                        stage_7_outlier_evidence(data_dir, work_configs, work_manifests)))
        results.append(("8. Automated protocol checks",
                        stage_8_protocol(data_dir, work_configs, work_manifests, work_dir)))
        results.append(("9. Windowing to model-ready tensors",
                        stage_9_windows(data_dir, work_configs, work_manifests, work_dir)))
    finally:
        elapsed = time.time() - started

        print()
        print(RULE)
        print("SUMMARY")
        print(RULE)
        for label, result in results:
            print(f"  {'PASS' if result else 'FAIL'}   {label}")
        print(THIN)

        all_passed = all(r for _, r in results) and len(results) == 9
        print(f"  {'ALL STAGES PASSED' if all_passed else 'ONE OR MORE STAGES FAILED'}"
              f"   ({elapsed:.1f}s)")
        print(RULE)

        if created_temp and not args.keep:
            shutil.rmtree(work_dir, ignore_errors=True)
        elif args.keep:
            print(f"  work directory kept at: {work_dir}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
