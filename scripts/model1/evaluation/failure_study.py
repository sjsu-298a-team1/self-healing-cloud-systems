"""
Model 1 Phase 8: failure study / generalization-gap analysis.

DESCRIPTIVE ONLY. Reads the already-frozen validation and test score/metric
artifacts (Phases 5-7) and produces comparison tables. Never computes,
selects, or suggests a new threshold; never retrains or re-scores anything;
never loads any file that wasn't already produced by a prior, already-
approved phase. The frozen threshold (from experiments/model1/
final_model_selection.json) is used only to reproduce already-known
per-window predictions for the per-case/per-fault breakdowns below -- it is
never recalculated.
"""
import argparse
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "protocol"))
from metrics import detection_delay, fault_type_of_case, first_detection_time  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

VALIDATION_SCORES_PATH = os.path.join(
    REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42",
    "scoring_rule_ablation", "S2", "validation_scores.csv",
)
TEST_SCORES_PATH = os.path.join(
    REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42", "final_test", "test_scores.csv",
)
FINAL_SELECTION_PATH = os.path.join(REPO_ROOT, "experiments", "model1", "final_model_selection.json")
VALIDATION_METRICS_PATH = os.path.join(
    REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42",
    "scoring_rule_ablation", "S2", "validation_metrics.json",
)
TEST_METRICS_PATH = os.path.join(
    REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42", "final_test", "test_metrics.json",
)

FAULT_TYPES = ("cpu", "mem", "delay", "loss")
QUANTILES = ("median", "p90", "p95", "p99", "max")


def read_scores_csv(path):
    with open(path) as f:
        rows = []
        for r in csv.DictReader(f):
            rows.append(dict(
                case_id=r["case_id"], service=r["service"], fault_type=r["fault_type"],
                window_index=int(r["window_index"]), window_start_time=int(r["window_start_time"]),
                window_end_time=int(r["window_end_time"]), region=r["region"], score=float(r["score"]),
            ))
        return rows


def quantiles_of(scores):
    scores = np.asarray(scores, dtype=np.float64)
    return dict(
        median=float(np.median(scores)),
        p90=float(np.percentile(scores, 90)),
        p95=float(np.percentile(scores, 95)),
        p99=float(np.percentile(scores, 99)),
        max=float(scores.max()),
        n=len(scores),
    )


def case_inject_time(case_rows):
    post = [r["window_end_time"] for r in case_rows if r["region"] == "post_injection_evaluation_region"]
    assert post, "case has no post-injection-region windows"
    return min(post)


def per_case_metrics(rows, threshold):
    by_case = {}
    for r in rows:
        by_case.setdefault(r["case_id"], []).append(r)

    results = []
    for cid, case_rows in sorted(by_case.items()):
        case_rows = sorted(case_rows, key=lambda r: r["window_end_time"])
        inject_time = case_inject_time(case_rows)
        known_normal = [r for r in case_rows if r["region"] == "known_normal_region"]
        post_injection = [r for r in case_rows if r["region"] == "post_injection_evaluation_region"]

        pre_fault_preds = [r["score"] > threshold for r in known_normal]
        pre_fault_fpr = (sum(pre_fault_preds) / len(pre_fault_preds)) if pre_fault_preds else float("nan")

        post_preds = [r["score"] > threshold for r in post_injection]
        post_recall = (sum(post_preds) / len(post_preds)) if post_preds else float("nan")

        times = [r["window_end_time"] for r in case_rows]
        labels = [r["region"] == "post_injection_evaluation_region" for r in case_rows]
        preds = [r["score"] > threshold for r in case_rows]
        det_time = first_detection_time(times, labels, preds)
        detected = det_time is not None
        delay = detection_delay(inject_time, det_time) if detected else None

        results.append(dict(
            case_id=cid,
            fault_type=fault_type_of_case(cid),
            inject_time=inject_time,
            pre_fault_fpr=pre_fault_fpr,
            first_detection_delay=delay,
            post_injection_recall=post_recall,
            detected=detected,
        ))
    return results


