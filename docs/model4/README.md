# Model 4 — Action-Risk Classifier / Safety Gate

**298A: DESIGN ONLY.** No implementation, training, fine-tuning, or evaluation exists
for Model 4 in this repository. This document records verified, design-level facts
only, per `docs/project/semester_scope.md`.

**298B: IMPLEMENT/TRAIN.**

Approved role (per `docs/abstract/298-14-abstract-declarations.md:22`): "action-risk
classifier gating autonomous execution."

## Intended task

Given a proposed remediation action from Model 3, score its risk and decide whether
it may execute automatically, requires human approval, or must be blocked outright,
before any action reaches the running system.

## Expected input from Model 3

**TBD / not committed.** Model 3 has no committed output schema (see
`docs/model3/README.md`); Model 4's input contract is therefore undefined until
Model 3's structured-output schema is decided in 298B. Design-level expectation
only: a proposed action drawn from a fixed, named action vocabulary (see action
table below), plus the diagnosis context that produced it.

## Expected output (still proposed, not implemented)

Per `docs/literature/safe-remediation/README.md`'s recommendation section (lines
305-334), the proposed (not implemented) output shape is a routing decision per
action: **Automatic / Escalate (approval-required) / Never-automated (block)**, plus
a recorded justification (which signals triggered the decision), following the
"gate must explain itself" requirement attributed to Gandalf (line 315, 234).
A numeric risk score feeding that routing decision is proposed, not implemented —
**TBD** on exact scoring function.

## Reversibility / blast radius (literature-review-stage proposal only)

The following action table is a **literature-review-stage proposal** written against
the now-superseded OpenTelemetry Demo fault-injection plan (`docs/infra/environment-evaluation/README.md`,
issue 298-12) — it has **not been re-validated against the current BARO/Online
Boutique direction** and is reproduced here only as existing design context, not as a
current commitment:

| Action | Reversibility | Blast radius | Proposed handling (298-16 recommendation) |
|---|---|---|---|
| Turn off a feature flag | High | One service | Automatic |
| Restart a container | High | One service | Automatic |
| Scale replicas up | High | One service, extra resource cost | Automatic above a confidence threshold |
| Roll back a deployment | Medium | Service and its callers | Escalate |
| Evict or drain a pod | Low | Node level | Escalate |
| Change a network policy | Low | Possibly cluster-wide | Never automated at this stage |

Source: `docs/literature/safe-remediation/README.md` lines 23-30, 323-330.

## Hard constraints (proposed, not implemented)

Two constraints proposed in the literature review, derived from the (superseded)
OpenTelemetry Demo plan, not yet re-validated for BARO/Online Boutique:

1. **Never remediate the observability plane** (no automated action may target the
   metrics/tracing/logging stack itself) — proposed as absolute and non-overridable
   for automated actions. (`docs/literature/safe-remediation/README.md` lines 336-343)
2. **One remediation at a time** — no overlapping automated actions while an earlier
   one is still being evaluated. (same doc, line 341)

## Circuit breaker / rate limiting (proposed, not implemented)

Proposed: no more than 3 automated actions within a 15-minute window, after which the
system stops acting and escalates until a person manually resumes it. **Explicitly
stated by the literature review itself as a starting value chosen by the reviewer,
not derived from any paper or from data** (`docs/literature/safe-remediation/README.md`
lines 347-353): "no paper supports it... We should revise this once we have run
enough experiments to see the real distribution."

## Does BARO contain action/context/outcome labels? Confirmed answer: NO

Verified by direct inspection of the `fse-ob` artifact's case-folder contents (see
`docs/model3/README.md`'s "What BARO does NOT provide" section for the full file-type
list). **No action labels, no action context, no action-outcome labels exist
anywhere in BARO's artifact.**

## Does safe/harmful-action ground truth exist? Confirmed answer: NO

No remediation action has ever been executed against this dataset (it is a telemetry
collection for anomaly detection and root-cause ranking, not a remediation-execution
log). There is therefore **no ground-truth label anywhere distinguishing a safe
action from a harmful one.** This is not an assumption — it follows directly from
"what BARO does NOT provide" above, and is independently confirmed by the literature
review's own field-wide finding: "the missing resource is labelled action outcomes...
nobody publishes [this]" (`docs/literature/safe-remediation/README.md` line 303).

## Data that must be generated or collected in 298B

1. **Action-outcome records**: for each (fault, candidate action) pair the team
   actually executes in a controlled experiment, record the action taken and whether
   it resolved the fault — this does not exist today and must be generated by the
   team's own fault-injection + remediation experiments, exactly as
   `docs/literature/safe-remediation/README.md` line 382 recommends ("Record every
   remediation attempt with the action taken, the injected fault, and the outcome.
   This is the data the reviewed methods depend on and none of them publish.").
2. A decided, committed action vocabulary validated against the **current**
   BARO/Online Boutique environment (the table above is from the superseded
   OpenTelemetry Demo plan and has not been re-derived for Online Boutique).
3. A committed Model 3 output schema to consume as input (does not yet exist).

## Candidate metrics (proposed, not committed, no target numbers)

Per `docs/literature/safe-remediation/README.md`'s recommendation (lines 357-367):
- **False remediation rate** (proposed primary safety metric) — share of executed
  repairs that were unnecessary or wrong. Computable only once action-outcome records
  exist (gap above).
- **Harmful-action rate** / **gate recall** (proposed secondary metric, "following
  Gandalf... share of unsafe actions the gate actually blocked") — same data
  dependency.
- **No numeric target is set for either metric.** The literature review explicitly
  recommends against inventing one: "we do not set a numeric target yet... any
  number we picked now would be invented... We should set the target after our first
  round of fault experiments" (same doc, lines 365).

## Unresolved comparator question

**No reproducible published baseline exists for action-risk gating**, confirmed
directly: none of the three reviewed systems (Dai et al., Narya, Gandalf) releases
code or data (`docs/literature/safe-remediation/README.md` lines 52, 172-184,
236-246). Narya and Gandalf are internal Azure production systems whose results
"cannot be compared" to anything the team could build (line 266). **Whether Model 4
will have any numerical comparator at all — or will only be measured against the
team's own recorded ground truth — remains unresolved** and is a question for the
team/professor, not something this document resolves.
