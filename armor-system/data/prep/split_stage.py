"""STEP 4: build versioned split manifests (official ARMOR, the proposed 100/26/84, and a recommended alternative)."""
import os

import numpy as np

from . import paths, splits as sp
from .common import iso, write_csv, write_json
from .loader import category_of
import d1_checks as ck  # noqa: E402

OFFICIAL, CANDIDATE, ALTERNATIVE = "official_armor_v1", "model1_candidate_100_26_84_v1", "model1_alternative_v1"


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
    cand, cand_rows = sp.build(CANDIDATE, "evaluated",
                               "Proposed Model 1 split: first 100 cases train, next 26 validation, last 84 (official test) test.",
                               cases, cats, {"train": [0, 100], "validation": [100, k_off], "test": [k_off, n]}, ts_list, segs, ad_split)

    scan = sp.boundary_scan(cases, cats, segs)
    ok = [r for r in scan if r["boundary_ok"]]
    near = sorted(ok, key=lambda r: (abs(r["k"] - 100), -r["safe_gap_seconds"]))   # nearest to 100; ties -> larger safe gap
    chosen = near[0] if near else None
    alt = alt_rows = None
    if chosen:
        k = chosen["k"]
        alt, alt_rows = sp.build(ALTERNATIVE, "proposed_pending_approval",
                                 f"Recommended alternative: train/validation boundary moved from 100 to {k} (nearest index with a positive safe gap "
                                 f"and no split incident group); same official 84-case test set.",
                                 cases, cats, {"train": [0, k], "validation": [k, k_off], "test": [k_off, n]}, ts_list, segs, ad_split)
    folds = sp.rolling_origin(cases, cats, segs)

    for m in [off, cand] + ([alt] if alt else []):
        write_json(os.path.join(out, f"{m['name']}.json"), m)
    write_json(os.path.join(out, "boundary_scan.json"), {"description": "train|validation boundary index k scanned around the proposed 100",
                                                        "required_case_to_case_seconds": sp.REQUIRED_SPAN, "scan": scan,
                                                        "nearest_safe_k_to_100": chosen["k"] if chosen else None})
    write_json(os.path.join(out, "rolling_origin_folds_v1.json"), {"manifest_version": sp.MANIFEST_VERSION, "status": "proposed_pending_approval",
                                                                  "description": "Forward-chaining validation folds over the first 126 cases (no random assignment); test is always the official last 84 cases.",
                                                                  "folds": folds})
    # one assignment table for the dashboard and for downstream use
    rows = []
    for i, c in enumerate(cases):
        r = {"case_index": i, "timestamp": c["timestamp"], "utc": iso(c["timestamp"]), "category": cats[i],
             "failure_type": c["failure_type"], "level": c["level"], "cmdb_id": c["cmdb_id"],
             "group_id": off_rows[i]["group_id"], "official_split": off_rows[i]["split"], "candidate_split": cand_rows[i]["split"],
             "alternative_split": alt_rows[i]["split"] if alt_rows else ""}
        rows.append(r)
    write_csv(os.path.join(out, "case_split_assignments.csv"), rows)
    return {"official": off, "candidate": cand, "alternative": alt, "scan": scan, "folds": folds, "ad_split": ad_split}
