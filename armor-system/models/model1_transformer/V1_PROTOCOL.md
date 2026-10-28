# Model 1 v1: design audit and recorded protocol (Linear 298-51)

**Status: recorded before any v1 training. Nothing in v1 has been implemented or run.** The project lead's v1 configuration (section 1) is recorded as approved. Implementation details marked **[S]** were specified by this audit and need the lead's confirmation before training starts. **Blocker B1 (section 9; evidence in section 8) prevents freezing the primary threshold rule**; until it is decided the primary detector below is *provisional*.

## 0. Predeclaration (unchanged from the v0 protocol)

> Model 1 v0 uses no simulated-missing training and is reported as the ablation. Model 1 v1 uses simulated-missing training and is the predeclared final model for held-out test evaluation, regardless of validation performance.

v0 (five Stage 1 checkpoints, forecast-error detection, results in `results/detection_v0/`) is preserved unchanged.

## 1. Design authority: what is approved and what is new

Source: `MODEL1_V0_DESIGN.md` (approved, merged), sections 3, 4, 7 and the frozen list F1-F11 in section 10. A search of that note finds **no** binary detection head, no supervised detection objective, no SPOT/EVT thresholding and no rolling maximum.

| Element | Approved original design | v1 status |
|---|---|---|
| Encoder, next-step head, fault head (d 64, 2 layers, 4 heads) | F7 "initial default", two heads | **Unchanged** (168,200 parameters: encoder 151,169, fault head 8,581, next-step head 8,450) |
| Binary detection head | **Not specified** (F7: "two heads"; F9: detection = next-step error) | **Explicit v1 extension** (amendment A-2): +8,321 parameters = 176,521 |
| Supervised detection labels | F3 defines the three window categories only for training/validation use; S1 "never sees `event_associated`" | **New use** of F3 categories as weak detection labels (A-2) |
| Detection signal | F9: M1/M2/M3 forecast error, M2 primary | v1 primary = supervised score; forecast-error detection kept as a **diagnostic** (A-2) |
| Threshold | F9: 99th percentile on calibration windows | v1 = SPOT/EVT (**extension A-3; provisional, see B1**) |
| Trailing rolling maximum | not in design | **Extension A-3** |
| Simulated missing | 4.4 optional switch [D]: probability 0.1, off for v0, "one ablation on validation only" | v1: **0.2**, both stages, and v1 is the final model (**extension A-4** of a [D] default) |
| Case-balanced fault weights, five-class head, case-level aggregation | F8 + amendment A-1 (TRAINING.md section 7) | unchanged |
| Split, scaler, masks, calibration region, ARMOR interval/scoring rules, 25 validation incidents, +/-300 s proxy | F1, F2, F5, F9, F10, F11 | **Unchanged** |
| Seeds, optimizer, learning rates, epochs, clipping | TRAINING.md section 7 | unchanged (v0 values) |

Per design 7.4 item 5, A-2 to A-4 are written amendments; this document is that record.

## 2. Architecture

Existing model unchanged. Detection head [S]: input = the fault head's pooled last-minute features (mean and max over valid nodes, 128 values) -> `Linear(128, 64)` -> GELU -> `Linear(64, 1)`, one **logit per window**, no node identity. Added parameters: 8,256 + 65 = **8,321**; total **176,521**.

## 3. Training and loss policy (no calibration, validation or test example in any weight update)

Optimizer settings are v0's (AdamW, weight decay 0.01, clip 1.0, batch 64; Stage 1 lr 1e-3 cosine, Stage 2 lr 1e-4 constant, 100 epochs, patience 10, seeds 0-4). Only fitting windows are batched (`check_batch` roles/categories enforced).

- **Stage 1** [S]: unchanged objective: next-step masked MSE on fitting `normal_reference` windows only, with simulated-missing inputs (section 4). No detection loss in Stage 1 because Stage 1 contains no event windows (F3). The detection head is not trained here. Validation early stopping uses clean (not masked) validation `normal_reference` MSE, as in v0.
- **Stage 2** [S]: initialised from that seed's selected v1 Stage 1 checkpoint, fresh AdamW. Each optimizer step uses a **paired batch**: 64 windows from the 523 eligible fitting event windows (shuffled; the ambiguous conflicting-label window is excluded as in v0) plus 64 fitting `normal_reference` windows (shuffled, cycling through the 1,312). An epoch is one pass over the event windows. `ignore` windows are never used.
  - `L = L_fault + L_det`, both weight 1 (fixed, no search).
  - `L_fault`: case-balanced class-weighted cross-entropy (v0 weighting) on the 64 event windows.
  - `L_det`: binary cross-entropy with logits over the 128 windows, label 1 for event windows and 0 for normal windows; the 1:1 pairing balances the classes, so no class weight is applied.
  - The next-step head is not trained in Stage 2 (as in v0). Both heads backpropagate into the shared encoder.
