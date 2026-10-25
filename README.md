# AI-Driven Incident Response and Self-Healing Cloud Systems

SJSU DATA 298A/298B capstone, Topic 6 (Team 1).

> **Status: migration in progress.** The ARMOR-based architecture below is **planned, not built**. No new model, DAG, dataset, backend, frontend or deployment exists yet. Everything that did exist was archived unchanged under `old/`.

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
| `armor-system/` | The new implementation (currently empty scaffolding: airflow, data, baselines, models, evaluation, backend, frontend, deployment, configs, tests, docs). |
| `old/` | The previous implementation and all earlier submissions, archived with contents unchanged: LSTM autoencoder, BARO baseline reproduction evidence, experiments, EDA, manifests, literature reviews, Checkpoint 1 material, tests. See [`old/README.md`](old/README.md). |

## Recovering the original project

The commit before this migration is preserved by the Git tag `pre-armor-migration-2026-10-28` (commit `31ffc3739e317eda3a828af2593b53479da53424`):

```bash
git checkout pre-armor-migration-2026-10-28        # original runnable layout, detached HEAD
```

Model checkpoints (`*.pt`) were never tracked in Git; see `old/README.md`.
