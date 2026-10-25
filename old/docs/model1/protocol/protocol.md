# Model 1 preprocessing, split, and evaluation protocol

M1 = multivariate LSTM encoder-decoder autoencoder on BARO Online Boutique telemetry
(BARO's `data/fse-ob`). This phase only **defines and validates the protocol** — no
training, no test-set model evaluation. Builds directly on the dataset-inspection
findings at `docs/model1/dataset-inspection/findings.md` (and its generated outputs
under `data/model1/dataset_inspection/`).

All scripts accept `--data-dir <BARO_DATA_DIR>` (path to BARO's `data/fse-ob`
directory) and use any Python environment with pandas/numpy installed. Nothing
under the BARO clone was read-write touched; no data was modified or re-downloaded.

**Changelog (revisions after initial protocol):**
1. Split assignment changed from a fixed run-4/run-5 val/test rule to a deterministic
   seeded per-combo permutation (§2). Manifests and the scaler were regenerated.
2. Investigated the BARO paper, supplementary material, and artifact source/config for
   evidence of injected-fault duration (§6, full writeup in
   `fault_duration_investigation.md`). No such evidence exists; labeling terminology
   revised accordingly — `t >= inject_time` is now the "post-injection evaluation
   region," not a guaranteed anomaly label.
3. Independently unit-tested `scripts/metrics.py` against 3 hand-computed cases before
   closing the issue (§11). Added `first_detection_time()` to `metrics.py`, which had
   been missing — the protocol's `detection_event_rule` was previously only prose, with
   no corresponding code.
4. Formally documented the fault-duration limitation before training (§8) and added a
   required fault-type-stratified evaluation policy (§9), with a corresponding 5th
   automated check.
5. Migrated from local-only files into this shared repo; all scripts were made
   path-configurable (`--data-dir`, `--configs-dir`, `--manifests-dir`, etc.) instead
   of hardcoding a local checkout's directory structure. No locked protocol semantics
   changed during migration.

```bash
cd scripts/model1/protocol
python3 build_manifests.py --data-dir <BARO_DATA_DIR> --inspection-dir ../../../data/model1/dataset_inspection
python3 fit_scaler.py --data-dir <BARO_DATA_DIR>
python3 metrics.py               # formula sanity check only (synthetic data)
python3 validate_protocol.py --data-dir <BARO_DATA_DIR>
cd ../../../tests/model1
python3 test_metrics.py          # hand-computed unit tests
```

## 1. Fixed 55-feature list

`configs/model1/features.json`. Sourced from `data/model1/dataset_inspection/column_presence.csv`
(`present_in_all == True`, excluding `time`) — the 55 telemetry columns present in
literally all 100 cases. Excludes 7 non-universal columns (6 istio error counters +
`istio-init_mem`) that are absent from some cases' CSV headers (see inspection
findings.md B.1/A.12). `time` and row index are explicitly excluded as model inputs.

## 2. Deterministic train/val/test manifests

`data/model1/manifests/train_cases.json` (60), `data/model1/manifests/val_cases.json` (20),
`data/model1/manifests/test_cases.json` (20), plus `data/model1/manifests/manifest_summary.csv` for a
human-readable per-case view. **Revised rule**: for each of the 20
`(service, fault_type)` combos, `{1,2,3,4,5}` is shuffled with
`random.Random(f"{split_seed}-{combo}")` (a deterministic, per-combo seed derived from
the single global seed in `configs/model1/split_seed.json`, currently `298`); the first 3
shuffled run_ids → train, next 1 → val, last 1 → test. This replaces the earlier fixed
rule (run 4 always val, run 5 always test for every combo), which risked confounding
the split with any run-order/warm-up effect. Verified programmatically in
`build_manifests.py` and confirmed by inspection that val/test now draw from all of
run_ids 1–5, not just 4/5 (e.g. val includes `cartservice_cpu/5`,
`checkoutservice_delay/3`, etc.). Every combo still has exactly 3/1/1.
`configs/model1/split_seed.json` records the seed and the exact permutation used per combo
for audit and re-derivation.

