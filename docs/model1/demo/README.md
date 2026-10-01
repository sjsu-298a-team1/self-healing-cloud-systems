# Model 1 preprocessing and data-quality demo

Issue 298-37. A single command that runs the whole Model 1 data chain end to end
against a local copy of the BARO Online Boutique artifact, prints evidence at each
stage, and re-derives the committed split manifests and scaler from raw data to check
they still reproduce.

## Why this exists

The pipeline it demonstrates already existed before this issue — 298-33 built the
dataset inspection, 298-35 the deterministic split and preprocessing, 298-36 the
evaluation metrics and protocol validation. What did not exist was a way to *show* it.

Running the chain by hand means six commands across three directories, with
`--data-dir`, `--configs-dir`, `--manifests-dir` and `--inspection-dir` threaded
between them, and the results scattered across seven generated files plus a 160-line
findings document. That is fine for development and impossible to run live in front of
an audience.

This wraps it into one command that finishes in about 12 seconds.

## Running it

```bash
python3 scripts/model1/demo/run_data_demo.py --data-dir <BARO_DATA_DIR>
```

`<BARO_DATA_DIR>` is the extracted `fse-ob` directory — see
[docs/data/README.md](../../data/README.md) for how to obtain it. Needs only numpy and
pandas; torch is not required, since nothing here trains or loads a model.

Options:

| Flag | Effect |
|---|---|
| `--work-dir <path>` | Where regenerated artifacts go. Default: a fresh temp directory. |
| `--keep` | Keep the work directory instead of deleting it on exit. |

Exit code is 0 only if every stage passes, so it can be used as a check rather than
read by eye.

## What it does not do

**It never writes to committed artifacts.** The committed configs are copied into the
work directory first, everything is regenerated there, and the committed files under
`configs/model1/` and `data/model1/` are only ever read for comparison. A demo that
overwrote the artifacts it was demonstrating would be worse than useless.

It also does not train anything, load a checkpoint, or touch the test split beyond
confirming the manifest is disjoint from the others.

## The six stages

**1. Dataset integrity and structure.** Confirms 100 cases across 20 service/fault
combinations, every case exactly 721 rows spanning 720 seconds at a uniform 1 Hz, no
duplicate rows, no duplicate timestamps, and fault injection at the exact midpoint of
every single case. The consequence is what matters: each case is 360s of known-normal
data followed by 360s of post-injection data.

**2. Data quality.** Quantifies what is actually wrong with the data rather than
asserting it is clean. 2,630 missing cells out of roughly 4.1 million, which is 0.064%,
and concentrated rather than uniform. 90 of 100 cases contain at least one locally
constant column, almost entirely istio `*_error` counters that legitimately stay flat
when no errors occur during a 12-minute window. Metric scales differ by orders of
magnitude, which is why per-feature normalisation is required rather than optional.

**3. Deterministic splits reproduce.** Rebuilds the 60/20/20 train/val/test manifests
from the raw data and the committed seed, checks they are pairwise disjoint and cover
all 100 cases exactly once, then compares them against the manifests already in the
repository. This turns the determinism claim into something observable: the same raw
data and the same seed produce the committed split exactly, on a different machine.

**4. Train-only scaler reproduces.** Refits the z-score scaler from scratch and
compares all 55 features against the committed `scaler.json`. The scaler is fitted on
pre-fault rows of train-split cases only — 60 cases × 360 rows = 21,600 rows — so
validation and test data never influence normalisation.

**5. Automated protocol checks.** Runs the five locked checks from `validate_protocol.py`:
split overlap, feature consistency, train-only scaler fit, no time or index leakage,
and fault-type stratification.

This stage also surfaces the **negative control**, which is the most convincing single
piece of evidence in the pipeline. Deliberately adding one validation case to the
scaler fit measurably shifts the result, which proves the check can actually detect
contamination rather than passing vacuously. A check that cannot fail proves nothing.

**6. Windowing.** Builds the training windows and reports the result: 4,020 windows,
tensor shape `[4020, 30, 55]`, 67 windows from each of the 60 training cases, and —
checked rather than assumed — every window lying strictly in the pre-fault region.

## Evidence summary

The numbers the demo prints, gathered here for reference:

| Property | Value |
|---|---|
| Cases | 100 (5 services × 4 fault types × 5 runs) |
| Rows per case | 721, spanning 720s at 1 Hz |
| Fault injection point | exact midpoint of every case, 360s pre / 360s post |
| Duplicate rows / timestamps | 0 / 0 |
| Missing cells | 2,630 of ~4,109,700 (0.064%), concentrated in a few columns |
| Cases with a locally constant column | 90 of 100, almost all istio `*_error` counters |
| Features used | 55 (the intersection present in all 100 cases) |
| Split | 60 train / 20 val / 20 test, case-disjoint, seeded per combo |
| Scaler fit on | 21,600 pre-fault training rows only |
| Training windows | 4,020, shape `[4020, 30, 55]`, all strictly pre-fault |
| Runtime | about 12 seconds |

## Mapping to Checkpoint 2

Checkpoint 2 asks for a clean dataset, fixed splits, justified metrics, and end-to-end
data extraction demonstrated live.

| Requirement | Where it is shown |
|---|---|
| Clean dataset | Stages 1 and 2 |
| Fixed splits | Stage 3, including regeneration against the committed manifests |
| Justified metrics | Stage 5, protocol checks; formulas and targets in [protocol.md](../protocol/protocol.md) §7 |
| End-to-end extraction, live | The whole run, raw CSV through to model-ready tensors, in one command |

## Limitations

This demonstrates the **data** half of Model 1. It deliberately stops at model-ready
tensors and does not train, score, or evaluate, so it says nothing about Model 1's
held-out performance — for that see `experiments/model1/model1_final_summary.json`,
including the validation-to-test generalisation gap recorded there.

The comparisons in stages 3 and 4 prove the committed artifacts are **reproducible**
from the raw data. They do not independently prove the artifacts are *correct*; that
is what the protocol checks in stage 5 and the hand-computed metric tests in
`tests/model1/test_metrics.py` are for.

Stage 2 reports a missing-cell percentage against an approximate total cell count,
since the number of metric columns varies between 56 and 59 across cases. The absolute
count of 2,630 is exact; the percentage is indicative.
