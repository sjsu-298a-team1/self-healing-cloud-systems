# Model 1 Configs

Locked configuration artifacts for Model 1 (multivariate LSTM encoder-decoder
anomaly detector), all committed and treated as frozen once produced by the
scripts under [scripts/model1/](../../scripts/model1/).

| File | Produced by | Contents |
|---|---|---|
| `features.json` | `scripts/model1/protocol/build_manifests.py` (derived from dataset inspection) | The locked 55-feature list used as model input. |
| `protocol_config.json` | Hand-authored, versioned alongside protocol decisions | Full locked protocol: windowing, normalization/imputation policy, labeling, metrics, success targets. See [docs/model1/protocol/protocol.md](../../docs/model1/protocol/protocol.md). |
| `scaler.json` | `scripts/model1/protocol/fit_scaler.py` | Per-feature z-score mean/std, fit on train-split pre-fault rows only; never refit after Phase 3. |
| `split_seed.json` | `scripts/model1/protocol/build_manifests.py` | The seed and exact per-combo permutation used to produce the 60/20/20 case split. |
| `training_config.json` | Hand-authored | The frozen baseline (Candidate A, h64/z32) training hyperparameters: seed, optimizer, batch size, epochs, early stopping, missing-value policy. |
| `training_config_candidate_{B,C,D}.json` | Copies of `training_config.json` with only `model.hidden_size`/`model.latent_size` changed | Predeclared architecture-capacity candidates compared in `experiments/model1/candidate_comparison/`. |
| `candidate_architectures.json` | Hand-authored, predeclared before training B/C/D | The four candidate architectures (A/B/C/D), frozen settings shared across all of them, and the model-selection eligibility/tie-break rule. |

Model 1's final frozen selection (which candidate, scoring rule, and threshold
actually won) is recorded in `experiments/model1/final_model_selection.json`, not
here -- these files are frozen *inputs* to that decision, not the decision itself.
