# self-healing-cloud-systems
AI-driven system for detecting, diagnosing, and safely remediating cloud infrastructure incidents using ML, LLMs, and automated cloud monitoring.

## Current direction

- **Active benchmark/data direction:** BARO + Online Boutique. See [docs/baseline/README.md](docs/baseline/README.md).
- **Reproduced published baseline:** BARO (Pham, Ha, Zhang, FSE 2024) — Table 3 coarse-grained RCA, Online Boutique.
- **Model 1** (multivariate LSTM encoder-decoder anomaly detector): **complete and merged** via [PR #24](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/24). See [docs/model1/README.md](docs/model1/README.md).
- **SMD / CausalRCA** materials in this repository (`docs/checkpoint-1/`, `docs/abstract/`, parts of `docs/presentations/`, `docs/baseline/baseline-selection/`, `docs/infra/environment-evaluation/`, `docs/data/dataset-benchmark-evaluation/`) reflect the **historical Checkpoint 1 direction**, later superseded by BARO/Online Boutique. See [docs/checkpoint-1/README.md](docs/checkpoint-1/README.md) for context.
