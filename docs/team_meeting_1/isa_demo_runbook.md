# Team Meeting 1 ISA Demonstration Runbook

**Project:** AI-Driven Incident Response and Self-Healing Cloud Systems
**Repository:** `sjsu-298a-team1/self-healing-cloud-systems`
**Branch reviewed:** `main`
**Model:** Model 1, multivariate LSTM encoder-decoder anomaly detector
**Dataset:** BARO Online Boutique artifact (`fse-ob`)
**Presenters:** `[Assign names before the meeting]`

## Purpose and scope

This runbook is the reproducible sequence for the Team Meeting 1 ISA demonstration. It uses the existing Model 1 data-quality, preprocessing, validation, EDA, split, leakage-check, and metric artifacts. It does not change Model 1, its data split, preprocessing, metrics, or training/evaluation results.

Present the six official ISA checks in this exact order:

1. Raw data, provenance, and sample records
2. Cleaning and preprocessing
3. Deliberately corrupted input
4. EDA
5. Fixed split and leakage validation
6. Committed evaluation metrics

## Before the meeting

### Environment and data

Run from the repository root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Obtain the official BARO artifact using [`docs/data/README.md`](../data/README.md):

- BARO code: <https://github.com/phamquiluan/baro>
- Telemetry artifact: <https://doi.org/10.5281/zenodo.11046533>
- Required extracted directory: `<BARO_DATA_DIR>` containing the `fse-ob` directory

The raw data must remain outside Git. Its expected layout is:

```text
<BARO_DATA_DIR>/<service>_<fault_type>/<run_id>/
    simple_data.csv
    inject_time.txt
```

Replace `<BARO_DATA_DIR>` below with the absolute path to the extracted `fse-ob` directory.

### Preflight command

Run this once before the meeting and keep its output/work directory as fallback evidence:

```bash
python3 scripts/model1/demo/run_data_demo.py \
  --data-dir <BARO_DATA_DIR> \
  --work-dir ./isa_demo_work \
  --keep
```

This existing repository command runs nine internal stages, writes regenerated artifacts only to `isa_demo_work`, and compares them with the committed artifacts. The verified run completed in approximately 8 seconds and ended with:

```text
ALL STAGES PASSED   (about 8 seconds)
```

Do not rerun the final held-out Model 1 test evaluation during the meeting. The repository records that it was performed once after the architecture, scoring rule, and threshold were frozen.

---

## ISA check 1 — Raw data, provenance, and sample records

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** approximately 1–2 seconds; downloading the artifact is not a live-demo step.

### Commands

```bash
python3 scripts/model1/dataset_inspection/inspect_dataset.py \
  --data-dir <BARO_DATA_DIR> \
  --out-dir ./isa_demo_raw_inspection
```

Show one representative raw telemetry record:

```bash
python3 -c "import pandas as pd; p='<BARO_DATA_DIR>/cartservice_cpu/1/simple_data.csv'; d=pd.read_csv(p,nrows=1); print(d.iloc[:, :8].to_string(index=False))"
```

### Files and figures to show

- [`docs/data/README.md`](../data/README.md)
- [`data/model1/dataset_inspection/dataset_summary.json`](../../data/model1/dataset_inspection/dataset_summary.json)
- [`data/model1/dataset_inspection/case_summary.csv`](../../data/model1/dataset_inspection/case_summary.csv)
- `<BARO_DATA_DIR>/cartservice_cpu/1/simple_data.csv`
- BARO Zenodo provenance: <https://doi.org/10.5281/zenodo.11046533>

### Expected output

| Property | Expected value |
|---|---:|
| Cases | 100 |
| Service/fault combinations | 20 |
| Target services | 5 |
| Fault types | `cpu`, `delay`, `loss`, `mem` |
| Rows per case | 721 |
| Time span | 720 seconds |
| Sampling | 1 Hz |
| Duplicate rows/timestamps | 0 cases |
| Injection location | midpoint of every case |

The verified sample begins with `time`, `adservice_cpu`, `cartservice_cpu`, `checkoutservice_cpu`, `currencyservice_cpu`, `emailservice_cpu`, `frontend_cpu`, and `main_cpu`.

### Provenance and terms to state

