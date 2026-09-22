# Investigation: does the injected fault remain active for the full post-injection window?

Question asked: is there evidence — anywhere other than file length — that the
injected fault (CPU hog, memory leak, network delay, packet loss) remains
physically active from `inject_time` through the end of each 721-row case
(i.e. for the full ~360s post-injection segment), or is that assumption
unsupported?

## Sources checked

1. **Paper**: `<BARO_CLONE>/docs/paper.pdf` (read-only; extracted locally with
   `pdftotext -layout`, 1364 lines, into a local-only text file kept outside the
   BARO clone and not committed to this repo -- see "Data handling" note below).
   Full text searched for `duration|inject|minute|stop|revert|restore|remove|timeout|period`.
2. **Supplementary material**: `<BARO_CLONE>/docs/fse_baro_supplementary_material.pdf`
   (extracted locally the same way, 46 lines — entirely about Figures S1/S2, the
   `t_bias` sensitivity analysis; contains no fault-duration content).
3. **Artifact source code**: full-repo grep of `.py`/`.sh`/`.yaml`/`.yml`/`.md`
   files (excluding `env/` and `data/`) for `inject|chaos|duration|sleep|stress|
   tc qdisc|pumba|toxiproxy`. Only hits are downstream *analysis* code
   (`baro/utility.py`, `baro/reproducibility.py`, `baro/root_cause_analysis.py`,
   `run_bench.py`, `data_loader.py`) that reads `inject_time.txt` and splits data
   at that timestamp — **no fault-injection script is included in this repo**.
4. **Fault-injection configuration**: checked every file present in a sample
   dataset case folder (`data.csv`, `simple_data.csv`, `inject_time.txt`,
   `plot.png`, `postprocess.log`, six `*.json` baseline-algorithm outputs) —
   **no config file specifying stress-ng/tc parameters or a fault duration is
   bundled with the Zenodo artifact.**

**Data handling note:** the extracted paper/supplementary text used for this
investigation is not committed to this repo -- it reproduces large portions of a
published, copyrighted ACM paper. Anyone re-verifying this investigation should
re-extract locally from their own BARO clone's `docs/paper.pdf` (read-only) rather
than expect a copy in-repo. The quotes below are short excerpts kept under fair use
for citation/commentary, not the full extracted text.

## What the paper actually says (Section 4.1, p.12, local paper extract lines 664–687)

> "We inject four common anomalies: CPU hog, memory leak, network delay, and
> packet loss into several key services... For CPU hog and memory leak, we use
> **stress-ng** to stress the container resource. For network delay and packet
> loss, we use **tc** to manipulate the traffic of the container... For each
> combination of fault type and targeted service, we repeat the operation (i.e.
> fault injection and metrics data collection) five times... Furthermore, to
> ensure the independence of different injection experiments, we chose to
> **restart the microservice systems after each experiment** of injecting
> failures and collecting data, instead of waiting for a cooldown period..."

No `stress-ng` or `tc` command-line flags (e.g. `--timeout`, duration in
seconds) are given anywhere in the paper, supplementary material, or repo.

## What the paper says about the "anomalous period" (Section 4.2.1 and 3.4.1)

- Section 4.2.1 (evaluation metrics, the paper's own text, line 699 of the local extract): "We determine
  metrics data collected **during a fault injection period** as abnormal,
  while metrics data before that period is considered normal." This sentence
  never defines when the "fault injection period" *ends* — it is presented as
  self-evident, not derived from a measured fault-duration.
- Section 3.4.1 (RobustScorer algorithm, the paper's own text, lines 518–545) is more
  precise but purely **mathematical/procedural**: for a time series
  `x_{t0:t0+T}`, RobustScorer trains on `[t0, t̂_A)` (before the estimated
  anomaly time) and scores `[t̂_A, t0+T]` (up to **the end of the recorded
  window**) as the "anomalous period." `t0+T` is the end of data collection by
  definition of the notation, not an empirically confirmed fault-end time. This
  is the paper defining its own evaluation convention, not asserting that the
  physical stressor was still running at `t0+T`.

## Conclusion

**No direct evidence was found — in the paper, supplementary material, or
artifact code/config — that the physical fault remains active for the entire
post-injection segment.** The "abnormal from injection to end of collection"
framing in the paper is an **evaluation-metric convention** (how BARO scores
itself), not a verified claim about the underlying stressor's runtime.

Two fault families plausibly behave differently here, though neither is
confirmed:
- **`tc`-based faults (delay, loss)**: `tc qdisc` rules do not self-expire —
  they persist until explicitly removed or the container/pod is torn down.
  Since the paper states the system is restarted only *after* data collection
  finishes (not mid-collection), it's *plausible* delay/loss faults stayed
  active throughout. This is an inference from how `tc` behaves generally, not
  a statement in the artifact.
- **`stress-ng`-based faults (CPU, memory)**: `stress-ng` commonly takes an
  explicit `--timeout`, after which the stress process exits on its own,
  possibly well before the end of the 360s post-injection segment — if that
  happened, part of the "post-injection" data would reflect the system
  recovering to normal, not an active fault, while still being scored as
  anomalous under the paper's convention. No timeout value is disclosed
  anywhere, so this cannot be confirmed OR ruled out.

**Decision:** because this cannot be established from the available artifact,
the protocol terminology has been revised (see `configs/model1/protocol_config.json`
→ `labeling.terminology_revision` and `protocol.md`): `t >= inject_time` is now
called the **"post-injection evaluation region"**, not a guaranteed anomaly
label. Metrics computed against it (F1, precision, recall, detection delay,
pre-fault FPR) inherit this caveat and should be reported with it, especially
for CPU/mem fault types where premature fault self-termination is a real
possibility.

## Documented limitation (formal statement, added before training)

The artifact provides `inject_time` but **no verified fault-end time**. Therefore,
as a binding rule for this protocol going forward:

1. **`t < inject_time` is the known-normal region** — the only region in this
   dataset with a verified ground-truth label, since it strictly precedes fault
   injection — **and is the only region used to compute pre-fault FPR.**
2. **Detection delay is defined operationally**, purely as the time from
   `inject_time` to the first detection in the post-injection evaluation region.
   It does not assume, and does not require, that the fault was still physically
   active at the moment of detection.
3. **`t >= inject_time` is the "post-injection evaluation region,"** scored as
   anomalous following the dataset/paper convention (matching BARO's own
   `utility.py`/`reproducibility.py`), but this is **not claimed to represent
   verified active-fault ground truth at every timestamp** in that region.
4. **DELAY and LOSS must not be described as "confirmed persistent"** anywhere
   this dataset is discussed or reported — their plausible persistence (§ above,
   `tc` rules don't self-expire) is an inference from typical `tc` behavior, not
   direct artifact evidence. The same restraint applies to any claim about
   CPU/MEM fault duration: no timeout value is disclosed, so neither early
   self-termination nor full-duration persistence can be asserted as fact.
5. **Required mitigation**: evaluation must be reported **stratified by fault
   type (CPU, MEM, DELAY, LOSS)**, not only pooled, precisely so that any
   fault-duration-related difference in post-injection-region behavior between
   the two fault families is visible instead of being averaged away. Implemented
   in `scripts/metrics.py` (`fault_type_of_case`, `group_case_ids_by_fault_type`)
   and validated against all 100 real case ids by `scripts/validate_protocol.py`'s
   `fault_type_stratification` check (25 cases per fault type, confirmed).
