"""
Model 1 candidate architecture comparison (validation-only).

Aggregates each candidate's already-computed training_history.json,
run_metadata.json, and threshold_selection/{selected_threshold,validation_metrics}.json
into one machine-readable comparison table, applies the predeclared eligibility
rule and deterministic tie-break (configs/model1/candidate_architectures.json
model_selection_rule), and reports the result.

Does not train or score anything itself -- purely aggregates existing,
already-frozen per-candidate artifacts. Never reads any test-split file.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "training"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "models", "model1"))

import torch  # noqa: E402
from train import build_model_from_config, load_training_config  # noqa: E402
from lstm_autoencoder import count_trainable_parameters  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
FAULT_TYPES = ("cpu", "mem", "delay", "loss")


def load_candidate_row(name, spec, experiments_dir):
    run_id = spec["run_id"]
    run_dir = os.path.join(experiments_dir, run_id)
    training_config_path = os.path.join(REPO_ROOT, spec["training_config"])
    training_config = load_training_config(training_config_path)
    model, model_config = build_model_from_config(training_config)
    n_params = count_trainable_parameters(model)

    with open(os.path.join(run_dir, "run_metadata.json")) as f:
        run_metadata = json.load(f)

    ts_dir = os.path.join(run_dir, "threshold_selection")
    with open(os.path.join(ts_dir, "selected_threshold.json")) as f:
        selected_threshold = json.load(f)
    with open(os.path.join(ts_dir, "validation_metrics.json")) as f:
        validation_metrics = json.load(f)

    pooled = validation_metrics["pooled"]
    by_fault_type = validation_metrics["by_fault_type"]

    row = dict(
        candidate=name,
        label=spec["label"],
        run_id=run_id,
        hidden_size=spec["hidden_size"],
        latent_size=spec["latent_size"],
        n_trainable_parameters=n_params,
        best_epoch=run_metadata["best_epoch"],
        best_val_loss=run_metadata["best_val_loss"],
        threshold=selected_threshold["selected_threshold"],
        validation_precision=pooled["precision"],
        validation_recall=pooled["recall"],
        validation_f1=pooled["f1"],
        validation_pre_fault_fpr=pooled["pre_fault_fpr"],
        validation_median_detection_delay=pooled["median_detection_delay"],
    )
    for ft in FAULT_TYPES:
        m = by_fault_type.get(ft, {})
        row[f"{ft}_f1"] = m.get("f1")
        row[f"{ft}_detection_delay"] = m.get("median_detection_delay")
    return row


def apply_eligibility(row, targets):
    eligible = (
        row["validation_f1"] >= targets["f1_min"]
        and row["validation_median_detection_delay"] <= targets["median_detection_delay_max_sec"]
        and row["validation_pre_fault_fpr"] <= targets["pre_fault_fpr_max"]
    )
    row["eligible"] = eligible
    return row


def select_candidate(rows):
    eligible_rows = [r for r in rows if r["eligible"]]
    if not eligible_rows:
        return None, rows
    ranked = sorted(
        eligible_rows,
        key=lambda r: (-r["validation_f1"], r["validation_median_detection_delay"], r["n_trainable_parameters"]),
    )
    return ranked[0], rows


def write_comparison_csv(rows, out_path):
    import csv
    fieldnames = [
        "candidate", "label", "run_id", "hidden_size", "latent_size", "n_trainable_parameters",
        "best_epoch", "best_val_loss", "threshold",
        "validation_precision", "validation_recall", "validation_f1",
        "validation_pre_fault_fpr", "validation_median_detection_delay",
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
    parser.add_argument("--candidate-architectures", default=os.path.join(REPO_ROOT, "configs", "model1", "candidate_architectures.json"))
    parser.add_argument("--protocol-config", default=os.path.join(REPO_ROOT, "configs", "model1", "protocol_config.json"))
    parser.add_argument("--experiments-dir", default=os.path.join(REPO_ROOT, "experiments", "model1"))
    parser.add_argument("--out-dir", default=os.path.join(REPO_ROOT, "experiments", "model1", "candidate_comparison"))
    return parser.parse_args()


def main():
    args = parse_args()
    with open(args.candidate_architectures) as f:
        candidate_spec = json.load(f)
    with open(args.protocol_config) as f:
        protocol_config = json.load(f)
    targets = protocol_config["success_targets"]

    rows = []
    for name, spec in candidate_spec["candidates"].items():
        row = load_candidate_row(name, spec, args.experiments_dir)
        row = apply_eligibility(row, targets)
        rows.append(row)

    write_comparison_csv(rows, os.path.join(args.out_dir, "comparison_table.csv"))

    selected, _ = select_candidate(rows)
    result = dict(
        targets=targets,
        tie_break_order=candidate_spec["model_selection_rule"]["tie_break_order"],
        eligible_candidates=[r["candidate"] for r in rows if r["eligible"]],
        selected_candidate=selected["candidate"] if selected else None,
        selected_run_id=selected["run_id"] if selected else None,
        rows=rows,
    )
    os.makedirs(args.out_dir, exist_ok=True)
    with open(os.path.join(args.out_dir, "comparison_result.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