- This is BARO's Online Boutique telemetry artifact, not a newly collected team dataset.
- The telemetry artifact is separate from the BARO analysis code and the Online Boutique application source.
- The repository's provenance notes identify the telemetry artifact as CC BY 4.0, the BARO analysis code as MIT, and the Online Boutique application source as Apache 2.0.
- Raw telemetry stays outside Git; only derived, reviewed summaries are committed.

### Talking points

1. “We begin with the raw cases and recorded injection timestamps before preprocessing.”
2. “The artifact has 100 cases: 5 services, 4 fault types, and 5 runs per combination.”
3. “Each case is sampled at 1 Hz for 720 seconds, with the injection at the midpoint.”

### Fallback

Show `dataset_summary.json`, `case_summary.csv`, `docs/data/README.md`, and the saved preflight output in `isa_demo_work`. State whether the raw record was shown live or from previously captured evidence.

---

## ISA check 2 — Cleaning and preprocessing

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** approximately 1–2 seconds for inspection and approximately 1 second for the missing-value test.

### Commands

```bash
python3 scripts/model1/dataset_inspection/inspect_schema_and_missingness.py \
  --data-dir <BARO_DATA_DIR> \
  --out-dir ./isa_demo_raw_inspection
```

```bash
python3 tests/model1/test_missing_value_imputation.py \
  --data-dir <BARO_DATA_DIR>
```

For the before/after worked example, show Stage 5 from the verified preflight command:

```bash
python3 scripts/model1/demo/run_data_demo.py \
  --data-dir <BARO_DATA_DIR> \
  --work-dir ./isa_demo_work \
  --keep
```

### Files to show

- [`data/model1/dataset_inspection/schema_report.json`](../../data/model1/dataset_inspection/schema_report.json)
- [`data/model1/dataset_inspection/missing_cells_detail.csv`](../../data/model1/dataset_inspection/missing_cells_detail.csv)
- [`data/model1/dataset_inspection/column_presence.csv`](../../data/model1/dataset_inspection/column_presence.csv)
- [`configs/model1/features.json`](../../configs/model1/features.json)
- [`configs/model1/scaler.json`](../../configs/model1/scaler.json)
- [`configs/model1/protocol_config.json`](../../configs/model1/protocol_config.json)
- [`scripts/model1/data/dataset.py`](../../scripts/model1/data/dataset.py)
- [`tests/model1/test_missing_value_imputation.py`](../../tests/model1/test_missing_value_imputation.py)

### Expected evidence

- 62 telemetry columns appear in the union.
- 55 common telemetry features are retained.
- 7 non-universal columns are excluded.
- 2,630 raw missing cells are reported.
- 90 of 100 cases contain at least one locally constant column.
- The scaler is fitted on 60 training cases × 360 pre-fault rows = 21,600 rows.
- Missing locked-feature values are replaced with the training-only feature mean and become 0.0 after z-score scaling.
- No forward fill, backward fill, interpolation, scaler refit, or test-statistic use occurs.

The missing-value test must end with:

```text
[PASS] missing_replaced_with_committed_mean
[PASS] imputed_values_become_zero_after_scaling
[PASS] non_missing_values_scale_unchanged
[PASS] scaler_not_refit
[PASS] no_fill_or_interpolation_logic
[PASS] window_counts_and_finiteness_unchanged
[PASS] manifests_and_features_unchanged

ALL MISSING-VALUE IMPUTATION TESTS PASSED: True
```

The verified worked example showed a missing `adservice_cpu` value in `currencyservice_cpu/1`, imputed with mean `1.135116`, standard deviation `0.441552`, and standardized value `0.000000`.

### Talking points

1. “We measure missingness and schema variation instead of assuming the raw data is clean.”
2. “The 55-feature intersection gives every case the same feature meaning and order.”
3. “Preprocessing is train-only: validation and test data cannot influence the scaler.”

### Fallback

Show `schema_report.json`, `features.json`, `scaler.json`, the missing-value test source, and the saved Stage 5 output.

---

## ISA check 3 — Deliberately corrupted input

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** approximately 8 seconds if the consolidated demo is rerun.

### Command

The existing repository exposes the deliberate corrupted-input demonstration inside Stage 6 of `run_data_demo.py`. Use the verified command:

