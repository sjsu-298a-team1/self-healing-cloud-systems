# Model 1 Split Manifests

Model 1's deterministic, seeded train/val/test case-ID manifests over the BARO
Online Boutique case folders. Does not contain the raw BARO dataset itself (see
repository root `.gitignore`) -- only which case IDs belong to which split.

| File | Contents |
|---|---|
| `train_cases.json` | 60 case IDs used for training (and model-selection validation loss is computed on the separate `val_cases.json` set, never on these). |
| `val_cases.json` | 20 case IDs used for model-selection validation loss / early stopping, and later for threshold selection. |
| `test_cases.json` | 20 case IDs reserved for the one-time held-out test evaluation. Never loaded by any script before `scripts/model1/evaluation/test_evaluation.py`. |
| `manifest_summary.csv` | Human-readable per-case view of the split assignment (service, fault type, run, split). |

Produced by `scripts/model1/protocol/build_manifests.py`, using the seed and
per-combo permutation recorded in `configs/model1/split_seed.json`. Split rule,
disjointness guarantees, and leakage checks are documented in
[docs/model1/protocol/protocol.md](../../../docs/model1/protocol/protocol.md) §2-3
and verified by `scripts/model1/protocol/validate_protocol.py`.
