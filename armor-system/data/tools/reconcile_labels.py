"""Record how ARMOR D1's two official label files relate (cases.csv vs ad_cases.pkl).

Descriptive evidence only: it never creates training labels, durations or intervals,
and it does not use any tolerance to force matches (matching is exact equality; the
nearest timestamp in the other file is reported for unmatched events only).

Outputs, in the manifest directory:
  label_reconciliation.csv   one row per distinct timestamp in either file
  label_reconciliation.json  counts and the evaluation populations

Usage:  python3 -I reconcile_labels.py [--d1 DIR] [--manifest-dir DIR]
"""
import argparse
import bisect
import csv
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import d1_checks as ck  # noqa: E402
import pickle_symbolic as ps  # noqa: E402

FT_SPLIT_RATIO = 0.6


def utc(ts):
    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _nearest(ts, sorted_other):
    i = bisect.bisect_left(sorted_other, ts)
    cand = [sorted_other[j] for j in (i - 1, i) if 0 <= j < len(sorted_other)]
    return min(cand, key=lambda v: abs(v - ts)) if cand else None


def reconcile(cases, ad_ts, split_ts):
    """cases: rows from ck.read_cases_csv (file order); ad_ts: list of ints; split_ts: AD split (epoch s)."""
    case_ts = [c["timestamp"] for c in cases]
    case_idx = {c["timestamp"]: i for i, c in enumerate(cases)}
    n_train_cases = ck.case_split_index(len(cases), FT_SPLIT_RATIO)
    in_c, in_a = set(case_ts), set(ad_ts)
    cs_sorted, ad_sorted = sorted(in_c), sorted(in_a)
    rows = []
    for ts in sorted(in_c | in_a):
        both, c_only, a_only = ts in in_c and ts in in_a, ts in in_c and ts not in in_a, ts in in_a and ts not in in_c
        category = "shared" if both else ("case_only" if c_only else "ad_only")
        row = {"timestamp_epoch": ts, "timestamp_utc": utc(ts),
               "in_cases_csv": int(ts in in_c), "in_ad_cases_pkl": int(ts in in_a), "category": category,
               "post_ad_split": int(ts > split_ts),
               "cases_csv_index": case_idx.get(ts, ""),
               "ft_rcl_side": ("" if ts not in in_c else ("train" if case_idx[ts] < n_train_cases else "test")),
               "level": "", "cmdb_id": "", "failure_type": "",
               "nearest_other_source_epoch": "", "nearest_other_source_delta_s": ""}
        if ts in in_c:
            c = cases[case_idx[ts]]
            row.update(level=c["level"], cmdb_id=c["cmdb_id"], failure_type=c["failure_type"])
        if category != "shared":
            other = _nearest(ts, ad_sorted if c_only else cs_sorted)
            row["nearest_other_source_epoch"] = other
            row["nearest_other_source_delta_s"] = other - ts
        rows.append(row)

    post = lambda xs: [x for x in xs if x > split_ts]  # noqa: E731
    pre_ad = sorted(x for x in ad_ts if x <= split_ts)
    summary = {
        "cases_csv_count": len(case_ts), "ad_cases_pkl_count": len(ad_ts),
        "ad_cases_pkl_unique": len(in_a), "ad_cases_pkl_sorted": list(ad_ts) == sorted(ad_ts),
        "exact_shared": len(in_c & in_a), "ad_only": len(in_a - in_c), "case_only": len(in_c - in_a),
        "match_rule": "exact timestamp equality; no tolerance applied",
        "ad_split_ts": split_ts, "ad_split_utc": utc(split_ts),
        "pre_split_ad_events": len(pre_ad),
        "pre_split_ad_events_equal_cases_csv_first_n": pre_ad == case_ts[:len(pre_ad)],
        "ad_only_post_split": len([x for x in in_a - in_c if x > split_ts]),
        "case_only_post_split": len([x for x in in_c - in_a if x > split_ts]),
        "evaluation_populations_post_split": {
            "official_ad_labels": len(post(in_a)), "injection_cases": len(post(in_c)),
            "intersection": len(post(in_a & in_c)), "union": len(post(in_a | in_c)),
        },
        "min_abs_delta_ad_only_to_nearest_case_s": min(abs(r["nearest_other_source_delta_s"]) for r in rows if r["category"] == "ad_only"),
        "min_abs_delta_case_only_to_nearest_ad_s": min(abs(r["nearest_other_source_delta_s"]) for r in rows if r["category"] == "case_only"),
    }
    return rows, summary


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    ap = argparse.ArgumentParser()
    ap.add_argument("--d1", default=os.path.join(here, "..", "raw", "armor_zenodo_21744694", "extracted", "D1"))
    ap.add_argument("--manifest-dir", default=os.path.join(here, "..", "manifests", "armor_d1"))
    args = ap.parse_args()
    cases = ck.read_cases_csv(os.path.join(args.d1, "cases", "cases.csv"))
    ad = ps.read_symbolic(os.path.join(args.d1, "cases", "ad_cases.pkl"))
    if ps.global_refs(ad):
        raise SystemExit("ad_cases.pkl references globals; refusing to treat it as literal data")
    with open(os.path.join(args.manifest_dir, "d1_inspection.json")) as fh:
        split_ts = json.load(fh)["split_and_leakage"]["armor_ad_split_derived_from_code"]["split_ts"]
    rows, summary = reconcile(cases, [int(x) for x in ad], split_ts)
    with open(os.path.join(args.manifest_dir, "label_reconciliation.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(os.path.join(args.manifest_dir, "label_reconciliation.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
