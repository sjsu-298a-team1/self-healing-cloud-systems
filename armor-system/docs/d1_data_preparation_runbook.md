# ARMOR D1 data-preparation runbook (Linear 298-44)

Engineering runbook for the D1 data-preparation pipeline and its Streamlit dashboard. CPU only; no model is trained and no ARMOR code is run.

## 1. Environment

- macOS or Linux, Python 3.10+ (tested with 3.14). Repository virtual environment: `.venv` (Git-ignored).
- Dependencies for the pipeline: `numpy`, `scipy`, `matplotlib`. For the dashboard: `streamlit`, `plotly`, `pandas` (versions in `armor-system/dashboard/requirements.txt`).

```bash
python3 -m venv .venv                      # once
.venv/bin/python -m pip install -r armor-system/dashboard/requirements.txt
```

- The verified D1 release must exist at `armor-system/data/raw/armor_zenodo_21744694/` (Git-ignored). It is produced by `armor-system/data/tools/fetch_d1.py` (Linear 298-43, PR #34). Nothing here downloads data.

## 2. Run the pipeline

```bash
.venv/bin/python armor-system/data/pipeline.py --stage all
```

Stages run in this order and `--stage X` runs everything up to X: `cache`, `inspect`, `splits`, `preprocess`, `eda`, `figures`, `augmentation`, `quality`, `tests`, `evidence` (`tests` and `evidence` only when selected or with `all`). A full run takes well under a minute on a laptop.

| Stage | Output (under `armor-system/data/artifacts/d1/`) |
|---|---|
| cache | `armor-system/data/processed/d1_features_v1.npz` (7,200 x 46 x 130 float32; Git-ignored) |
| inspect | `inspection/*` |
| splits | `splits/*` |
| preprocess | `preprocessing/*` |
| eda, figures | `eda/*`, `eda/figures/*.png` |
| augmentation | `augmentation/*`, `armor-system/docs/d1_augmentation_assessment.md` |
| quality | `quality/nine_stage_validation.json` (and a PASS/FAIL table on the console) |
| tests, evidence | `evidence/evidence.json` |

## 3. Reproduce the splits

`splits` rebuilds three manifests deterministically (no randomness) from `cases.csv` order and the sample timestamps:

- `official_armor_v1`: ARMOR's own case split (126 / 84). Approved reproduction.
- `model1_candidate_100_26_84_v1`: the proposed 100 / 26 / 84. **Fails hard checks** (S4 incident isolation, S5 boundary gap, S6 case extent) and is marked `usable: false`.
- `model1_alternative_v1`: train/validation boundary moved to the nearest safe index (see `splits/boundary_scan.json`), same 84 test cases. **Pending approval.**

Each manifest has a `content_sha256`; Stage 5 of the validation rebuilds all manifests and compares hashes with the committed files. Checks S1-S9 are defined in `armor-system/data/prep/splits.py`.

## 4. EDA and preprocessing outputs

`eda/` holds the tables behind every plot, `eda_findings.json` (each finding carries its computed evidence) and PNG figures. Model-development statistics use only samples at or before the official AD boundary; temporal trends, descriptive statistics and held-out-case rows are labelled descriptive. Preprocessing components are in `armor-system/data/prep/preprocess.py`; the configuration and its hash are in `preprocessing/preprocessing_config_v1.json`.

## 5. Validation and tests

```bash
.venv/bin/python armor-system/data/pipeline.py --stage quality      # nine-stage validation, PASS/FAIL table
for s in data prep dashboard; do .venv/bin/python -I -m unittest discover -s armor-system/tests/$s -p 'test_*.py'; done
```

The nine stages are: dataset integrity, schema consistency, timestamp validity, class-label consistency, split reproducibility, training-only scaler fitting, temporal leakage, missing/invalid numerics, and deliberately corrupted inputs (14 cases including a clean control).

## 6. Launch the dashboard

```bash
armor-system/dashboard/run_dashboard.sh          # http://localhost:8501  (optional argument: port)
```

Pages: **1 Overview** (counts, provenance, work completed vs pending), **2 Dataset Explorer** (schema, representative records, case filters, timestamps, live sample inspector), **3 Data Splitting** (protocol selector, checks, boundary what-if slider, fold table), **4 EDA** (ten tabs), **5 Preprocessing** (config, scaler, masks, before/after, windows), **6 Data Quality** (nine stages, corruption cases, tests, limitations), **7 Deliverables and Evidence** (artifact index, test run, PR and Linear links). The dashboard reads generated artifacts and shows an explicit message when one is missing.

## 7. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `D1 release not found` | Run `armor-system/data/tools/fetch_d1.py` (298-43) or check the path above. |
| `feature cache missing` in the dashboard | Run `pipeline.py --stage cache`. Only the Live sample inspector and live before/after view need it. |
| Dashboard pages say "Artifact not available" | Run `pipeline.py --stage all`; pages never fill in values themselves. |
| `ModuleNotFoundError: streamlit/plotly` | Install `armor-system/dashboard/requirements.txt` into the venv you launch with (`ARMOR_PYTHON` overrides the interpreter). |
| Port already in use | `run_dashboard.sh 8502`. |
| A validation check FAILS | The JSON in `quality/` shows which check and why; do not edit manifests by hand, re-run the stage after fixing the cause. |

## 8. Remaining limitations

- The proposed 100 / 26 / 84 split is unusable (fails hard checks); the alternative needs approval before any Model 1 use.
- The Node Memory class has one validation case in the 100/26-style splits; per-class validation metrics are unstable.
- `ad_cases.pkl` (224 events) and `cases.csv` (210 cases) differ by 21 AD-only and 7 case-only events; the origin is unexplained (ART release).
- No incident end times exist; no sample-level detection labels were built.
- Features are precomputed aggregates scaled by an undocumented recipe over the full timeline.
- Augmentation was assessed and not adopted. Raw telemetry, D2, model training and Airflow remain out of scope.
