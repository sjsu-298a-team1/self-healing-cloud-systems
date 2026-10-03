# 298A / 298B Semester Scope Boundary

Factual scope record. Prior to this document, no 298A/298B boundary document existed
anywhere in this repository (confirmed by repo-wide search). This is the first.

Created: 2026-10-03, on branch `khushi/project-evidence-cleanup`.

## 298A (this semester)

| Item | Scope | Status |
|---|---|---|
| Model 1 (multivariate LSTM autoencoder anomaly detector) | Built, trained, evaluated | **Done.** Merged via PR #24. Held-out test: all 3 locked targets failed (see `experiments/model1/model1_final_summary.json`) — frozen, not retuned. |
| BARO baseline | Reproduced | **Done.** See `docs/baseline/baseline_reproduction.md` — Table 3 Avg@5 reproduced exactly (0.91/0.96/0.95/0.62/0.86). |
| Evaluation harness | Built | **Done.** `scripts/model1/protocol/metrics.py`, `tests/model1/` (9 test files). |
| Automated cloud pipeline | In scope | **Not started.** No cloud provider/CI-CD selected yet (`docs/infra/environment-evaluation/README.md` is historical/superseded; no replacement decision made — see `docs/planning/compute-budget-and-risks.md` §3). |
| Deployed prototype | In scope | **Not started.** No deployment artifact exists in this repository. |
| Failure study / reproducibility | Done | `experiments/model1/failure_study/failure_study.json`; `scripts/model1/demo/run_data_demo.py` (9-stage, reproducible); `tests/model1/` (9/9 passing). |
| Models 2, 3, 4 | **Design only** | See below. No training, no implementation code. |

### Models 2–4: design-only in 298A

- **Model 2 (service-graph RCA):** design only. See `docs/model2/README.md`. Where a
  service topology is used for design purposes, it is an **assumed Online Boutique
  topology**, reconstructed from a specific, pinned public version of
  `GoogleCloudPlatform/microservices-demo` and mapped onto BARO's 13 ranking
  candidates — **this is never to be described as BARO's own authoritative topology**,
  since BARO's own artifact contains no topology/version identifier (verified by
  exhaustive search of the BARO clone). No Model 2 training code exists in this
  repository.
- **Model 3 (LLM diagnosis/remediation generator):** design only. See
  `docs/model3/README.md` and `docs/literature/safe-remediation/README.md`. No
  model selected, no training data collected, no implementation code exists.
- **Model 4 (action-risk classifier):** design only. See `docs/model4/README.md`
  and `docs/literature/safe-remediation/README.md`. No model selected, no training
  data collected, no implementation code exists.

### Intended four-model pipeline (design level only)

```
Model 1 (anomaly detection) -> Model 2 (ranked root cause) -> Model 3 (diagnosis/remediation) -> Model 4 (risk gate)
```

Cross-model interface schemas are **not fixed** beyond what each model's own design
doc states. Known concretely today: Model 1's real output shape (window-level
anomaly score + threshold flag + detection timestamp, see
`scripts/model1/evaluation/scoring.py`). Everything else in this chain — Model 2's
exact ranked-output schema, Model 3's structured-output schema, and Model 4's input
contract — is **TBD**, documented as such in `docs/model2/README.md`,
`docs/model3/README.md`, and `docs/model4/README.md` respectively. No schema is
invented here to fill these gaps.

## 298B (next semester)

| Item | Scope |
|---|---|
| Model 2 implementation and training | 298B |
| Model 3 implementation, training, and adaptation | 298B |
| Model 4 implementation and training | 298B |
| Full four-model benchmark / comparison | 298B |
| Retraining / promotion / rollback system | 298B |
| Complete production-style application | 298B |

## Facts this document must not contradict

- Model 1's held-out test result is **frozen** — no retuning after seeing the failed
  result (`experiments/model1/final_model_selection.json` status: "FROZEN...").
- BARO's RCA task (service-level root-cause ranking) and Model 1's anomaly-detection
  task are **different tasks** and are not numerically compared anywhere in this
  repository.
- Any Model 2 topology referenced in design discussions is an **assumed**
  reconstruction from a pinned public Online Boutique version, **not** an
  authoritative BARO artifact.
- Models 3 and 4 remain **design-only** for the duration of 298A.