- **Checkpoint selection** [S] (validation, no gradient, clean inputs, never a detection F1, threshold or interval metric): lowest `case-level fault NLL (25 cases, v0 definition) + balanced window BCE`, the latter the mean of the per-class mean BCE over the 150 validation event windows and the 411 validation normal windows. Patience 10.
- **What the labels mean:** `event_associated` is the documented-fault window under policy B (pre 120 s, post 300 s), a weak proxy; `normal_reference` is far from every case. The head therefore learns the *geometry of documented injections*. **v1 detection is a supervised detector, not label-free like ARMOR's AD**, so a comparison with ARMOR's unsupervised AD must say so.

## 4. Simulated-missing policy (training only, both stages)

- **Rate and unit** [S]: each applicable and available (node, modality) block is hidden with probability **0.20**, independently per window, input minute, node and modality. A hidden block sets `observed_entry` False for all of that modality's channels of that node at that minute; `effective = applicable & observed`, and the existing adapter path replaces the values by 0 with `torch.where` and receives the mask. Targets are never hidden.
- **Three states stay distinguishable:** *natural absence* (`applicable` False, layers 1-2) is never droppable and never counted; a *true zero* (`applicable` True, `observed` True, value 0) is data; an *artificially hidden* block (`applicable` True, `observed` False) is logged in a separate boolean `artificial_missing` that the model never receives (the model sees only the effective mask), so tests and logs can tell hidden blocks from real ones.
- **Determinism** [S]: the Bernoulli draws come from a counter-based generator (`numpy` Philox) keyed by (seed, stage, epoch, window start index), independent of batch order and size, with its own stream (it does not consume the shuffle or dropout RNG).
- Never applied to calibration, validation or test scoring unless a missing-data experiment says so (section 7); training-time masks are never reused as evaluation masks.

## 5. Detection pipeline (v1)

1. **Score**: `s_t` = detection logit of the window whose target minute is `t` (inputs end at `t - 60 s`).
2. **Trailing rolling maximum** [S]: `s'_t = max(s_t, s_{t-60 s})`, using the previous window only if it exists, is exactly 60 s earlier and belongs to the same role and period; otherwise `s'_t = s_t` (partial window). The output is stamped `t`, the target minute of the later window, and uses nothing later than `t`: it is causal. The same transform is applied to the calibration scores before thresholds are fitted. Consequence, intended and to be reported: one isolated exceeding minute becomes a two-minute alert, so ARMOR's singleton rule no longer drops it. The interval start is unchanged, so detection delay is not shifted.
3. **Threshold**: ARMOR's SPOT initialisation on the rolled calibration `normal_reference` scores (no validation or test labels), with ARMOR's D1 parameters `q = 0.1`, `level = 0.95` and ARMOR's fallback (percentile at `level` on any exception). Deviation [S]: ARMOR's "threshold <= 0 is invalid" rule is dropped because logits are legitimately negative. **Provisional: B1.**
4. **Alerts and scoring**: `s' > threshold`; the ARMOR-equivalent `get_pre_interval` (delay 600 s, singleton drop) and `eval_AD` (+/-300 s proxy) against the **25 documented validation incident timestamps**; the same diagnostics as v0 (precision, recall, F1, detection delay, false-positive intervals, normal-reference false-alarm rate over the 411 windows, ignore-region classes, coverage, no-score handling). Five seeds, mean +/- sample SD. No official ARMOR label or interval file, no test data.

## 6. Primary and diagnostic configurations

- **Primary (provisional until B1):** supervised logit -> rolling maximum -> SPOT(q 0.1, level 0.95) on calibration -> ARMOR intervals -> 25 validation incidents. Fixed before training; never chosen from validation; the same configuration is the test configuration.
- **Diagnostics, not alternatives (reported, never selected from):**
  - D1: same supervised rolled score with the **99th-percentile threshold** on calibration (and 95/97/99.5), isolating the thresholding effect.
  - D2: supervised score **without** the rolling maximum, SPOT threshold, isolating the rolling maximum.
  - D3: v1 **Stage 1** checkpoint, forecast-error M2 at the 99th percentile (the v0 protocol), isolating the effect of simulated-missing training against v0.
  - D4: v0 as already reported.
- Five simultaneous changes separate v1 from v0 (head, supervision, SPOT, rolling maximum, simulated missing); D1-D3 are the minimum needed to attribute differences.

## 7. Missing-data validation plan (validation only, not executed)

**ARMOR's six scenarios.** `main.py::build_missing_cases(include_all_missing=False)` takes every non-empty proper subset of the three modalities {log, metric, trace}: drop {log}, {metric}, {trace}, {log, metric}, {log, trace}, {metric, trace}, plus the full baseline. `get_channel_indices_to_mask` zeroes **all channels of the modality for all nodes and the whole evaluation period**; ARMOR's `metric` includes the 57 VM metrics (spans 0-52 and 73-129). `SLD` also zeroes those channels' error terms, and ARMOR recomputes its initialisation statistics and threshold on the same masked data. Reproduction on our schema: `observed_entry` False for every channel in `modality_index_ranges[modality]` (metric 110, trace 9, log 11), for every node and minute, input and target (target mask follows design rule 3). Dropping `metric` hides the VMs entirely (their missing vector is used); dropping `trace` or `log` affects pods only. Primary: **recalibrate on the same masked calibration windows** (ARMOR-faithful); secondary: clean thresholds applied to masked validation (deployment without warning). Models: v0 (forecast error), v1 primary and D3. Five seeds.

