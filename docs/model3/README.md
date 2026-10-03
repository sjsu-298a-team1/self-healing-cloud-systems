# Model 3 — LLM Incident Diagnosis + Remediation-Plan Generator

**298A: DESIGN ONLY.** No implementation, training, fine-tuning, or evaluation exists
for Model 3 in this repository. This document records verified, design-level facts
only, per `docs/project/semester_scope.md`.

**298B: IMPLEMENT/TRAIN.**

Approved role (per `docs/abstract/298-14-abstract-declarations.md:22`): "LLM diagnosis
and remediation-plan generator."

## Intended task

Given an anomaly flagged by Model 1 and a candidate root-cause ranking from Model 2,
produce (1) a human-readable diagnosis explanation and (2) a structured remediation
plan proposal, to be passed to Model 4 for risk gating before any action executes.

## Expected inputs from Models 1 / 2

| From | Verified shape (as currently implemented/designed) | Source |
|---|---|---|
| Model 1 | Per-window anomaly score (MSE-based reconstruction error), a binary detection flag relative to the frozen threshold (`0.8249893178835667`), and a detection timestamp | `experiments/model1/model1_final_summary.json`, `scripts/model1/evaluation/scoring.py` |
| Model 2 | Design-level only (see `docs/model2/README.md`): a ranked list over 13 candidate services (coarse-grained root-cause localization). **Exact output schema is still TBD** — `docs/model2/README.md` documents the design (architecture family, candidate set, metrics) but no implementation or committed output format exists yet | `docs/model2/README.md`; `docs/abstract/298-14-abstract-declarations.md:22` |

## Expected structured outputs

**TBD.** No output schema has been designed or committed. Candidate fields (not yet
decided, not implemented): affected service, fault-type guess, natural-language
explanation referencing supporting telemetry evidence, and a proposed remediation
action drawn from a fixed action vocabulary (see Model 4 for the only committed
action-list reference, `docs/literature/safe-remediation/README.md`).

## What BARO currently provides (verified)

Directly verified from `~/298A_project/code/baro/data/fse-ob/` case-folder contents
(e.g. `cartservice_cpu/1/`):

- `data.csv`, `simple_data.csv` — Prometheus/Istio metric time series only.
- `inject_time.txt` — a single Unix timestamp (oracle fault-injection time).
- `naive_bocpd.json`, `robust_bocpd.json`, `univariate_bocpd.json`, `bocpd_time.json`,
  `nsigma.json`, `spot.json`, `birch.json` — BARO's own baseline-algorithm outputs
  (changepoint/anomaly-detector results), not ground-truth labels.
- `plot.png`, `postprocess.log` — a rendered plot and a processing log.

## What BARO does NOT provide (confirmed absent)

Confirmed by direct inspection of every file type present in the case folders above
— **none of the following exist anywhere in the `fse-ob` artifact**:

- Application or system **logs** (no log files of any kind).
- Distributed **traces** (no span/trace data).
- **Runbooks** or remediation procedure documents.
- **Remediation action labels** (no record of any repair action ever being taken).
- **Outcome labels** (no record of whether any hypothetical remediation would have
  succeeded).

This matches the literature review's own finding: `docs/literature/safe-remediation/README.md`
line 303 — "The missing resource is labelled action outcomes... Our fault-injection
setup can generate it, at small scale... [but has not yet done so]."

## Feasible diagnosis target (design-level proposal, not implemented)

Given the data actually available, the most defensible diagnosis target is
**(service, fault type)** classification — e.g. "cartservice, cpu" — since this is
exactly the ground truth BARO's own case-folder naming convention already encodes
(`<service>_<fault_type>/<run_id>/`, verified: 5 services × 4 fault types). A richer
free-text diagnosis is possible as an LLM-generated explanation layered on top of this
classification, but the classification itself is the only target with real,
verifiable ground truth today.

## Remediation-data gap

**Confirmed, not assumed.** No remediation action, action outcome, or rollback record
exists anywhere in the BARO artifact or this repository. Per
`docs/literature/safe-remediation/README.md`'s own conclusion (line 52): "None of the
three [reviewed] approaches offers a reproducible baseline" for exactly this reason —
the field-wide gap is that "these methods need data nobody publishes: histories of
remediation actions with recorded outcomes" (line 303). This gap applies identically
to Model 3's remediation-plan-generation half of its role. **Collecting this data is
298B work**, not yet started.

## Candidate architecture families (not selected — no evidence basis to select yet)

**TBD.** No architecture has been selected. Documented candidates from literature
review only, none implemented or benchmarked:
- Retrieval-augmented generation over telemetry evidence (retrieval tooling only;
  no fine-tuning) — closest to what `docs/presentations/checkpoint-1/nikhil-checkpoint-1-content.md:39`
  describes as "selective evidence tools with retrieval and summarization, initially
  without fine-tuning" (historical Checkpoint 1 framing, not re-validated for BARO).
- A fine-tuned/prompted LLM directly on structured telemetry features — not
  evidenced, not attempted.

Do not select an architecture without evidence: **TBD remains TBD** until 298B.

## Likely evaluation metrics (candidate, not committed)

- Diagnosis accuracy: correct (service, fault-type) classification rate — feasible
  today, ground truth exists.
- Remediation-plan quality: **no metric defined** — blocked on the remediation-data
  gap above.
- MicroRemed (`docs/literature/safe-remediation/README.md` lines 44, 373-375) is
  explicitly **not recommended as a safety/correctness baseline** ("does not measure
  whether the repair was safe to attempt"), but is noted as a possible later
  comparison specifically for repair-script generation quality, not diagnosis.

## Data/resources that must be obtained or created in 298B

1. Recorded remediation-action history with outcomes (does not exist; must be
   generated via the team's own fault-injection experiments, per
   `docs/literature/safe-remediation/README.md` line 382).
2. A committed Model 2 output schema to consume as input (does not yet exist in
   this repository).
3. A decision on architecture family (RAG vs. fine-tuned vs. other) — currently TBD.
4. A decided and committed structured-output schema for the remediation plan.

## Unresolved baseline/comparator question

**No reproducible published baseline exists for this pillar**, confirmed directly by
the literature review (`docs/literature/safe-remediation/README.md` lines 52, 291-301):
no reviewed paper releases code or data for diagnosis+remediation generation with
safety labels. MicroRemed is the only runnable public artifact in the broader area but
measures a different question (repair-script correctness, not diagnosis or safety).
**Whether Model 3 will have any reproducible numerical comparator at all remains
unresolved** — this is a question for the team/professor, not something this document
resolves.
