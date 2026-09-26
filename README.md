# self-healing-cloud-systems
AI-driven system for detecting, diagnosing, and safely remediating cloud infrastructure incidents using ML, LLMs, and automated cloud monitoring.

## Current direction

- **Active benchmark/data direction:** BARO + Online Boutique. See [docs/baseline/README.md](docs/baseline/README.md).
- **Reproduced published baseline:** BARO (Pham, Ha, Zhang, FSE 2024) — Table 3 coarse-grained RCA, Online Boutique.
- **Model 1** (multivariate LSTM encoder-decoder anomaly detector): **complete and merged** via [PR #24](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/24). See [docs/model1/README.md](docs/model1/README.md).
- **SMD / CausalRCA** materials in this repository (`docs/checkpoint-1/`, `docs/abstract/`, parts of `docs/presentations/`, `docs/baseline/baseline-selection/`, `docs/infra/environment-evaluation/`, `docs/data/dataset-benchmark-evaluation/`) reflect the **historical Checkpoint 1 direction**, later superseded by BARO/Online Boutique. See [docs/checkpoint-1/README.md](docs/checkpoint-1/README.md) for context.

## Repository layout

```
configs/<model>/     locked configuration artifacts (features, scaler, protocol, training config)
data/<model>/        generated dataset-inspection outputs + split manifests (no raw datasets)
docs/<model>/        protocol, findings, and status documentation for that model
docs/baseline/       BARO published-baseline selection and reproduced result
docs/checkpoint-1/   historical Checkpoint 1 (SMD/CausalRCA) evidence
docs/literature/     paper-by-paper literature reviews (kept as reference material)
experiments/<model>/ training-run artifacts (config snapshot, history, metrics) -- checkpoints/*.pt are gitignored
models/<model>/      model architecture code (e.g. the LSTM autoencoder)
scripts/<model>/     runnable scripts: data pipeline, protocol, training, evaluation
tests/<model>/       test suites for that model's code and pipeline
```

`<model>` is currently only `model1`; see "Adding a new model" below for the convention.

## Local setup

This repo needs one Python environment with `numpy`, `pandas`, and `torch` installed
(one environment can run every script in the repo -- verified; see
[requirements.txt](requirements.txt) for exact versions and how they were verified,
not guessed). Verified against **Python 3.14.4**; other Python 3.x versions were not
tested against this codebase.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`matplotlib` is intentionally not in `requirements.txt` -- no committed script
imports it. See `requirements.txt` for how to install it separately if you want to
regenerate the historical loss-curve figures under `experiments/model1/`.

## Dataset setup

Model 1 and the BARO baseline reproduction both use the BARO Online Boutique
telemetry artifact, which is **not** part of this repository. See
[docs/data/README.md](docs/data/README.md) for exactly where to get it, the expected
directory layout, and how to point scripts at your local copy via `--data-dir
<BARO_DATA_DIR>`.

## Running the Model 1 pipeline

Once you have `<BARO_DATA_DIR>` set up:

```bash
# 1. Dataset inspection (see docs/model1/dataset-inspection/commands.txt)
cd scripts/model1/dataset_inspection
python3 inspect_dataset.py --data-dir <BARO_DATA_DIR> --out-dir ../../../data/model1/dataset_inspection
python3 inspect_schema_and_missingness.py --data-dir <BARO_DATA_DIR> --out-dir ../../../data/model1/dataset_inspection

# 2. Protocol validation (see docs/model1/protocol/protocol.md)
cd ../protocol
python3 build_manifests.py --data-dir <BARO_DATA_DIR> --inspection-dir ../../../data/model1/dataset_inspection
python3 fit_scaler.py --data-dir <BARO_DATA_DIR>
python3 validate_protocol.py --data-dir <BARO_DATA_DIR>

# 3. Tests -- see tests/model1/README.md for the full list. Not all 8 are runnable
#    from a fresh clone: 5 need only --data-dir; 3 additionally need a locally
#    trained checkpoint (*.pt files are gitignored, not committed).
cd ../../../tests/model1
python3 test_metrics.py  # no data-dir or checkpoint needed; start here
python3 test_data_pipeline_leakage.py --data-dir <BARO_DATA_DIR>
```

Model 1's own status, frozen configuration, and results are documented in
[docs/model1/README.md](docs/model1/README.md) and
`experiments/model1/model1_final_summary.json`.

## Adding a new model

Model 1 is the reference pattern for any future model (Model 2, 3, ...). Follow the
same per-model directory convention across the repo, using `modelN` in place of
`model1`:

```
models/modelN/      architecture code only
scripts/modelN/      data pipeline, protocol, training, evaluation scripts
configs/modelN/      locked config artifacts
data/modelN/          generated dataset-inspection outputs + split manifests
experiments/modelN/  training-run artifacts (never commit checkpoints -- see .gitignore)
tests/modelN/         test suites
docs/modelN/          protocol/findings/status documentation
```

Keep each model's work self-contained under its own `modelN` subdirectory in every
top-level folder, rather than mixing multiple models' files together.
