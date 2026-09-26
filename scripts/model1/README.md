# Model 1 Scripts

Runnable scripts for Model 1 (multivariate LSTM encoder-decoder anomaly detector),
organized by pipeline stage. All scripts that touch the BARO dataset take it via
`--data-dir <BARO_DATA_DIR>` -- see [docs/data/README.md](../../docs/data/README.md)
for how to obtain and set up that directory.

## `dataset_inspection/` -- read-only dataset inspection

- `inspect_dataset.py` -- structure, timestamps, sampling, duplicates, basic
  constant/missing checks, per-case and per-metric rollups.
- `inspect_schema_and_missingness.py` -- schema union/intersection, per-column
  presence by service/fault type, constant-column breakdown, missing-cell breakdown
  with pre/post-fault split.

Exact commands: [docs/model1/dataset-inspection/commands.txt](../../docs/model1/dataset-inspection/commands.txt).
Findings: [docs/model1/dataset-inspection/findings.md](../../docs/model1/dataset-inspection/findings.md).

## `protocol/` -- locked preprocessing/split/evaluation protocol

- `build_manifests.py` -- builds the deterministic 60/20/20 train/val/test case
  manifests (seeded per-combo permutation).
- `fit_scaler.py` -- fits the per-feature z-score scaler on train-split pre-fault
  rows only.
- `metrics.py` -- evaluation-metric formulas (precision/recall/F1, detection delay,
  pre-fault FPR, fault-type stratification). Importable library, also runnable
  standalone for a synthetic formula sanity check.
- `validate_protocol.py` -- runs the 5 automated protocol checks (split overlap,
  feature consistency, scaler train-only fit, no time/index leakage, fault-type
  stratification) and writes `docs/model1/protocol/validation_report.json`.

Full protocol writeup: [docs/model1/protocol/protocol.md](../../docs/model1/protocol/protocol.md).

## `data/` -- windowing library

- `dataset.py` -- the core data-loading/windowing library (feature/scaler/manifest
  loading, training-mean imputation, train/model-selection-validation/eval window
  construction). Imported by every script below, not run standalone.
- `build_train_windows.py` -- standalone driver that builds and summarizes train
  windows using `dataset.py`.

## `training/` -- training loop

- `train.py` -- trains the LSTM autoencoder (architecture from
  `models/model1/lstm_autoencoder.py`) on known-normal training windows, with
  early stopping / best-checkpoint selection on validation reconstruction loss.
  Writes `experiments/model1/<run_id>/`.

## `evaluation/` -- validation-only scoring, threshold selection, test evaluation

- `scoring.py` -- reconstruction anomaly scoring (S1: full-window MSE) against a
  frozen checkpoint, eval()/no_grad only.
- `scoring_rules.py` -- the three predeclared scoring-rule formulas (S1 full-window,
  S2 final-timestep, S3 trailing-5-timestep MSE).
- `scoring_ablation.py` -- scores validation windows under all three rules from a
  single frozen forward pass, for the scoring-rule comparison.
- `threshold_selection.py` -- validation-only, deterministic threshold-selection
  procedure (percentile-grid candidates, smallest threshold satisfying the
  pre-fault-FPR ceiling).
- `compare_candidates.py` -- aggregates multiple architecture candidates'
  validation results into one comparison table + eligibility/selection result.
- `compare_scoring_rules.py` -- same comparison, across scoring rules (S1/S2/S3).
- `test_evaluation.py` -- the one-time held-out test-set evaluation using a frozen
  checkpoint/scoring-rule/threshold; never invokes threshold selection.
- `failure_study.py` -- descriptive-only validation-vs-test generalization-gap
  analysis (score-distribution quantiles, per-case metrics, LOSS-specific
  analysis). Never computes or suggests a new threshold.

Model 1's final frozen configuration and results:
`experiments/model1/model1_final_summary.json`. Status/history:
[docs/model1/README.md](../../docs/model1/README.md).
