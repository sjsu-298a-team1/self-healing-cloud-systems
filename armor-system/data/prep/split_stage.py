"""STEP 4: build versioned split manifests.

Three distinct things are kept apart (and documented in every Model 1 manifest):
  1. the Model 1 CASE split (this file's FINAL manifest) - which injection cases train / validate / test;
  2. the sample-level anomaly-detection TIMELINE of the official ARMOR baseline (AD split at 60% of samples);
  3. the official ARMOR FT/RCL protocol (first 126 / last 84 cases), preserved unchanged.
"""
import os

from . import paths, splits as sp
from .common import iso, write_csv, write_json
from .loader import category_of
import d1_checks as ck  # noqa: E402

OFFICIAL, CANDIDATE, FINAL = "official_armor_v1", "model1_candidate_100_26_84_v1", "model1_split_101_25_84_v1"
APPROVED_K = 101                      # approved by the project owner: 101 train / 25 validation / 84 test
APPROVED_COUNTS = {                   # the approved class table (order: sp.CLASSES)
    "train": {"Container Hardware": 37, "Container Network": 32, "Node CPU": 10, "Node Disk": 18, "Node Memory": 4},
    "validation": {"Container Hardware": 10, "Container Network": 6, "Node CPU": 3, "Node Disk": 5, "Node Memory": 1},
    "test": {"Container Hardware": 36, "Container Network": 22, "Node CPU": 8, "Node Disk": 14, "Node Memory": 4},
}


class ApprovedSplitError(RuntimeError):
    """Raised instead of overriding a safeguard when the approved split fails a hard check."""


FINAL_EXTRA = {
    "approval": {"decision": "101 train / 25 validation / 84 test", "approved_by": "project owner (Khushi Donda)", "recorded": "2026-10-25",
                 "basis": "nearest boundary to the proposed 100 with a positive safe gap and no cut incident group (see boundary_scan.json)"},
    "scope": {
        "this_manifest": "Model 1 case-level split: which injection cases are used for training, validation and testing.",
        "sample_level_ad_timeline": "ARMOR's anomaly-detection split is sample-based (60% of the 7,200 samples = the AD split time) and is unchanged; "
                                    "the validation|test sample boundary here is aligned to it, so every post-AD-boundary sample belongs to the test period.",
        "official_armor_protocol": "official_armor_v1 (126 / 84 by case order) is preserved unchanged for reproduction; the 84 test cases are identical in both.",
        "detection_evaluation": "reported as two separate event-level populations (98 official AD events, 84 documented injection cases); never averaged",
    },
    "statistical_limitations": [
        "Validation contains a single Node Memory case: Node Memory validation metrics (recall, F1, macro-F1 contribution) are statistically unstable and must not be used to tune hyper-parameters or thresholds on their own.",
        "Node Memory has only 4 training and 4 test cases; per-class test estimates for it have very wide uncertainty.",
        "Validation Node CPU has 3 cases; treat per-class validation numbers as indicative only.",
        "No incident end times exist: this split assigns cases, it does not define sample-level detection labels.",
    ],
}


def run(labels, ts, is_test):
    out = paths.art("splits")
    cases = labels["cases"]
    cats = [category_of(c, labels) for c in cases]
    ts_list = sorted(ts.tolist())
    ad_split = ts_list[int(len(ts_list) * 0.6)]
    segs = ck.segment_bounds(sorted(ts[is_test].tolist()))
    n = len(cases)
    k_off = ck.case_split_index(n, 0.6)

    off, off_rows = sp.build(OFFICIAL, "approved_reproduction",
                             "ARMOR's own FT/RCL case split (first 60% train, last 40% test). Preserved unchanged for reproduction.",
                             cases, cats, {"train": [0, k_off], "test": [k_off, n]}, ts_list, segs, ad_split, ad_aligned=False)
    cand, cand_rows = sp.build(CANDIDATE, "rejected_fails_hard_checks",
                               "Proposed Model 1 split: first 100 cases train, next 26 validation, last 84 (official test) test. Rejected: fails hard checks; kept as evidence.",
                               cases, cats, {"train": [0, 100], "validation": [100, k_off], "test": [k_off, n]}, ts_list, segs, ad_split)
    scan = sp.boundary_scan(cases, cats, segs)
    row = next(r for r in scan if r["k"] == APPROVED_K)
    if not row["boundary_ok"]:
        raise ApprovedSplitError(f"approved boundary k={APPROVED_K} has no positive safe gap or cuts an incident group: {row}")
    final, final_rows = sp.build(FINAL, "approved",
                                 f"Approved Model 1 case split: first {APPROVED_K} cases train, next {k_off - APPROVED_K} validation, last {n - k_off} (official test) test. "
                                 "Chronological and incident-group-aware.",
                                 cases, cats, {"train": [0, APPROVED_K], "validation": [APPROVED_K, k_off], "test": [k_off, n]}, ts_list, segs, ad_split, extra=FINAL_EXTRA)
    hard = [c for c in final["checks"] if c["severity"] == "hard" and c["status"] == "FAIL"]
    if hard:
        raise ApprovedSplitError("approved split fails hard checks: " + "; ".join(c["id"] + ": " + c["detail"] for c in hard))
    got = {s: r["class_counts"] for s, r in final["case_ranges"].items()}
    if got != APPROVED_COUNTS:
        raise ApprovedSplitError(f"class counts differ from the approved table: {got}")
    folds = sp.rolling_origin(cases, cats, segs)

    for m in (off, cand, final):
        write_json(os.path.join(out, f"{m['name']}.json"), m)
    write_json(os.path.join(out, "boundary_scan.json"), {"description": "train|validation boundary index k scanned around the proposed 100 (justification for the approved 101)",
                                                        "required_case_to_case_seconds": sp.REQUIRED_SPAN, "scan": scan, "approved_k": APPROVED_K})
    write_json(os.path.join(out, "rolling_origin_folds_v1.json"), {"manifest_version": sp.MANIFEST_VERSION, "status": "proposed_not_approved",
                                                                  "description": "Forward-chaining folds over the first 126 cases. NOT part of the approved protocol; kept as an optional idea only.",
                                                                  "folds": folds})
    rows = []
    for i, c in enumerate(cases):
        rows.append({"case_index": i, "timestamp": c["timestamp"], "utc": iso(c["timestamp"]), "category": cats[i], "failure_type": c["failure_type"],
                     "level": c["level"], "cmdb_id": c["cmdb_id"], "group_id": off_rows[i]["group_id"], "official_split": off_rows[i]["split"],
                     "model1_split": final_rows[i]["split"], "rejected_100_26_84_split": cand_rows[i]["split"]})
    write_csv(os.path.join(out, "case_split_assignments.csv"), rows)
    return {"official": off, "candidate": cand, "final": final, "scan": scan, "folds": folds, "ad_split": ad_split}
