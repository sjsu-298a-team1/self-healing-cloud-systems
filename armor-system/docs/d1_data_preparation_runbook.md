# ARMOR D1 data-preparation runbook (Linear 298-44)

Engineering runbook for the D1 data-preparation pipeline and its Streamlit dashboard. **CPU only**: no model is trained, no ARMOR code is run, no GPU is used. Every command below was executed on macOS (Apple silicon, Python 3.14) while this runbook was written; the results are recorded in `armor-system/data/artifacts/d1/evidence/evidence.json`.

## 1. Environment (exact commands)

Run from the repository root.

```bash
python3 -m venv .venv                                              # Python 3.10+ (tested with 3.14)
.venv/bin/python -m pip install -r armor-system/dashboard/requirements.txt
.venv/bin/python -c "import numpy, scipy, matplotlib, pandas, streamlit, plotly; print('ok')"
```

`requirements.txt` pins numpy, scipy, matplotlib, pandas (pipeline) and streamlit, plotly (dashboard). The optional browser check also needs `playwright` and Google Chrome (`.venv/bin/python -m pip install playwright`; it uses the installed Chrome, no browser download).

The verified D1 release must exist at `armor-system/data/raw/armor_zenodo_21744694/` (Git-ignored, about 62 MB for D1 only). It is produced by:

```bash
python3 -I armor-system/data/tools/fetch_d1.py                      # stdlib only; D1 only, never D2; see the 298-43 report
```

## 2. Run the pipeline

```bash
.venv/bin/python armor-system/data/pipeline.py --stage all           # about 1-2 minutes
```

Stages (`--stage X` runs everything up to X): `cache`, `inspect`, `splits`, `preprocess`, `eda`, `figures`, `augmentation`, `quality`, `tests`, `evidence`. `tests` and `evidence` run only when selected or with `all`; `evidence` also runs the data stages twice in fresh processes and compares artifact hashes.

| Stage | Output (under `armor-system/data/artifacts/d1/`) |
|---|---|
| cache | `armor-system/data/processed/d1_features_v1.npz` (7,200 x 46 x 130 float32; Git-ignored) |
| inspect | `inspection/*` |
| splits | `splits/*` |
| preprocess | `preprocessing/*` |
| eda, figures | `eda/*`, `eda/figures/*.png` |
| augmentation | `augmentation/*`, `armor-system/docs/d1_augmentation_assessment.md` |
| quality | `quality/nine_stage_validation.json` plus a PASS/FAIL table on the console |
| tests, evidence | `evidence/evidence.json` |

## 3. The splits (three things kept apart)

1. **Model 1 case split, approved: 101 train / 25 validation / 84 test** (`splits/model1_split_101_25_84_v1.json`, status `approved`). Chronological and incident-group-aware, no randomness. Class counts (train / validation / test): Container Hardware 37 / 10 / 36, Container Network 32 / 6 / 22, Node CPU 10 / 3 / 8, Node Disk 18 / 5 / 14, Node Memory 4 / 1 / 4. **Validation contains a single Node Memory case, so minority-class validation is statistically unstable** and must not drive tuning on its own.
2. **Sample-level anomaly-detection timeline of the unchanged ARMOR baseline:** AD splits at 60% of the 7,200 samples (2022-05-06T16:00:00Z). The Model 1 validation/test sample boundary is aligned to it, so every post-boundary sample is in the test period. Detection evaluation is reported as two separate populations: 98 official AD events and 84 documented injection cases, never averaged.
3. **Official ARMOR FT/RCL protocol, unchanged:** first 126 / last 84 cases (`splits/official_armor_v1.json`, `approved_reproduction`). The 84 test cases are identical in both protocols.

`splits/model1_candidate_100_26_84_v1.json` is the **rejected** earlier proposal (fails S4 incident isolation, S5 boundary gap, S6 case containment); it is kept as evidence. `splits/rolling_origin_folds_v1.json` is an optional idea that is **not approved**. The pipeline raises `ApprovedSplitError` and stops instead of overriding a safeguard if the approved split ever fails a hard check or its class counts differ from the approved table.

