# Model 1 dataset inspection — BARO Online Boutique artifact

Dataset inspected: `<BARO_DATA_DIR>` (BARO's `data/fse-ob`, 477 MB, downloaded from
Zenodo record 11046533 during BARO baseline reproduction on 2026-09-18). Read-only
throughout — nothing under the BARO clone was modified, no data was re-downloaded, no
imputation/deletion/normalization was performed. BARO baseline reproduction itself
was not touched.

Scripts (run with any Python environment that has pandas/numpy installed, e.g. the
`fse-baro` project's own env from a local BARO clone):
- `inspect_dataset.py` — structure, timestamps, sampling, duplicates, basic constant/
  missing checks, per-case and per-metric rollups.
- `inspect_schema_and_missingness.py` — schema union/intersection, per-column presence
  by service/fault type, constant-column breakdown, missing-cell breakdown with
  pre/post-fault split.

Raw outputs: `case_summary.csv`, `column_stats.csv`, `dataset_summary.json`,
`column_presence.csv`, `constant_columns.csv`, `missing_cells_detail.csv`,
`schema_report.json`.

## A. Factual findings

**1. Directory/file structure.** `data/fse-ob/<service>_<fault_type>/<run_id>/`.
20 combo folders (5 target services × 4 fault types) × 5 run folders each = **100 case
folders**. Each case folder holds: `data.csv` (raw, 427 columns — untouched
Prometheus/istio scrape names, e.g. `cartservice_container-cpu-system-seconds-total`),
`simple_data.csv` (the file BARO's own `reproducibility.py` globs for — aggregated,
human-readable metric names), `inject_time.txt`, `plot.png`, `postprocess.log`, and
six `*.json` files that are saved outputs of BARO's own change-point/anomaly
algorithms (`birch.json`, `nsigma.json`, `spot.json`, `naive_bocpd.json`,
`robust_bocpd.json`, `univariate_bocpd.json`, `bocpd_time.json`) — **these are
baseline-algorithm results, not ground-truth labels.**

**2/3. Metrics and service ownership.** `simple_data.csv` columns follow
`<service>_<metric>`. Across all 100 cases: **union = 62 metric columns, intersection
(present in literally every case) = 55 metric columns**, spanning 13 distinct service
prefixes: adservice, cartservice, checkoutservice, currencyservice, emailservice,
frontend, frontend-external, main, paymentservice, productcatalogservice,
recommendationservice, redis, shippingservice. Metric types per service: `cpu`, `mem`,
`workload`, `latency-50`, `latency-90` (not every service has every type — `redis` and
`main` have only `cpu`/`mem`; `frontend-external` has only `workload`). *(Note: an
earlier memory entry said "49 metrics" for this dataset — the actual `simple_data.csv`
schema has 55–62 metric columns depending on case; 49 does not match anything measured
here and should be treated as superseded.)*

**Target/faulted services** (from folder names): cartservice, checkoutservice,
currencyservice, paymentservice, productcatalogservice — 5 services, matching the
locked baseline description in memory.

**4/5. Timestamp format and sampling.** `time` column is Unix epoch seconds, integer.
Every one of the 100 cases has exactly **721 rows spanning 720 seconds at a 1 Hz
sampling interval** (mode, min, and max diff are all 1.0s — no gaps, no irregular
sampling).

**6/7. Runs and fault labels.** 100 runs = 5 services × 4 fault types (`cpu`, `mem`,
`delay`, `loss`) × 5 repeated runs each. Labels are structural (from folder names), not
row-level: `inject_time.txt` gives a single Unix timestamp per case, no fault-end
timestamp exists anywhere in the artifact.

**8/9. Fault window and pre-fault period.** `inject_time` falls inside `[time.min(),
time.max()]` for all 100 cases, and — notably — at **exactly the midpoint (fraction
0.5) in every single case**: 360s of pre-fault data, 360s of post-fault data, always.
BARO's own code (`utility.py`, `reproducibility.py`) treats this as a hard binary
split: `time < inject_time` → normal, `time >= inject_time` → anomalous. There is no
recovery/fault-end marker, so "anomalous" effectively means "any time after
injection," not "time during the active fault."

**10. Missing values.** 2,630 missing cells total across the whole dataset (out of
~100 × 721 × ~57 ≈ 4.1M cells — negligible in aggregate, ~0.06%), but **highly
concentrated**: it is not spread evenly. Two columns account for the bulk:
`istio-init_mem` (1,137 missing, but this column only exists as a header in 2/100
cases — an istio sidecar init-container metric that's essentially noise) and
`cartservice_error`/`adservice_error`/`frontend_error` (large single-case gaps, e.g.
659 missing in one `cartservice_error` case). Most of the remaining missingness (7
other `*_cpu` columns, ≤11 cells each) is a handful of isolated NaNs in single cases,
consistent with occasional scrape misses, not a systemic collection problem. Split:
1,474 missing pre-fault vs. 1,156 post-fault — roughly even, **no evidence that
missingness itself leaks the fault window.**

**11. Duplicate rows.** Zero duplicate full rows and zero duplicate timestamps in any
of the 100 cases.

**12. Constant/near-constant metrics.** No column is constant in *every* case (good —
nothing is dead weight across the whole dataset). But **90/100 cases have at least one
constant column locally**, driven almost entirely by 7 columns, all `*_error` counters
(istio 5xx/error counts) plus `istio-init_mem`:
`adservice_error` (flat in 41/100 cases), `frontend_error` (flat in 80/100),
`frontend-external_error` (38/100), `productcatalogservice_error` (21/100),
`cartservice_error` (7/100), `checkoutservice_error` (6/100). These are Prometheus
counters that report a fixed value (usually 0) whenever no errors occurred during that
12-minute window — expected behavior for error counters, not a data bug. One
non-error column, `emailservice_mem`, is flat in 11/100 cases (email service simply
isn't touched by CPU/mem/delay/loss faults injected into other services in those
runs) — this is real signal (an unaffected service staying flat), not a defect.

**13. Scale/range differences.** Metrics span wildly different magnitudes by
construction: CPU/latency metrics are small floats (sub-second to low seconds), while
byte-count and counter-style metrics (had they been carried into `simple_data.csv`,
which they mostly aren't — see below) would be in the millions. Within the 55-column
intersection, `*_cpu` and `*_latency-*` are on comparable small-float scales,
`*_workload` (request counts) and `*_mem` differ by orders of magnitude from those and
from each other. **Per-metric scaling/standardization will be required before feeding
a multivariate model** — this dataset was not designed to be all one scale.

**14. Alignment across timestamps.** All 100 cases share the identical row count (721)
and identical time span (720s) at 1 Hz, so within a single case every metric column is
already row-aligned on a shared `time` index. Alignment is **not** guaranteed *across*
cases at the level of raw epoch value (each run starts at a different real-world Unix
time — `inject_time` alignment is what matters, not absolute epoch), which is fine as
long as models consume relative/elapsed time, not raw epoch seconds.

**15/16/17 (suitability, splitting, leakage)** — see sections C and D below.

## B. Unresolved questions

1. **7 sparse columns (`*_error` ×6, `istio-init_mem`) — keep, drop, or fill?** They
   are genuinely absent from the CSV header in the minority of cases (confirmed via
   `column_presence.csv`; not a same-name-different-representation issue) — i.e. this
   is a true schema inconsistency, not a labeling artifact. Not resolved here because
   resolving it means choosing a modeling policy (drop vs. zero-fill vs. per-case
   indicator), which is a Model 1 design decision, not an inspection fact.
2. **Why does `inject_time` sit at exactly the midpoint in literally 100/100 cases?**
   This looks like a fixed experimental protocol (start collection, wait 6 min, inject,
   wait 6 more min, stop) rather than organic timing. Not confirmed against the BARO
   paper's methodology section — worth checking Section III/IV of the paper text
   directly if precise experimental protocol matters for the report.
3. **No fault-end timestamp anywhere in the artifact.** Unclear whether the original
   experiment had a fixed fault *duration* (e.g. "inject for N minutes then stop") that
   simply wasn't persisted, or whether the fault was left active until the run ended.
   This matters for whether "post-fault" should really be treated as uniformly
   anomalous for the full 360s, or whether part of it is actually a fault that already
   ended (silent mislabeling risk) — could not be resolved from the artifact alone.
4. **The `*.json` algorithm-output files** (`nsigma.json`, `spot.json`, etc.) were not
   deeply parsed here beyond confirming they're baseline change-point outputs, not
   ground truth. Worth a follow-up pass only if the team wants to compare Model 1
   against these per-case detections directly (not needed for this phase).

## C. Dataset suitability verdict for multivariate anomaly detection

**Usable, with caveats.** The 55-column intersection gives a clean, aligned,
zero-duplicate, 1 Hz multivariate time series per case with a real (if simplistic)
before/after fault label — enough to support a **semi-supervised** framing (train
"normal" on pre-fault segments, detect deviation post-fault) which is exactly how
BARO's own pipeline uses it. It is weaker for **fully supervised** framing because the
only label signal is a single injection timestamp with no confirmed fault-end, so
"positive" windows may include a tail of already-resolved-fault time treated as still
anomalous. **Unsupervised** framing (no labels at all) is also supportable given the
pre/post structure, though most value comes from actually using the labels available.
Not suitable as-is for models expecting a uniform per-run feature schema without a
harmonization step first (see D).

## D. Recommended splitting strategy

- **Split by case (run), never by row.** Every window drawn from `cartservice_cpu/3`,
  for example, must land entirely in one split — pre- and post-fault rows from the
  same 12-minute run are highly autocorrelated, so splitting rows within a run leaks
  the run's own signature across splits (see leakage risk below).
- **Stratify the split by `(service, fault_type)` combo, not just randomly by case.**
  With only 5 runs per combo, a naive random 100-case split risks a combo (e.g.
  `checkoutservice_loss`) being entirely absent from train or entirely absent from
  test. Recommend something like: for each of the 20 combos, put 3 runs in train, 1 in
  validation, 1 in test (or 3/1/1-style, adjustable) — guarantees every combo is
  represented in every split while keeping whole runs intact.
- Optionally hold out **one or two entire combos** (not just runs) purely for a
  generalization check ("does the model detect a fault type/service pairing it never
  saw at all"), reported separately from the main stratified split — useful evidence
  for the report's discussion of generalization, but not the primary split.

## E. Leakage risks

1. **Row-level leakage within a run** (see D) — the main risk, avoided by splitting on
   whole cases.
2. **Fixed injection position (t=360s in all 100 cases) is a shortcut a model could
   learn.** If elapsed-time-in-window or raw row index is ever exposed as a feature
   (directly or via positional encoding), a model can trivially learn "index ≥ 361 →
   anomalous" without learning any real telemetry signal, and that trick would
   transfer suspiciously well across the whole dataset because the injection point
   never moves. Recommend: do not feed absolute row index/elapsed time as a raw
   feature; if temporal position is needed, keep it implicit (e.g. via a
   sequence-aware model's own internal state) rather than explicit.
3. **Repeated-run similarity inflating apparent performance.** The 5 runs within one
   combo are the same fault type on the same service under (presumably) a similar load
   pattern — they are not independent in the way 5 truly different incidents would be.
   A random case-level split can still let a model "recognize" a combo's signature from
   3 training runs and just pattern-match the other 2, which will look like strong
   generalization but partly isn't. The combo-holdout check in D partially addresses
   this; worth calling out explicitly in the report as a known ceiling-inflation risk
   rather than something fully solved by case-level splitting alone.

## Recommendations (schema / features)

- **Safest common feature set:** the 55-column intersection listed in
  `column_presence.csv` (`present_in_all == True`, excluding `time`) — every one of
  these is present in all 100 cases with no cross-case schema inconsistency.
- **Exclude for Model 1:** the 7 varying-presence columns — `adservice_error`,
  `cartservice_error`, `checkoutservice_error`, `frontend_error`,
  `frontend-external_error`, `productcatalogservice_error`, `istio-init_mem`. Reasons:
  inconsistent presence across cases (true schema gap, not derivable from a fixed
  imputation rule without a modeling decision), and where present they are flat/zero
  in a large fraction of cases anyway (low information density).
- **Schema harmonization is required before modeling** — `simple_data.csv` files are
  not schema-identical across all 100 cases (56–59 raw metric columns per case vs. 55
  in the guaranteed intersection). Any loader must explicitly select the 55-column
  intersection (or an explicitly documented alternative) rather than assuming
  `pd.concat` across cases will align cleanly.
- **Per-metric scaling is required** given the scale spread noted in A.13 — deferred
  to Model 1 design, not done here.

## Commands used

```bash
cd scripts/model1/dataset_inspection
python3 inspect_dataset.py --data-dir <BARO_DATA_DIR> --out-dir ../../../data/model1/dataset_inspection
python3 inspect_schema_and_missingness.py --data-dir <BARO_DATA_DIR> --out-dir ../../../data/model1/dataset_inspection
```

`<BARO_DATA_DIR>` is the path to BARO's `data/fse-ob` directory on your machine (see
`commands.txt` in this folder). No files under the BARO clone were modified. No data
was re-downloaded.