**Random missingness.** Rates **0, 10, 20, 30, 40%** with **10 deterministic masks per rate**. A mask is a Bernoulli draw over (sample minute, node, applicable modality) of the whole sample timeline (Philox keyed by rate index and mask index), so a hidden sample is hidden in every window that uses it, and the target mask follows. Masks depend only on (rate, mask index): identical for every model and seed (paired). At 0% all ten masks are identical (one distinct mask, reported once). Calibration is redone per mask on the masked calibration windows, then the validation protocol of section 5 is run; report per rate the mean +/- SD over masks (and seeds) of F1, recall, precision, false-positive intervals and alert coverage, relative to 0%. Not executed; no test data.

Caveat: v1 trains with per-block random drops, so ARMOR's whole-modality scenarios are out of distribution for it; the random-rate experiment matches its training distribution at 20%.

## 8. SPOT feasibility audit (measured, analysis only)

ARMOR's original `SPOT` and `get_threshold` were run unchanged on the v0 forecast-error M2 scores of the **329 calibration windows** (five seeds; `v1_audit_spot.py`, `results/v1_audit/`). The v1 supervised scores do not exist yet; these are the best available proxy.

- ARMOR uses only the initialisation step: threshold `t` = ascending order statistic `S[int(level * n)]`, peaks = scores above `t` minus `t`, a Grimshaw GPD maximum-likelihood fit, extreme quantile `t + (sigma / gamma) * ((n q / Nt)^(-gamma) - 1)`; no streaming; fallback `sorted(scores)[int(n * level)]` on any exception.
- With `level = 0.95`, `q = 0.1`: `n q / Nt` is about 2 for any `n`, so the "extreme quantile" lies **below** `t`, near the 90th percentile. ARMOR fits on about 2,270 in-sample training minutes (about 113 peaks); here `Nt = 16`.
- **Dependence:** adjacent windows share 6 of 7 minutes; lag-1 autocorrelation 0.23-0.29, effective sample size **128-170 of 329**, so the 16 peaks carry about 7 independent ones.
- **The fit degenerates:** the GPD shape is estimated as exactly **gamma = 0** (an exponential tail) on the real scores of all five seeds and in all 2,500 block-bootstrap resamples. The threshold is then `t - sigma ln(r)`: **12.5-18.9, against empirical 90th percentiles of 35.9-42.6**; **21-32% of the normal calibration windows exceed it** (nominal 10%).
- **Unstable:** 7-window block bootstrap, threshold IQR/median 0.67-1.15 (plain bootstrap 1.0-2.9); 2.5% quantiles of the resampled thresholds are **negative** in every seed (ARMOR's invalid rule would fire).
- No fit raised an exception; the fallback was never needed.

## 9. Blockers, risks and decisions needed before training

- **B1 (blocks freezing the primary threshold):** on 329 windows ARMOR-style SPOT is not a tail estimator: 16 correlated peaks, exponential degeneration, extrapolation below the peaks cut, thresholds far below the 90th percentile and unstable, and a likely 20-30% normal-window alert rate. Options, to be chosen **before training and never from validation results**: (a) keep SPOT exactly as proposed and report its alert coverage honestly; (b) **recommended**: take the ARMOR-equivalent operating point as the empirical 90th percentile of the rolled calibration scores (ARMOR's q = 0.1 meaning), with the block-bootstrap interval reported, and SPOT as diagnostic D1'; (c) fit SPOT on the 1,312 fitting `normal_reference` windows as ARMOR does (about 66 peaks), accepting that in-sample supervised logits are optimistic and the threshold too low for held-out windows. The v1 supervised score distribution is unknown until trained, so even (a) cannot be checked in advance.
- **R1** Supervised vs label-free detection: v1 uses fitting-region incident labels and cannot be compared one-to-one with ARMOR's unsupervised AD.
- **R2** The rolling maximum bypasses the singleton rule and changes what an alert is; five changes versus v0 are confounded (D1-D3 mitigate).
- **R3** Stage 2 paired batches and the selection metric are specified here [S]; the held-out label geometry (policy B) is learned by the head.
- **R4** Validation (25 incidents, one Node Memory case) also selects the checkpoint; calibration (329 overlapping windows) is the only source of thresholds; calibration-region drift is unmeasured.
- **R5** `check_batch` and `training_loader` currently accept one category per batch; paired batches need a small, tested extension.
- **R6** ARMOR missing-data scenarios are out of distribution for v1; random-rate experiments match training.
- **R7** The unexplained `ad_cases.pkl` events cannot be separated from false positives without opening the official labels (test period).

## 10. Guardrails

No hyper-parameter search; no validation-driven choice of the primary detector, threshold, rolling window or rate; v0 checkpoints and results untouched; no calibration, validation or test example in any weight update; no test data until both models are frozen; no training before items marked [S] and B1 are confirmed.