```bash
python3 scripts/model1/demo/run_data_demo.py \
  --data-dir <BARO_DATA_DIR> \
  --work-dir ./isa_demo_work \
  --keep
```

Do not create a separate validation script. Stage 6 loads a valid training case, copies it in memory, drops one required feature, and checks the copy. The raw CSV is not modified.

### Files to show

- [`scripts/model1/demo/run_data_demo.py`](../../scripts/model1/demo/run_data_demo.py), Stage 6 and `_structural_check`.
- [`configs/model1/features.json`](../../configs/model1/features.json).
- The Stage 6 output in the terminal or saved preflight record.

### Expected output

```text
[PASS] Valid sample (cartservice_cpu/1): PASS -- all 55 required features present and numeric
[PASS] Corrupted sample: FAIL -- required feature missing: adservice_cpu
```

The word `FAIL` is expected for the deliberately corrupted sample. The overall stage and overall demo must pass.

### What this proves

- A valid sample passes structural validation.
- Removing a required feature is detected before model use.
- The corruption exists only in memory; raw data remains unchanged.
- The demo includes a negative control instead of showing only successful inputs.

### Talking points

1. “The validator catches a missing feature rather than silently accepting a malformed input.”
2. “This is a schema-validation negative control, separate from the scaler-contamination negative control.”
3. “The raw artifact is protected because the test modifies only a DataFrame copy.”

### Fallback

Show the Stage 6 source and captured output from `isa_demo_work`. Clearly label it as captured evidence if it was not run live.

---

## ISA check 4 — EDA

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** approximately 5 seconds to regenerate EDA into a separate output directory.

### Command

```bash
python3 scripts/model1/eda/build_eda.py \
  --data-dir <BARO_DATA_DIR> \
  --output-root ./isa_eda_rerun
```

The verified command returned:

```text
{"n_known_normal_rows": 21600, "extreme_cells": 2596, "affected_row_fraction": 0.04513888888888889, "raw_files_unchanged": true}
```

Show the committed presentation figures, not unreviewed replacements:

- [`01_coverage.png`](../model1/eda/figures/01_coverage.png): 5 services × 4 faults × 5 runs.
- [`02_missingness.png`](../model1/eda/figures/02_missingness.png): missingness concentration.
- [`03_distributions.png`](../model1/eda/figures/03_distributions.png): CPU, memory, latency, and tails.
- [`04_correlations.png`](../model1/eda/figures/04_correlations.png): strongest correlation pairs.
- [`05_injection_timelines.png`](../model1/eda/figures/05_injection_timelines.png): fault-injection examples.
- [`06_extreme_values.png`](../model1/eda/figures/06_extreme_values.png): standardized extreme-value evidence.

Also show [`docs/model1/eda/findings.md`](../model1/eda/findings.md) and [`docs/model1/eda/README.md`](../model1/eda/README.md).

### Expected evidence and talking points

| Figure | Expected message |
|---|---|
| Coverage | All 100 cases and all 20 service/fault combinations are represented. |
| Missingness | Exactly 2,630 raw missing cells are concentrated in a small number of columns/cases. |
| Distributions | Feature scales differ substantially, supporting per-feature normalization. |
| Correlations | The strongest reported pair is `frontend_latency-50` and `recommendationservice_latency-50`, `r = 0.9997`; correlation is not causality. |
| Injection timelines | The 360-second boundary is the recorded injection timestamp; the shaded region is the post-injection evaluation region. |
| Extreme values | 2,596 of 1,188,000 known-normal training cells exceed `|z| > 5`, affecting 4.51% of rows; no records are removed. |

State the limitation: the artifact has an injection timestamp but no verified fault-end timestamp. Therefore, `t >= inject_time` is called the post-injection evaluation region, not a guaranteed active-fault label.

### Fallback

Show the six committed PNGs, `findings.md`, and the EDA CSV outputs under `data/model1/eda/`.

---

## ISA check 5 — Fixed split and leakage validation

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** approximately 1–2 seconds for the leakage test; approximately 8 seconds for full regeneration/comparison.

### Commands

Use the consolidated demo to regenerate split artifacts in a work directory and compare them with the committed artifacts:

```bash
python3 scripts/model1/demo/run_data_demo.py \
  --data-dir <BARO_DATA_DIR> \
  --work-dir ./isa_demo_work \
  --keep
```