Counting units (never added together): a **case** is one injection record (210); a **sample** is one minute of 46 x 130 features (7,200); a **window** is 7 consecutive samples (6 inputs + next step) lying wholly inside one split; an **AD event** is one timestamp in `ad_cases.pkl` (224; 98 after the AD boundary are scored). See `preprocessing/split_counts_by_unit.csv`.

## 4. Preprocessing and EDA

Components: `armor-system/data/prep/preprocess.py` (schema/numeric validation, structural-absence masks, per node-channel scaler, missing-modality indicators, windows, boundary protection, `prepare_window`). A zero is not a missing value; only node-modality blocks that are zero in every fit sample are structurally absent (6 trace, 16 log). Two fit sets, neither containing a test sample: `model1_train_period` (before the 101|25 boundary; the only fit set for Model 1, so validation never influences it) and `official_train_period` (samples at or before the AD boundary; reference for the unchanged official protocol). No feature is selected and nothing is tuned on validation or test. `preprocessing/prepared_example.json` shows one real training case from raw to prepared. EDA statistics behind model-development decisions use only the Model 1 train period; the validation period appears only in the diagnostic train-vs-validation comparison; trend and held-out-case views are labelled descriptive.

## 5. Validation and tests

```bash
.venv/bin/python armor-system/data/pipeline.py --stage quality       # nine-stage validation, PASS/FAIL table
for s in data prep dashboard; do .venv/bin/python -I -m unittest discover -s armor-system/tests/$s -p 'test_*.py'; done
```

The nine stages: dataset integrity, schema consistency, timestamp validity, class-label consistency, split reproducibility, training-only scaler fitting, temporal leakage, missing/invalid numerics, and deliberately corrupted inputs (16 cases including a clean control).

## 6. Launch and check the dashboard

```bash
armor-system/dashboard/run_dashboard.sh                  # http://localhost:8501 ; optional argument: port
.venv/bin/python armor-system/dashboard/browser_check.py # optional: drives it in headless Chrome, writes evidence/dashboard_browser_check.json
```

Pages: **1 Overview**, **2 Dataset Explorer** (schema, representative records, case filters, timestamps, live sample inspector), **3 Data Splitting** (protocol selector, checks, boundary slider, counting units), **4 EDA** (ten tabs), **5 Preprocessing** (config, raw-to-prepared example, scaler, masks, before/after, windows), **6 Data Quality**, **7 Deliverables and Evidence**. Pages read generated artifacts and show an explicit message when one is missing. Only the approved Model 1 split and the official reproduction are shown as approved; the rejected candidate and the optional folds are labelled as such.

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `D1 release not found` | Run `armor-system/data/tools/fetch_d1.py`, or check the path in section 1. |
| `feature cache missing` in the dashboard | `pipeline.py --stage cache`; only the live sample inspector and live before/after view need it. |
| Pages say "Artifact not available" | `pipeline.py --stage all`; pages never fill in values themselves. |
| `ModuleNotFoundError: streamlit/plotly` | Install `armor-system/dashboard/requirements.txt` into the interpreter you launch with (`ARMOR_PYTHON` overrides it). |
| Port in use | `run_dashboard.sh 8502`. |
| `ApprovedSplitError` | A split safeguard failed; read the message, fix the cause, do not edit manifests by hand. |
| A validation check FAILS | `quality/nine_stage_validation.json` shows which and why; fix the cause and re-run the stage. |

## 8. Remaining limitations

- Validation has one Node Memory case (and 3 Node CPU cases); per-class validation metrics are unstable. Node Memory has only 4 train and 4 test cases.
- `ad_cases.pkl` (224 events) and `cases.csv` (210 cases) differ by 21 AD-only and 7 case-only events; the origin is unexplained (ART release). No incident end times exist, so no sample-level detection labels were built.
- Features are precomputed aggregates scaled by an undocumented recipe over the full timeline; a train-only second stage cannot undo that.
- Augmentation was assessed and not adopted. Raw telemetry, D2, ARMOR execution, model training and Airflow are out of scope here.
