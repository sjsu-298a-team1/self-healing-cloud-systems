# Model 1 two-stage training and validation interface (Linear 298-51, infrastructure only)

**Status: infrastructure implemented and tested. No full training run, no validation run.** The tests do at most three optimizer steps per stage, on real *fitting* windows, to prove the wiring. The 84 test cases stay locked.

## 1. Case-balanced classification weighting (S2)

For every eligible fitting fault window `i` of case `c` with class `k`:

```
w_i = class_weight[k] / n_c        class_weight[k] = N / (K * n_k) = 88 / (5 * n_k),  n_k = fitting CASES of class k
```

- Eligible = fitting `event_associated` windows with a real label; the one ambiguous conflicting-label window (start index 2550, cases 78/79) is excluded: **523 windows from 88 cases**, 5 or 6 windows per case.
- Counts `[33, 29, 9, 13, 4]` and weights `[0.533333, 0.606897, 1.955556, 1.353846, 4.4]` are computed in code (float64) from the window table and checked against the manifest.
- The windows of one case sum to that case's class weight; all windows sum to 88 = the number of cases (a test per fitting case).
- The cross-entropy is computed per window with `reduction="none"` and **no `weight=` argument**, so the class weight is applied exactly once.

**Normalisation and minibatches.** Weights are rescaled to mean 1 over the training windows, `w~_i = w_i * 523 / 88`. A minibatch loss is `mean_i(w~_i * ce_i)` with a **fixed denominator (the batch size)**. A full pass over all windows (including a short last batch) reproduces the epoch objective `(1/523) * sum_i w~_i ce_i` exactly, and the loss has the scale of an ordinary mean cross-entropy. A batch's scale does not depend on which classes it holds, but a batch rich in rare-class windows gives a larger gradient, which is what the class weights ask for. The alternative (divide by the batch's own weight sum) was not used because it makes the step size depend on the class mix.

This matches the XGBoost control in effect: XGBoost has one row per case with weight `N/(K n_k)`, so a case counts once and each class carries equal total weight.

## 2. Training configuration (`training_config_v1.json`, hash recorded in every checkpoint)

| | S1 (normal-reference next-step masked MSE) | S2 (fault fine-tuning, case-balanced CE) |
|---|---|---|
| Data | fitting `normal_reference`, 1,312 windows | fitting `event_associated`, 523 windows |
| Optimizer | AdamW, weight decay 0.01 (all parameters) | AdamW, weight decay 0.01, fresh state |
| Learning rate | 1e-3, cosine decay per epoch (design) | 1e-4, constant (design gives no S2 schedule: **proposed**) |
| Batch / clip | 64 / global grad-norm 1.0 | 64 / 1.0 |
| Max epochs | 100 (**proposed, not in the design**) | 100 (**proposed**) |
| Patience | 10 (design) | 10 (design; **monitored metric undefined**, see section 6) |
| Init | `Model1.build(seed)` | the S1 checkpoint of the same seed, all weights trainable |

Seeds are exactly 0–4 (`validate_seed` rejects anything else); the seed fixes model initialisation, loader shuffling and the dropout stream. `enable_determinism()` (deterministic kernels, one CPU thread) is called when a model is built. `select_device("auto"|"cpu"|"cuda")`: CUDA only if available; MPS is deliberately not offered (no determinism guarantee). CUDA was not available here and is untested. No hyper-parameter was tuned.

**Guards.** `check_batch` refuses any batch that is not entirely `fit` windows of the stage's own category, before the forward pass. `training_loader` only accepts `training_dataset` objects, which exist only for the two fit-only objectives. Non-finite loss, non-finite gradient norm (both checked **before** `optimizer.step`), non-finite parameters at epoch end, an empty epoch and unknown cases in the weight table all raise. Logs (`train_epochs` history) hold loss, lr, gradient norm mean/max, clipped batches and counts, and no wall-clock values, so they are reproducible.

## 3. Checkpoints (`checkpoint.py`, git-ignored `*.pt`)

`<name>.pt` (weights as plain tensors plus metadata, loaded with `weights_only=True`) and `<name>.json` (provenance, state digest, SHA-256 of the `.pt`). Provenance: split-manifest content hash, fit-only scaler hash, feature-cache hash, preprocessing-config hash, adapter-spec fingerprint, training-config hash, git HEAD, library versions, stage, seed, epoch, history. Loading verifies the file hash, that the JSON equals the metadata inside the file, stage/seed/provenance expectations, the architecture, a strict state-dict load, and the recomputed state digest (so tampered weights with a repaired file hash are still caught). Checkpoints are never committed.

## 4. Case-level validation interface (`case_eval.py`)

For the 25 validation cases: the approved non-ambiguous `event_associated` windows (150 = 6 per case, equal to the manifest list) -> softmax probabilities per window -> **mean once per case** -> argmax (tie to the lowest class id). Output rows are sorted by case id; probability columns keep the class order 0 Container Hardware, 1 Container Network, 2 Node CPU, 3 Node Disk, 4 Node Memory. `xgb_style_rows` emits the XGBoost per-case prediction layout so one metrics implementation scores both models.

`check_alignment` demands **exact** equality with the frozen XGBoost provenance (`observation_timing.json`, `case_features_provenance.json`): same 25 cases (array hash), same labels (hash) and class distribution `[10, 6, 3, 5, 1]`, same class order, 6 windows per case, and for every case the same first sample, last sample and number of distinct one-minute samples (12), consecutive at 60 s, and the same documented case time. On the real table this holds (`minute_union_sha256` is printed by the test). Only the `validation` role can be scored; any other role raises `RoleLocked`.

This milestone ran the alignment on window **metadata** only. No model was run on real validation windows.

## 5. What was verified

See the test files `test_m1_training_weights.py`, `test_m1_training_loop.py`, `test_m1_case_validation.py` (counts are in the milestone report): weighting identities per fitting case, AdamW first-step formula, clipping, determinism, failure stops, early-stopper logic, schedules, checkpoint tampering, real two-stage wiring on fit windows with bit-reproducible runs, aggregation, alignment mutations (shifted/dropped/extra windows, wrong labels, wrong order), and locked roles.

## 6. Decisions needed before the five-seed experiment

1. **Amendment A-1 (needs written approval).** Design 4.3 says class weights are inverse case counts "because windows per case are nearly equal". The case-balanced rule above (also dividing by the case's eligible window count) is a refinement of that frozen decision; per design 7.4 it needs a written amendment.
2. **Maximum epochs** for S1 and S2 (not in the design; 100 is a placeholder) and the **S2 learning-rate schedule**.
3. **S2 early-stopping metric** (design 6 says "S1/S2 validation metric"; E-4 is open). Candidates: validation case-level macro-F1 (noisy: 25 cases, Node Memory n = 1) or a validation loss on the 150 windows. The `EarlyStopper` is generic; the callback is not wired for S2 on purpose.
4. **S1 early stopping** uses validation `normal_reference` masked MSE (non-gradient, allowed by the design); `evaluate_masked_mse` exists and is tested on synthetic data only.
5. Weight decay is applied to every parameter (AdamW default), including biases and LayerNorm; excluding them is a possible later ablation.