Run the explicit leakage test:

```bash
python3 tests/model1/test_data_pipeline_leakage.py \
  --data-dir <BARO_DATA_DIR>
```

Run protocol validation while writing the report to the work directory rather than overwriting the committed report:

```bash
python3 scripts/model1/protocol/validate_protocol.py \
  --data-dir <BARO_DATA_DIR> \
  --report-path ./isa_demo_work/validation_report.json
```

### Files to show

- [`data/model1/manifests/train_cases.json`](../../data/model1/manifests/train_cases.json)
- [`data/model1/manifests/val_cases.json`](../../data/model1/manifests/val_cases.json)
- [`data/model1/manifests/test_cases.json`](../../data/model1/manifests/test_cases.json)
- [`data/model1/manifests/manifest_summary.csv`](../../data/model1/manifests/manifest_summary.csv)
- [`configs/model1/split_seed.json`](../../configs/model1/split_seed.json)
- [`docs/model1/protocol/validation_report.json`](../model1/protocol/validation_report.json)
- [`tests/model1/test_data_pipeline_leakage.py`](../../tests/model1/test_data_pipeline_leakage.py)
- [`docs/model1/protocol/protocol.md`](../model1/protocol/protocol.md)

### Expected split output

```text
train: 60 cases
validation: 20 cases
test: 20 cases
```

For each of the 20 service/fault combinations, run IDs 1–5 are deterministically shuffled using seed `298`; 3 go to train, 1 to validation, and 1 to test. The split unit is the whole case, not an individual row or window.

The consolidated demo must show:

```text
[PASS] train_cases: 60 cases (expected 60)
[PASS] val_cases: 20 cases (expected 20)
[PASS] test_cases: 20 cases (expected 20)
[PASS] splits are pairwise disjoint (no case in two splits)
[PASS] splits cover all 100 cases exactly once
[PASS] train_cases.json: regenerated output is identical to the committed artifact
[PASS] val_cases.json: regenerated output is identical to the committed artifact
[PASS] test_cases.json: regenerated output is identical to the committed artifact
```

The leakage test must end with:

```text
[PASS] locked_feature_list
[PASS] split_disjoint
[PASS] scaler_not_refit
[PASS] train_windows_only_from_train_cases
[PASS] train_windows_strictly_pre_fault
[PASS] train_tensor_shape
[PASS] train_window_time_contiguity
[PASS] eval_tensor_shape
[PASS] eval_windows_labeled_both_regions

ALL LEAKAGE TESTS PASSED: True
```

Protocol validation must show:

```text
[PASS] split_overlap
[PASS] feature_consistency
[PASS] scaler_train_only
[PASS] no_time_index_leakage
[PASS] fault_type_stratification

ALL CHECKS PASSED: True
```

### Talking points

1. “The same case cannot contribute rows to multiple splits.”
2. “The seed and exact per-combination permutations are version-controlled.”
3. “The leakage test verifies that training windows are pre-fault, train-only, contiguous, and built from the locked feature list.”

### Fallback

Show the committed manifests, `split_seed.json`, `validation_report.json`, and test source. Label the evidence as committed/captured if the live command cannot run.

---

## ISA check 6 — Committed evaluation metrics

**Presenter:** `[Name]`
**Handoff:** `[Name]`
**Runtime:** less than 1 second for formula tests. Do not rerun final held-out evaluation.

### Commands

```bash
python3 scripts/model1/protocol/metrics.py
```

```bash
python3 tests/model1/test_metrics.py
```

The verified tests include perfect detection, false positives and missed anomalies, no post-injection detection, and median-delay handling. They must end with:

```text
metrics.py: all synthetic formula sanity checks passed
ALL TESTS PASSED: True
```

### Files to show

