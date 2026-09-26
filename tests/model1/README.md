# Model 1 Tests

Eight test files, one per implementation phase. All use plain `assert`-free
check-function-returns-failure-list conventions (see any file's `main()`), not a
test framework -- run each with `python3 <file>.py [args]`; exit code 0 = all
checks passed.

Environment: see root [requirements.txt](../../requirements.txt). Files marked
"torch" below need it installed; files marked "no torch" only need numpy/pandas
(or, for `test_metrics.py`, nothing beyond the standard library).

**Not all 8 are runnable immediately from a fresh clone.** Checkpoints (`*.pt`) are
gitignored and not committed, so:

- **Runnable from a fresh clone** (no checkpoint needed -- just `<BARO_DATA_DIR>`
  where marked): `test_metrics.py`, `test_data_pipeline_leakage.py`,
  `test_lstm_autoencoder_architecture.py`, `test_training_pipeline.py`,
  `test_missing_value_imputation.py`.
- **Require a locally trained checkpoint** (marked **checkpoint required** below):
  `test_validation_scoring_and_threshold.py`, `test_scoring_rule_ablation.py`,
  `test_final_test_evaluation.py`. These will fail on a fresh clone until you run
  `python3 scripts/model1/training/train.py --data-dir <BARO_DATA_DIR> --run-id
  <some-run-id>` (or otherwise obtain a `best.pt`) first.

| File | Purpose | Dependencies | Command |
|---|---|---|---|
| `test_metrics.py` | Hand-computed unit tests for `scripts/model1/protocol/metrics.py`'s formulas (precision/recall/F1, detection delay, pre-fault FPR, fault-type stratification). | No torch, no data dir. | `python3 test_metrics.py` |
| `test_data_pipeline_leakage.py` | Confirms training/model-selection-validation windows never leak post-injection or wrong-split data; AST-checks the test manifest is never loaded. | No torch. Real data. | `python3 test_data_pipeline_leakage.py --data-dir <BARO_DATA_DIR>` |
| `test_lstm_autoencoder_architecture.py` | Shape and parameter-count checks for `models/model1/lstm_autoencoder.py`, including a deeper `num_layers=2, dropout=0.1` configurability check. Synthetic tensors only. | Torch. No data dir. | `python3 test_lstm_autoencoder_architecture.py` |
| `test_training_pipeline.py` | Training-loop correctness: parameter updates happen in train mode, validation runs under `eval()`/`no_grad`, early stopping and best-checkpoint selection use validation loss only, real pre-fault window checks, AST-checks test manifest never loaded. | Torch. Real data. | `python3 test_training_pipeline.py --data-dir <BARO_DATA_DIR>` |
| `test_missing_value_imputation.py` | Training-mean imputation policy: missing values replaced with the committed scaler mean and become exactly 0.0 after scaling; scaler never refit; no fill/interpolation logic exists; window counts/finiteness unchanged. | No torch. Real data. | `python3 test_missing_value_imputation.py --data-dir <BARO_DATA_DIR>` |
| `test_validation_scoring_and_threshold.py` | Validation-only scoring + threshold-selection pipeline: checkpoint loaded in `eval()`/`no_grad`, parameters never change, exactly 20 val cases scored, threshold candidates derived only from validation scores, correct end-time detection timestamp. | Torch. Real data. **Checkpoint required.** | `python3 test_validation_scoring_and_threshold.py --data-dir <BARO_DATA_DIR> --checkpoint <path/to/best.pt>` |
| `test_scoring_rule_ablation.py` | S1/S2/S3 scoring-rule formulas (hand-computed), eval()/no_grad scoring, frozen checkpoint unchanged, no test manifest loaded, correct end-time detection timestamp. | Torch. Real data. **Checkpoint required** (defaults to Candidate B's path -- override with `--checkpoint` if using a different run). | `python3 test_scoring_rule_ablation.py --data-dir <BARO_DATA_DIR> [--checkpoint <path/to/best.pt>]` |
| `test_final_test_evaluation.py` | Integrity checks for the one-time held-out test evaluation: checkpoint SHA-256 matches the frozen selection artifact, eval()/no_grad, exact stored threshold used (never recalculated), no threshold-selection function invoked on test scores, structural window counts. | Torch. **Checkpoint required** (reads the path recorded in `experiments/model1/final_model_selection.json`; no `--data-dir` needed since it checks already-generated artifacts). | `python3 test_final_test_evaluation.py` |

For the full protocol these tests verify, see
[docs/model1/protocol/protocol.md](../../docs/model1/protocol/protocol.md). For
what each implementation phase produced, see
[scripts/model1/README.md](../../scripts/model1/README.md).