## 3. No case leakage across splits

`validate_protocol.py` → `split_overlap` check: train/val/test case-id sets are
pairwise disjoint, no duplicates within any manifest, and their union is exactly the
100 cases. **PASS** (see `docs/model1/protocol/validation_report.json`).

## 4. Normalization (training data only)

Per-feature z-score, fit on **pre-fault rows of train-split cases only**
(`fit_scaler.py`; 60 cases × 360 pre-fault rows = 21,600 rows). Saved to
`configs/model1/scaler.json` (per-feature mean/std, near-zero-std features flagged — none
found). Applied to all splits using the frozen train-fit stats; val/test never
influence the scaler. Verified in `validate_protocol.py` → `scaler_train_only`: the
saved scaler is independently recomputed from the train manifest and matches exactly,
plus a negative control confirms the fit routine is actually sensitive to which cases
are included (adding one val case's rows measurably shifts the mean). **PASS**.

## 5. Initial windowing protocol (not tuned on val/test)

`configs/model1/protocol_config.json` → `windowing`. Window length 30s (30 steps at 1 Hz),
train-window stride 5s, eval-window stride 1s. Training windows are drawn only from
the pre-fault segment of train-split cases; evaluation windows span the full case
(pre + post-fault) for val (threshold selection) and test (final protocol validation,
not run in this phase). Explicitly flagged as an initial choice from dataset structure
alone, not empirically tuned — see open decisions below.

## 6. Post-injection evaluation region (revised labeling terminology)

Investigated whether the BARO paper, its supplementary material, the artifact source
code, or any fault-injection configuration establish that the injected fault (CPU/mem
via `stress-ng`, delay/loss via `tc`) stays physically active for the entire
post-injection segment through end-of-case. Full writeup: `fault_duration_investigation.md`.

**Finding: no such evidence exists.** The paper (Section 4.2.1) says metrics "during a
fault injection period" are abnormal but never defines when that period ends; Section
3.4.1's mathematical definition of the "anomalous period" (`t̂_A` to `t_0+T`) uses
end-of-collection as its boundary by notational construction, not as a measured
fault-end time. No `stress-ng`/`tc` duration flags, injection scripts, or config files
are included anywhere in the repo or the downloaded dataset. `tc`-based faults
(delay/loss) plausibly persist throughout (tc rules don't self-expire, and the system
is only restarted after collection ends per the paper) — but `stress-ng`-based faults
(CPU/mem) commonly use an explicit timeout and could self-terminate early, which cannot
be confirmed or ruled out here.

**Consequence — terminology revised** in `configs/model1/protocol_config.json` →
`labeling.terminology_revision`: `t >= inject_time` is now called the **"post-injection
evaluation region,"** not a guaranteed anomaly label. `t < inject_time` remains the
"pre-fault / known-normal region" (well-supported — it strictly precedes injection). Rules:
- Row/window region: `time >= inject_time` → post-injection evaluation region (per
  BARO's own convention; treated as anomalous for scoring purposes, with the caveat above).
- Window prediction: anomalous iff reconstruction error exceeds a threshold selected
  on the **val** split only.
- Detection time per case: timestamp of the first post-injection-region window
  predicted anomalous; cases with no detection are misses, reported separately (not
  dropped).

Any F1/precision/recall/detection-delay numbers computed downstream inherit this
caveat and should be reported alongside it, especially for CPU/mem fault types. See §8
for the formal, binding statement of this limitation and §9 for the required mitigation.

## 7. Metric formulas

`scripts/metrics.py` — pure functions, exercised only against synthetic arrays to
prove correctness (no real model output involved), and independently unit-tested with
hand-computed cases in §11:
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2·P·R / (P + R)
- Detection delay (per case) = time from `inject_time` to the first post-injection
  detection, seconds — a purely operational definition (§8); summarized as the
  **median** across cases with a detection
- Pre-fault FPR = (# windows with `time < inject_time` predicted anomalous) /
  (# all windows with `time < inject_time`) — computed **only** over the known-normal
  region (§8)

Success targets (locked): F1 ≥ 0.82, median detection delay ≤ 10s, pre-fault FPR ≤ 5%.

## 8. Documented fault-duration limitation (before training)

**The artifact provides `inject_time` but no verified fault-end time.** No evidence of
fault duration or fault removal was found in the BARO paper, its supplementary
material, or the artifact source/config (§6, full investigation in
`fault_duration_investigation.md`). Recorded here as a formal, binding limitation
*before* any training happens, per `configs/model1/protocol_config.json` → `limitations.fault_duration`:

1. **`t < inject_time` is the known-normal region** — the only region with a verified
   ground-truth label (it strictly precedes fault injection) — **and is therefore the
   only region used to compute pre-fault FPR.**
2. **Detection delay is defined operationally**: time from `inject_time` to the first
   detection in the post-injection evaluation region. This does not assume the fault
   was still physically active at the moment of detection.
3. **`t >= inject_time` is the "post-injection evaluation region,"** following the
   dataset/paper convention, but is **not claimed to represent verified active-fault
   ground truth at every timestamp** in that region.
4. **DELAY and LOSS must not be described as "confirmed persistent"** — their plausible
   persistence (tc rules don't self-expire) is an inference from typical `tc` behavior,
   not direct artifact evidence. This document and `fault_duration_investigation.md`
   have been checked to avoid that phrasing; any future report on this dataset should
   maintain the same restraint.

## 9. Stratified evaluation requirement (mitigation for §8)

Per `configs/model1/protocol_config.json` → `metrics.stratified_evaluation`: **all evaluation
metrics (precision, recall, F1, pre-fault FPR, detection delay) must be reported
separately for each of the 4 fault types — CPU, MEM, DELAY, LOSS — in addition to the
pooled numbers.** This is the required mitigation for §8: CPU/MEM (stress-ng, possible
early self-termination) and DELAY/LOSS (tc, plausibly persistent) may behave
differently in the post-injection evaluation region, and pooling across all 4 would
hide that difference. Stratified reporting lets fault-duration-related behavior (e.g.
detection delay or F1 degrading specifically for CPU/MEM in a pattern consistent with
an early-ending fault) actually be seen instead of averaged away.

Implemented as `fault_type_of_case()` / `group_case_ids_by_fault_type()` in
`scripts/metrics.py`, and validated for real by `validate_protocol.py`'s
`fault_type_stratification` check: all 100 real case ids parse to exactly one of
`{cpu, mem, delay, loss}`, 25 cases each (5 services × 5 runs). **PASS.**

## 10. Automated checks

All five implemented in `scripts/validate_protocol.py`, output in
`docs/model1/protocol/validation_report.json`:

| Check | Result |
|---|---|
| Split overlap (disjoint, no dupes, covers all 100 cases) | **PASS** |
| Feature consistency (all 55 features present & numeric in all 100 cases' `simple_data.csv`) | **PASS** |
| Training-only scaler fit (recomputed from train manifest matches saved scaler; negative control confirms sensitivity to case membership) | **PASS** |
| No time/index feature leakage (`time`/`index`-like names absent from feature list; labeling spec scopes `time` to labels only) | **PASS** |
| Fault-type stratification (all 100 real case ids parse to cpu/mem/delay/loss, 25 each) | **PASS** |

```
ALL CHECKS PASSED: True
```

## 11. Independent validation of `scripts/metrics.py`

Before closing this issue, `metrics.py` was validated against `scripts/test_metrics.py`
— 3 small, hand-computable evaluation cases with expected TP/FP/TN/FN, Precision,
Recall, F1, pre-fault FPR, and detection delay worked out by hand in code comments and
hard-coded as literal constants (never generated by calling `metrics.py` itself):

1. **Perfect detection** — all pre-fault windows correctly predicted normal, all
   post-injection windows correctly predicted anomalous. Hand-computed: TP=3, FP=0,
   FN=0, TN=5, P=R=F1=1.0, pre-fault FPR=0.0, detection delay=0.
2. **False positives + missed anomalies** — 2 pre-fault false positives, 1 true
   positive and 3 false negatives post-injection. Hand-computed: TP=1, FP=2, FN=3,
   TN=3, P=1/3, R=0.25, F1=2/7, pre-fault FPR=0.4, detection delay=2.
3. **No post-injection detection (total miss)** — every post-injection window
   predicted normal. Hand-computed: TP=0, FP=1, FN=5, TN=4, P=R=F1=0.0, pre-fault
   FPR=0.2, and `first_detection_time()` must return `None` (verified) rather than a
   fabricated delay; the case is then confirmed excluded from a 3-case median
   detection-delay rollup (hand-computed `median([0, 2]) = 1.0`, miss correctly
   dropped rather than counted as 0 or silently omitted from precision/recall).

`first_detection_time()` was added to `metrics.py` to make the previously-prose-only
`detection_event_rule` testable code. `fault_type_of_case()` /
`group_case_ids_by_fault_type()` (§9) also carry their own synthetic checks in
`metrics.py`'s `__main__` block.

**Result: ALL TESTS PASSED** (`python3 test_metrics.py`, exit code 0) — all three cases
plus the rollup check matched hand-computed expectations exactly.

## 12. Artifacts

```
configs/model1/
  features.json           # 55 features + exclusions
  protocol_config.json    # windowing, normalization, labeling, limitations,
                           #   stratified-evaluation policy, metric formulas, targets
  scaler.json             # per-feature mean/std fit on train pre-fault rows (seeded split)
  split_seed.json         # split seed + exact per-combo permutation used
data/model1/manifests/
  train_cases.json / val_cases.json / test_cases.json
  manifest_summary.csv
scripts/model1/protocol/
  build_manifests.py
  fit_scaler.py
  metrics.py               # formulas + fault_type_of_case/group_case_ids_by_fault_type
  validate_protocol.py     # 5 automated checks
tests/model1/
  test_metrics.py          # independent hand-computed unit tests for metrics.py
docs/model1/protocol/
  validation_report.json
  fault_duration_investigation.md  # fault-duration evidence investigation + formal limitation
  protocol.md                       # this file
```

(This tree reflects the shared-repo locations after migration. The `paper_extracts/`
directory used locally during the fault-duration investigation was intentionally not
migrated — it reproduces large portions of a copyrighted published paper; see
`fault_duration_investigation.md` for citations instead.)

## 13. Decisions needing human approval

1. **Window length (30s) and strides (train=5s, eval=1s)** are a reasonable starting
   point derived only from dataset structure (1 Hz, 720s/case, fault at midpoint), not
   empirically justified. Fine to proceed with for a first LSTM training run, but
   should be explicitly signed off — and if revisited, must be tuned on **val only**,
   never test.
2. **Window prediction threshold selection method** is specified only at the level of
   "a percentile of val normal-window reconstruction errors" — the exact percentile
   (e.g. 95th vs 99th) is not fixed yet and should be chosen once real val
   reconstruction-error distributions exist (still before touching test).
3. **Treatment of the 7 excluded columns** — dropped entirely for M1 per this
   protocol. Confirm the team is fine losing istio error-rate signal for M1's first
   iteration (could matter more for a later root-cause-localization model, M2).
4. **RESOLVED**: "post-injection evaluation region" labeling is now formally documented
   as a limitation (§8) with a required stratified-evaluation mitigation (§9), not an
   artifact-confirmed fault duration. Team should confirm this is acceptable to proceed
   with, or, if anyone has independent knowledge of the actual `stress-ng`/`tc`
   parameters used (e.g. from unpublished experiment scripts), surface it now — it
   would let us tighten the label instead of using the whole post-injection segment.
5. **RESOLVED**: run split is now a seeded per-combo permutation
   (`configs/model1/split_seed.json`, seed `298`) instead of a fixed run-4/run-5 rule. Team
   should confirm the seed value itself doesn't need to match some other
   already-published or team-standard seed.

Stopping here per instructions: no LSTM training, no threshold selection against real
val output, no test-set inspection.