def write_test_case_metrics_csv(case_results, out_path):
    fieldnames = ["case_id", "fault_type", "pre_fault_fpr", "first_detection_delay",
                  "post_injection_recall", "detected"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in case_results:
            writer.writerow({k: r[k] for k in fieldnames})


def build_validation_vs_test_summary(val_metrics, test_metrics):
    rows = []
    for split_name, m in (("validation", val_metrics), ("test", test_metrics)):
        pooled = m["pooled"]
        rows.append(dict(
            split=split_name, fault_type="pooled",
            precision=pooled["precision"], recall=pooled["recall"], f1=pooled["f1"],
            pre_fault_fpr=pooled["pre_fault_fpr"], median_detection_delay=pooled["median_detection_delay"],
        ))
        for ft in FAULT_TYPES:
            ftm = m["by_fault_type"].get(ft, {})
            if ftm:
                rows.append(dict(
                    split=split_name, fault_type=ft,
                    precision=ftm["precision"], recall=ftm["recall"], f1=ftm["f1"],
                    pre_fault_fpr=ftm["pre_fault_fpr"], median_detection_delay=ftm["median_detection_delay"],
                ))
    return rows


def write_summary_csv(rows, out_path):
    fieldnames = ["split", "fault_type", "precision", "recall", "f1", "pre_fault_fpr", "median_detection_delay"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def build_known_normal_quantile_table(val_rows, test_rows):
    groups = {}
    val_known_normal = [r["score"] for r in val_rows if r["region"] == "known_normal_region"]
    test_known_normal_all = [r for r in test_rows if r["region"] == "known_normal_region"]
    groups["validation_known_normal"] = quantiles_of(val_known_normal)
    groups["test_known_normal"] = quantiles_of([r["score"] for r in test_known_normal_all])
    for ft in FAULT_TYPES:
        subset = [r["score"] for r in test_known_normal_all if r["fault_type"] == ft]
        groups[f"test_known_normal_{ft}"] = quantiles_of(subset)
    return groups


def write_quantile_csv(groups, out_path):
    fieldnames = ["group", "n", "median", "p90", "p95", "p99", "max"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for name, q in groups.items():
            row = dict(group=name)
            row.update(q)
            writer.writerow(row)


def build_loss_case_analysis(val_rows, test_rows, threshold):
    """For each LOSS-fault test case: time-to-first-threshold-crossing
    (post-injection), pre/post mean score, and case-to-case variation,
    alongside the pooled LOSS validation numbers for comparison."""
    loss_test_cases = sorted(set(r["case_id"] for r in test_rows if r["fault_type"] == "loss"))
    rows = []
    for cid in loss_test_cases:
        case_rows = sorted([r for r in test_rows if r["case_id"] == cid], key=lambda r: r["window_end_time"])
        inject_time = case_inject_time(case_rows)
        known_normal = [r for r in case_rows if r["region"] == "known_normal_region"]
        post_injection = [r for r in case_rows if r["region"] == "post_injection_evaluation_region"]

        crossing_times = [r["window_end_time"] for r in post_injection if r["score"] > threshold]
        time_to_first_crossing = (crossing_times[0] - inject_time) if crossing_times else None

        rows.append(dict(
            case_id=cid,
            inject_time=inject_time,
            mean_score_pre_injection=float(np.mean([r["score"] for r in known_normal])),
            max_score_pre_injection=float(np.max([r["score"] for r in known_normal])),
            mean_score_post_injection=float(np.mean([r["score"] for r in post_injection])),
            max_score_post_injection=float(np.max([r["score"] for r in post_injection])),
            time_to_first_threshold_crossing=time_to_first_crossing,
            fraction_post_injection_above_threshold=float(np.mean([r["score"] > threshold for r in post_injection])),
        ))

    loss_val_scores_pre = [r["score"] for r in val_rows if r["fault_type"] == "loss" and r["region"] == "known_normal_region"]
    loss_val_scores_post = [r["score"] for r in val_rows if r["fault_type"] == "loss" and r["region"] == "post_injection_evaluation_region"]
    loss_test_scores_pre = [r["score"] for r in test_rows if r["fault_type"] == "loss" and r["region"] == "known_normal_region"]
    loss_test_scores_post = [r["score"] for r in test_rows if r["fault_type"] == "loss" and r["region"] == "post_injection_evaluation_region"]

    comparison = dict(
        validation_loss_pre_injection_mean=float(np.mean(loss_val_scores_pre)),
        validation_loss_post_injection_mean=float(np.mean(loss_val_scores_post)),
        test_loss_pre_injection_mean=float(np.mean(loss_test_scores_pre)),
        test_loss_post_injection_mean=float(np.mean(loss_test_scores_post)),
    )
    return rows, comparison


def write_loss_case_csv(rows, out_path):
    fieldnames = ["case_id", "inject_time", "mean_score_pre_injection", "max_score_pre_injection",
                  "mean_score_post_injection", "max_score_post_injection",
                  "time_to_first_threshold_crossing", "fraction_post_injection_above_threshold"]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow(r)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "experiments", "model1", "failure_study"))
    return parser.parse_args()


def main():
    args = parse_args()
    val_rows = read_scores_csv(VALIDATION_SCORES_PATH)
    test_rows = read_scores_csv(TEST_SCORES_PATH)
    with open(FINAL_SELECTION_PATH) as f:
        final_selection = json.load(f)
    threshold = final_selection["threshold"]["value"]
    with open(VALIDATION_METRICS_PATH) as f:
        val_metrics = json.load(f)
    with open(TEST_METRICS_PATH) as f:
        test_metrics = json.load(f)

    # 1. validation vs test summary (pooled + per fault type)
    summary_rows = build_validation_vs_test_summary(val_metrics, test_metrics)
    write_summary_csv(summary_rows, os.path.join(args.out_dir, "validation_vs_test_summary.csv"))

    # 2. per-case test results
    case_results = per_case_metrics(test_rows, threshold)
    write_test_case_metrics_csv(case_results, os.path.join(args.out_dir, "test_case_metrics.csv"))

    # 3. known-normal score quantiles (validation vs test, test by fault type)
    quantile_groups = build_known_normal_quantile_table(val_rows, test_rows)
    write_quantile_csv(quantile_groups, os.path.join(args.out_dir, "known_normal_score_quantiles.csv"))

    # 4. LOSS-specific case analysis
    loss_rows, loss_comparison = build_loss_case_analysis(val_rows, test_rows, threshold)
    write_loss_case_csv(loss_rows, os.path.join(args.out_dir, "loss_fault_case_analysis.csv"))

    # 5. failure_study.json -- aggregates everything above + safe-worded conclusions
    safe_conclusions = [
        "The selected Model 1 configuration (Candidate B + S2 scoring) did not generalize sufficiently to the "
        "held-out test cases under the locked success criteria (F1 >= 0.82, median detection delay <= 10s, "
        "pre-fault FPR <= 0.05); all three were met on validation and all three failed on test.",
        "Known-normal S2 score distributions shifted upward on the test split relative to validation, "
        "especially for CPU and MEM test cases, which is consistent with the large pre-fault FPR increase "
        "observed for those two fault types (0.22 and 0.30 on test vs. the 0.05 validation-calibrated ceiling).",
        "LOSS-fault test cases showed substantially weaker post-injection sensitivity than LOSS-fault "
        "validation cases (test recall 0.166 vs. the validation result that made S2 attractive), with a much "
        "longer time-to-first-threshold-crossing on average.",
        "Within the tested architecture range (Candidates A/B/C/D, 22.7K-242K parameters), architecture "
        "capacity alone did not materially resolve the validation detection-delay issue -- all four candidates "
        "clustered at 14.5-15.0s under the S1 scoring rule regardless of size.",
    ]

    failure_study = dict(
        phase7_commit="ece5684",
        threshold_used=threshold,
        validation_vs_test_summary=summary_rows,
        known_normal_score_quantiles=quantile_groups,
        loss_analysis=dict(per_case=loss_rows, pre_post_mean_comparison=loss_comparison),
        test_case_metrics=case_results,
        safe_conclusions=safe_conclusions,
        note="Descriptive analysis only. No new threshold was computed or suggested here; no model or "
             "scoring-rule change resulted from this analysis.",
    )
    with open(os.path.join(args.out_dir, "failure_study.json"), "w") as f:
        json.dump(failure_study, f, indent=2)

    print(f"Wrote failure study artifacts to {args.out_dir}")
    print(json.dumps(dict(
        known_normal_quantiles=quantile_groups,
        loss_pre_post_mean_comparison=loss_comparison,
    ), indent=2))


if __name__ == "__main__":
    main()
