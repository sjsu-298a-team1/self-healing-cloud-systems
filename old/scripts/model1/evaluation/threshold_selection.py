"""
Model 1 Phase 5 (validation-only): threshold selection.

Pure post-processing over already-computed validation window scores (see
scoring.py) -- no model, no gradient, no parameter of any kind. Never reads
test_cases.json and never reads any test-split score.

Threshold-selection rule (documented here BEFORE any numerical threshold is
chosen, per the audit of docs/model1/protocol/protocol.md Sec.13 item 2 and
configs/model1/protocol_config.json's window_prediction_rule):

The locked protocol specifies threshold selection only at the level of "a
percentile of val normal-window reconstruction errors" and explicitly flags
the exact percentile as an OPEN decision (protocol.md Sec.13 item 2) -- it
does not fix a number. This file resolves that open decision deterministically
using the ALREADY-LOCKED success target pre_fault_fpr_max = 0.05
(protocol_config.json success_targets):

  1. Candidate thresholds = a fixed, deterministic percentile grid (50.0 to
     100.0 in 0.1 steps) evaluated on the PRE-FAULT (known-normal region)
     validation window scores only -- so every candidate is a function of
     validation data alone, never a hand-picked constant.
  2. Selected threshold = the SMALLEST candidate whose empirical pre-fault
     FPR (fraction of pre-fault validation windows scoring above it) is
     <= 0.05. FPR is monotonically non-increasing as the threshold rises, so
     this is well-defined: it is the tightest threshold that still respects
     the locked FPR ceiling, maximizing sensitivity to real anomalies without
     violating that ceiling.
  3. Deterministic tie-break: if multiple candidates in the grid tie on
     empirical FPR (e.g. duplicate values from the percentile grid), the
     smallest such candidate is selected -- this falls out automatically from
     scanning the sorted grid ascending and stopping at the first candidate
     that satisfies the FPR<=0.05 constraint.

This is NOT a manual/visual choice and never touches the test split.
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))
from metrics import (  # noqa: E402
    confusion_counts,
    detection_delay,
    f1_score,
    first_detection_time,
    group_case_ids_by_fault_type,
    median,
    precision,
    recall,
)

TARGET_PRE_FAULT_FPR = 0.05  # locked: configs/model1/protocol_config.json success_targets.pre_fault_fpr_max
PERCENTILE_GRID = np.clip(np.arange(50.0, 100.0 + 1e-9, 0.1), 0.0, 100.0)


def read_validation_scores_csv(path):
    rows = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(
                dict(
                    case_id=r["case_id"],
                    service=r["service"],
                    fault_type=r["fault_type"],
                    window_index=int(r["window_index"]),
                    window_start_time=int(r["window_start_time"]),
                    window_end_time=int(r["window_end_time"]),
                    region=r["region"],
                    score=float(r["score"]),
                )
            )
    return rows


def build_candidate_thresholds(pre_fault_scores, percentile_grid=PERCENTILE_GRID):
    """Candidates are derived ONLY from the given validation scores: each
    candidate is percentile(pre_fault_scores, p) for p in percentile_grid.
    Returns a sorted array of unique threshold values."""
    pre_fault_scores = np.asarray(pre_fault_scores, dtype=np.float64)
    assert len(pre_fault_scores) > 0, "no pre-fault validation scores to derive candidates from"
    candidates = np.percentile(pre_fault_scores, percentile_grid, method="linear")
    return np.unique(candidates)


def empirical_pre_fault_fpr(pre_fault_scores, threshold):
    pre_fault_scores = np.asarray(pre_fault_scores, dtype=np.float64)
    return float(np.mean(pre_fault_scores > threshold))


def select_threshold(pre_fault_scores, candidates, target_fpr=TARGET_PRE_FAULT_FPR):
    """Smallest candidate (ascending scan) whose empirical pre-fault FPR is
    <= target_fpr. Falls back to the largest candidate if none satisfy the
    target (should not happen since FPR -> 0 as threshold -> max score)."""
    candidates = np.sort(np.asarray(candidates, dtype=np.float64))
    for c in candidates:
        fpr = empirical_pre_fault_fpr(pre_fault_scores, c)
        if fpr <= target_fpr:
            return float(c), fpr
    fallback = float(candidates[-1])
    return fallback, empirical_pre_fault_fpr(pre_fault_scores, fallback)


def _case_inject_time(case_rows):
    """Recovers inject_time for one case from its own window metadata: the
    smallest window_end_time among that case's post-injection-region windows
    (stride=1 evaluation windows produce every integer end_time, so this
    equals inject_time exactly, never an approximation)."""
    post = [r["window_end_time"] for r in case_rows if r["region"] == "post_injection_evaluation_region"]
    assert post, "case has no post-injection-region windows -- cannot recover inject_time"
    return min(post)


def compute_metrics(rows, threshold):
    """Pooled metrics for the given rows at the given threshold. rows must
    already be filtered to the fault-type/subset of interest by the caller
    (pass all validation rows for pooled numbers)."""
    labels = [r["region"] == "post_injection_evaluation_region" for r in rows]
    predictions = [r["score"] > threshold for r in rows]

    cm = confusion_counts(labels, predictions)
    p = precision(cm["tp"], cm["fp"])
    r_ = recall(cm["tp"], cm["fn"])
    f1 = f1_score(cm["tp"], cm["fp"], cm["fn"])

    pre_fault_preds = [pred for r, pred in zip(rows, predictions) if r["region"] == "known_normal_region"]
    pre_fault_fpr = (sum(1 for x in pre_fault_preds if x) / len(pre_fault_preds)) if pre_fault_preds else float("nan")

    by_case = {}
    for r, label, pred in zip(rows, labels, predictions):
        by_case.setdefault(r["case_id"], []).append((r["window_end_time"], label, pred))

    delays = []
    n_misses = 0
    for cid, entries in by_case.items():
        entries.sort(key=lambda e: e[0])
        times = [e[0] for e in entries]
        case_labels = [e[1] for e in entries]
        case_preds = [e[2] for e in entries]
        case_rows = [r for r in rows if r["case_id"] == cid]
        inject_time = _case_inject_time(case_rows)
        det_time = first_detection_time(times, case_labels, case_preds)
        if det_time is None:
            n_misses += 1
        else:
            delays.append(detection_delay(inject_time, det_time))

    return dict(
        tp=cm["tp"], fp=cm["fp"], fn=cm["fn"], tn=cm["tn"],
        precision=p, recall=r_, f1=f1,
        pre_fault_fpr=pre_fault_fpr,
        median_detection_delay=median(delays) if delays else float("nan"),
        n_cases_with_detection=len(delays),
        n_cases_missed=n_misses,
        n_cases=len(by_case),
    )


def build_threshold_candidates_table(rows, candidates):
    pre_fault_scores = [r["score"] for r in rows if r["region"] == "known_normal_region"]
    table = []
    for c in candidates:
        m = compute_metrics(rows, c)
        table.append(dict(
            threshold=float(c),
            precision=m["precision"], recall=m["recall"], f1=m["f1"],
            pre_fault_fpr=m["pre_fault_fpr"], median_detection_delay=m["median_detection_delay"],
        ))
    return table


def write_candidates_csv(table, out_path):
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["threshold", "precision", "recall", "f1", "pre_fault_fpr", "median_detection_delay"]
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in table:
            writer.writerow(row)


def build_validation_metrics(rows, threshold):
    pooled = compute_metrics(rows, threshold)
    by_fault_type = {}
    groups = group_case_ids_by_fault_type(sorted(set(r["case_id"] for r in rows)))
    for ft, case_ids in groups.items():
        subset = [r for r in rows if r["case_id"] in set(case_ids)]
        if subset:
            by_fault_type[ft] = compute_metrics(subset, threshold)
    return dict(threshold=threshold, pooled=pooled, by_fault_type=by_fault_type)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--validation-scores", required=True, help="Path to validation_scores.csv")
    parser.add_argument("--out-dir", required=True, help="Directory to write threshold_candidates.csv, "
                                                            "selected_threshold.json, validation_metrics.json")
    return parser.parse_args()


def main():
    args = parse_args()
    rows = read_validation_scores_csv(args.validation_scores)

    pre_fault_scores = [r["score"] for r in rows if r["region"] == "known_normal_region"]
    candidates = build_candidate_thresholds(pre_fault_scores)
    selected_threshold, achieved_fpr = select_threshold(pre_fault_scores, candidates)

    table = build_threshold_candidates_table(rows, candidates)
    write_candidates_csv(table, os.path.join(args.out_dir, "threshold_candidates.csv"))

    selection_info = dict(
        selected_threshold=selected_threshold,
        target_pre_fault_fpr=TARGET_PRE_FAULT_FPR,
        achieved_pre_fault_fpr=achieved_fpr,
        rule="smallest candidate (percentile-grid-of-pre-fault-validation-scores, 50.0-100.0 step 0.1) "
             "whose empirical pre-fault FPR is <= 0.05; ties broken by taking the smallest such candidate",
        n_candidates=len(candidates),
    )
    with open(os.path.join(args.out_dir, "selected_threshold.json"), "w") as f:
        json.dump(selection_info, f, indent=2)

    metrics = build_validation_metrics(rows, selected_threshold)
    with open(os.path.join(args.out_dir, "validation_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"Selected threshold: {selected_threshold:.6f} (achieved pre-fault FPR={achieved_fpr:.4f})")
    print(f"Pooled: {json.dumps(metrics['pooled'], indent=2)}")
    print(f"By fault type: {json.dumps(metrics['by_fault_type'], indent=2)}")


if __name__ == "__main__":
    main()
