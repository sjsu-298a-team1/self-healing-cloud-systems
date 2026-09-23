"""
Model 1 Phase 6: scoring-rule ablation comparison (S1/S2/S3), validation-only.

Aggregates each rule's already-computed threshold_selection/{selected_threshold,
validation_metrics}.json (produced by the UNMODIFIED threshold_selection.py --
same threshold-candidate procedure as Phase 5/architecture comparison) into one
machine-readable table, applies the predeclared eligibility rule (F1 >= 0.82
AND median detection delay <= 10s AND pre-fault FPR <= 0.05) and tie-break
(highest F1, then lower median detection delay). Never reads any test-split
file.
"""
import argparse
import json
import os

FAULT_TYPES = ("cpu", "mem", "delay", "loss")
RULE_DESCRIPTIONS = {
    "S1": "existing control: full-window MSE over all 30x55 elements",
    "S2": "current-timestep score: MSE at the final timestep only (55 features)",
    "S3": "trailing-5-second score: MSE over the final 5 timesteps (5x55 elements)",
}

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def load_rule_row(name, ablation_dir):
    rule_dir = os.path.join(ablation_dir, name)
    with open(os.path.join(rule_dir, "selected_threshold.json")) as f:
        selected_threshold = json.load(f)
    with open(os.path.join(rule_dir, "validation_metrics.json")) as f:
        validation_metrics = json.load(f)

    pooled = validation_metrics["pooled"]
    by_fault_type = validation_metrics["by_fault_type"]

    row = dict(
        rule=name,
        description=RULE_DESCRIPTIONS[name],
        threshold=selected_threshold["selected_threshold"],
        validation_precision=pooled["precision"],
        validation_recall=pooled["recall"],
        validation_f1=pooled["f1"],
        validation_pre_fault_fpr=pooled["pre_fault_fpr"],
        validation_median_detection_delay=pooled["median_detection_delay"],
        n_cases_missed=pooled["n_cases_missed"],
    )
    for ft in FAULT_TYPES:
        m = by_fault_type.get(ft, {})
        row[f"{ft}_f1"] = m.get("f1")
        row[f"{ft}_detection_delay"] = m.get("median_detection_delay")
    return row


def apply_eligibility(row, targets):
    row["eligible"] = (
        row["validation_f1"] >= targets["f1_min"]
        and row["validation_median_detection_delay"] <= targets["median_detection_delay_max_sec"]
        and row["validation_pre_fault_fpr"] <= targets["pre_fault_fpr_max"]
    )
    return row


def select_rule(rows):
    eligible = [r for r in rows if r["eligible"]]
    if not eligible:
        return None
    ranked = sorted(eligible, key=lambda r: (-r["validation_f1"], r["validation_median_detection_delay"]))
    return ranked[0]


def write_comparison_csv(rows, out_path):
    import csv
    fieldnames = [
        "rule", "description", "threshold",
        "validation_precision", "validation_recall", "validation_f1",
        "validation_pre_fault_fpr", "validation_median_detection_delay", "n_cases_missed",
        "cpu_f1", "mem_f1", "delay_f1", "loss_f1",
        "cpu_detection_delay", "mem_detection_delay", "delay_detection_delay", "loss_detection_delay",
        "eligible",
    ]
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r[k] for k in fieldnames})


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ablation-dir", default=os.path.join(
        REPO_ROOT, "experiments", "model1", "candidate_B_h32_z16_seed42", "scoring_rule_ablation"))
    parser.add_argument("--protocol-config", default=os.path.join(REPO_ROOT, "configs", "model1", "protocol_config.json"))
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.protocol_config) as f:
        protocol_config = json.load(f)
    targets = protocol_config["success_targets"]

    rows = []
    for name in ("S1", "S2", "S3"):
        row = load_rule_row(name, args.ablation_dir)
        row = apply_eligibility(row, targets)
        rows.append(row)

    write_comparison_csv(rows, os.path.join(args.ablation_dir, "comparison_table.csv"))

    selected = select_rule(rows)
    result = dict(
        targets=targets,
        tie_break_order=["highest F1", "lower median detection delay"],
        eligible_rules=[r["rule"] for r in rows if r["eligible"]],
        selected_rule=selected["rule"] if selected else None,
        rows=rows,
    )
    with open(os.path.join(args.ablation_dir, "comparison_result.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