- [`scripts/model1/protocol/metrics.py`](../../scripts/model1/protocol/metrics.py)
- [`tests/model1/test_metrics.py`](../../tests/model1/test_metrics.py)
- [`docs/model1/protocol/protocol.md`](../model1/protocol/protocol.md)
- [`configs/model1/protocol_config.json`](../../configs/model1/protocol_config.json)
- [`experiments/model1/model1_final_summary.json`](../../experiments/model1/model1_final_summary.json)
- [`experiments/model1/candidate_B_h32_z16_seed42/final_test/test_metrics.json`](../../experiments/model1/candidate_B_h32_z16_seed42/final_test/test_metrics.json)
- [`experiments/model1/candidate_B_h32_z16_seed42/final_test/test_per_fault_metrics.csv`](../../experiments/model1/candidate_B_h32_z16_seed42/final_test/test_per_fault_metrics.csv)
- [`experiments/model1/final_model_selection.json`](../../experiments/model1/final_model_selection.json)

### Metrics and rationale

| Metric | Why it is relevant | Implementation/protocol |
|---|---|---|
| Precision | Limits false alerts that can create operator fatigue or unsafe downstream actions. | `metrics.py`, `protocol.md` |
| Recall | Measures how much of the post-injection evaluation region is detected. | `metrics.py`, `protocol.md` |
| F1 | Balances precision and recall in one detection score. | `metrics.py`, `protocol.md` |
| Pre-fault FPR | Measures false alerts in the verified known-normal region `t < inject_time`. | `metrics.py`, `protocol.md` |
| Median detection delay | Measures how soon an incident becomes actionable; misses are reported separately. | `metrics.py`, `protocol.md` |
| Fault-type-stratified metrics | Prevents CPU, memory, delay, and loss behavior from being hidden by one pooled score. | `protocol_config.json`, `protocol.md` |

### Locked targets and committed results

Locked targets:

```text
F1 >= 0.82
median detection delay <= 10 seconds
pre-fault FPR <= 0.05
```

Frozen final configuration: Candidate B, LSTM encoder-decoder, hidden size 32, latent size 16, seed 42, scoring rule S2 (final-timestep MSE), validation-selected threshold `0.8249893178835667`.

| Split | Precision | Recall | F1 | Pre-fault FPR | Median delay | Target result |
|---|---:|---:|---:|---:|---:|---|
| Validation | 0.944 | 0.774 | 0.850 | 0.050 | 10 s | All three passed |
| Held-out test | 0.842 | 0.746 | 0.791 | 0.152 | 12 s | All three failed |

The held-out result must be shown honestly. The repository records a validation-to-test generalization gap and states that no post-test tuning, retraining, threshold recalibration, or second test evaluation occurred.

### Limitation to state

The artifact provides an injection timestamp but no verified fault-end timestamp. `t >= inject_time` follows the BARO evaluation convention and is called the post-injection evaluation region; it is not claimed to be confirmed active-fault ground truth at every later timestamp.

### Talking points

1. “The metrics were defined in the protocol and checked with hand-computed unit tests before final evaluation.”
2. “F1 is accompanied by false-positive rate and detection delay because safe incident response needs both accuracy and timely, low-noise alerts.”
3. “The held-out test result is weaker than validation, and we report that generalization gap instead of tuning after seeing it.”

### Fallback

Show the metric implementation, independent tests, frozen summary, and committed final-test JSON/CSV files. Do not replace the committed test result with a newly calculated value.

---

## Final six-check handoff table

| Order | Check | Primary evidence | Presenter |
|---:|---|---|---|
| 1 | Raw data/provenance/sample | `inspect_dataset.py`, `docs/data/README.md`, raw sample | `[Name]` |
| 2 | Cleaning/preprocessing | schema inspection, missing-value test, Stage 5 | `[Name]` |
| 3 | Corrupted input | Stage 6 of `run_data_demo.py` | `[Name]` |
| 4 | EDA | six committed figures and `findings.md` | `[Name]` |
| 5 | Split/leakage | manifests, leakage test, protocol validation | `[Name]` |
| 6 | Metrics | metric tests and frozen evaluation artifacts | `[Name]` |

## PR and Linear completion evidence

Before moving the Linear issue to Done:

1. Review presenter names, local data path, and handoffs.
2. Execute the preflight and the six checks from a clean checkout.
3. Save terminal output or a run-through record confirming the commands work.
4. Create a GitHub branch and PR containing `docs/team_meeting_1/isa_demo_runbook.md`.
5. Link the PR and run-through evidence to the Linear issue.
6. Obtain review approval before marking the issue Done.

This runbook was created in a local working copy only. It has not been committed or pushed to GitHub.
