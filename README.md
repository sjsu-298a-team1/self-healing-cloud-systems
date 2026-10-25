# AI-Driven Incident Response and Self-Healing Cloud Systems

SJSU DATA 298A/298B capstone, Topic 6 (Team 1).

> **Status (see [`START_HERE.md`](START_HERE.md) for what exists and what was actually run):** ARMOR D1 data acquisition, verification, split manifests, preprocessing, EDA, validation and a Streamlit dashboard are **implemented and tested** (Linear 298-43 and 298-44). **No ARMOR baseline run, Model 1, Airflow DAG, backend, frontend or deployment exists yet**; those parts below are planned. The previous implementation is archived unchanged under `old/`.

## Project direction

- **Published baseline: ARMOR (ASE 2026)** — "ARMOR: A Robust Self-Supervised Framework for Root Cause Analysis in Microservices under Missing Modality". It will be reproduced separately from our four models. *(Planned; reproduction not started.)*
- **Model 1 (298A)** — multimodal Transformer for incident detection and fault-type classification, with self-supervised pretraining followed by supervised fine-tuning. Planned evaluation: detection F1, fault-type macro-F1, missing-modality robustness, and label-budget testing at 10%, 25%, 50% and 100%. *(Planned.)*
- **Model 2 (298B)** — graph-based root-cause localization. *(Planned.)*
- **Model 3 (298B)** — grounded LLM remediation planner. *(Planned.)*
- **Model 4 (298B)** — learned action-risk model. *(Planned.)*
- **Apache Airflow** is the required pipeline orchestrator. *(Planned; no DAG exists.)*

## Repository layout

| Path | Contents |
|---|---|
| `armor-system/` | The new implementation. **Implemented:** `data/` (D1 acquisition tools, preparation pipeline, committed artifacts), `dashboard/`, `tests/`, `docs/` (D1 validation report, runbook, augmentation assessment). **Empty scaffolding only:** `airflow/`, `baselines/`, `models/`, `evaluation/`, `backend/`, `frontend/`, `deployment/`, `configs/`. |
| `old/` | The previous implementation and all earlier submissions, archived with contents unchanged: LSTM autoencoder, BARO baseline reproduction evidence, experiments, EDA, manifests, literature reviews, Checkpoint 1 material, tests. See [`old/README.md`](old/README.md). |

## Key references

- ARMOR paper: [arXiv 2603.25538](https://arxiv.org/abs/2603.25538); official artifacts (code, D1/D2 data, released checkpoints): [Zenodo record 21744694](https://zenodo.org/records/21744694) (CC-BY-4.0); D1 originates from the public [ART repository](https://github.com/bbyldebb/ART).
- Linear board: [298A Team 1](https://linear.app/298a-team-1-self-healing-cloud) (data preparation: 298-43, 298-44).
- Dataset provenance and checksums: `armor-system/data/manifests/armor_d1/`; engineering runbook: `armor-system/docs/d1_data_preparation_runbook.md`.

## Recovering the original project

The commit before this migration is preserved by the Git tag `pre-armor-migration-2026-10-28` (commit `31ffc3739e317eda3a828af2593b53479da53424`):

```bash
git checkout pre-armor-migration-2026-10-28        # original runnable layout, detached HEAD
```

Model checkpoints (`*.pt`) were never tracked in Git; see `old/README.md`.
