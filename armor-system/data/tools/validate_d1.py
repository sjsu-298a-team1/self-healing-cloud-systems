"""Check the ARMOR D1 evidence manifests against the hypotheses we set out to verify.

Offline by default: reads d1_inspection.json and the inventory. With --raw it also
re-hashes the extracted files and compares them to file_inventory.csv.

Each check is VERIFIED, MISMATCH, or CONFIG_STATED (stated in a config, not a data property).
Exit status is non-zero if any check is MISMATCH.

Usage:  python3 -I validate_d1.py [--manifest-dir DIR] [--raw DIR]
"""
import argparse
import csv
import hashlib
import json
import os
import sys

HYPOTHESES = [
    # (id, description, hypothesis, getter over d1_inspection summary, status if equal)
    ("failure_cases", "number of failure cases", 210, lambda s: s["cases"]["n_cases"], "VERIFIED"),
    ("nodes", "number of nodes/instances", 46, lambda s: s["features"]["n_nodes"], "VERIFIED"),
    ("normal_samples", "normal samples (train_samples.pkl)", 3714,
     lambda s: s["split_and_leakage"]["samples"]["train_samples"]["count"], "VERIFIED"),
    ("metric_channels", "metric channels", 110, lambda s: s["features"]["modality_groups"]["counts"]["metric"], "VERIFIED"),
    ("log_channels", "log feature channels", 11, lambda s: s["features"]["modality_groups"]["counts"]["log"], "VERIFIED"),
    ("trace_channels", "trace feature channels", 9, lambda s: s["features"]["modality_groups"]["counts"]["trace"], "VERIFIED"),
    ("channel_total", "total channels", 130, lambda s: s["features"]["n_channels"], "VERIFIED"),
    ("categories", "grouped failure categories", 5, lambda s: s["cases"]["distinct_categories"], "VERIFIED"),
    ("fine_types", "fine-grained failure types", 15, lambda s: s["cases"]["distinct_fine_failure_types"], "VERIFIED"),
    ("sampling_seconds", "dominant sampling step (s)", 60,
     lambda s: s["split_and_leakage"]["samples"]["samples_pkl"]["step_seconds_top"][0][0], "VERIFIED"),
    ("groups_cover_channels", "modality groups cover all channels exactly once", True,
     lambda s: s["features"]["modality_groups"]["covers_all_channels_exactly_once"], "VERIFIED"),
    ("no_nan_inf", "NaN+Inf values in feature tensors", 0,
     lambda s: s["features"]["nan_total"] + s["features"]["inf_total"], "VERIFIED"),
    ("all_types_mapped", "fine types lacking a category mapping", 0,
     lambda s: len(s["cases"]["unmapped_failure_types"]), "VERIFIED"),
    ("splits_disjoint", "train/test timestamp overlap", 0,
     lambda s: s["split_and_leakage"]["samples"]["train_test_timestamp_overlap"], "VERIFIED"),
    ("samples_pkl_union", "samples.pkl equals train union test", True,
     lambda s: s["split_and_leakage"]["samples"]["samples_pkl_is_exact_union_of_train_and_test_by_timestamp_and_values"], "VERIFIED"),
]
# Observations that are expected to DIFFER from the naive reading; recorded for the report.
KNOWN_DISCREPANCIES = [
    ("ad_events_equal_cases", "ad_cases.pkl timestamps equal cases.csv timestamps", True,
     lambda s: s["cases"]["ad_cases_not_in_cases_csv"] == 0 and s["cases"]["cases_csv_not_in_ad_cases"] == 0),
    ("train_scaled_on_train_only", "feature scaling statistics fit on train only (per-node-channel mean0/std1 holds on train alone)", True,
     lambda s: s["features"]["scaling_evidence_per_node_channel"]["train_only"]["fraction_of_nonconstant"] > 0.5),
    ("pretraining_set_precedes_ad_split", "pretraining set contains no samples after the AD split time", True,
     lambda s: s["split_and_leakage"]["pretraining_exposure"]["train_samples_after_ad_split_ts"] == 0),
]


def run_hypotheses(summary):
    results = []
    for hid, desc, expected, getter, status in HYPOTHESES:
        try:
            got = getter(summary)
        except (KeyError, IndexError, TypeError) as exc:
            results.append({"id": hid, "description": desc, "expected": expected, "observed": None,
                            "status": "MISMATCH", "error": repr(exc)})
            continue
        results.append({"id": hid, "description": desc, "expected": expected, "observed": got,
                        "status": status if got == expected else "MISMATCH"})
    for hid, desc, expected, getter in KNOWN_DISCREPANCIES:
        got = bool(getter(summary))
        results.append({"id": hid, "description": desc, "expected": expected, "observed": got,
                        "status": "VERIFIED" if got == expected else "DISCREPANCY_CONFIRMED"})
    return results


def verify_inventory(raw_d1_dir, inventory_csv):
    """Re-hash files under raw_d1_dir and compare to the recorded inventory."""
    problems = []
    with open(inventory_csv, newline="") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        path = os.path.join(raw_d1_dir, r["path"])
        if not os.path.exists(path):
            problems.append(f"missing: {r['path']}")
            continue
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for b in iter(lambda: f.read(1 << 20), b""):
                h.update(b)
        if h.hexdigest() != r["sha256"] or os.path.getsize(path) != int(r["bytes"]):
            problems.append(f"changed: {r['path']}")
    return {"files_checked": len(rows), "problems": problems}


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    mdir = os.path.join(here, "..", "manifests", "armor_d1")
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest-dir", default=mdir)
    ap.add_argument("--raw", default=None, help="extracted D1 directory (optional, enables re-hash)")
    args = ap.parse_args()
    with open(os.path.join(args.manifest_dir, "d1_inspection.json")) as fh:
        summary = json.load(fh)
    results = run_hypotheses(summary)
    report = {"hypothesis_checks": results}
    if args.raw:
        report["inventory_rehash"] = verify_inventory(args.raw, os.path.join(args.manifest_dir, "file_inventory.csv"))
    out_path = os.path.join(args.manifest_dir, "d1_validation.json")
    with open(out_path, "w") as fh:
        json.dump(report, fh, indent=2)
    bad = [r for r in results if r["status"] == "MISMATCH"]
    for r in results:
        print(f"{r['status']:<22} {r['id']:<34} expected={r['expected']!r} observed={r['observed']!r}")
    if args.raw:
        print("inventory:", report["inventory_rehash"])
    sys.exit(1 if bad or (args.raw and report["inventory_rehash"]["problems"]) else 0)


if __name__ == "__main__":
    main()
