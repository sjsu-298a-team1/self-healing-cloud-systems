# Model 2 — Service-Graph Root-Cause Localization

**298A: DESIGN ONLY.** No implementation, training, fine-tuning, or evaluation exists
for Model 2 in this repository. This document records already-verified design work
(from read-only inspection), per `docs/project/semester_scope.md`.

**298B: IMPLEMENT/TRAIN/EVALUATE.**

Approved role (per `docs/abstract/298-14-abstract-declarations.md:22`): "service-graph
root-cause localization model."

## Task

Coarse **service-level** root-cause localization: given a detected anomaly, rank
which of BARO's 13 ranking candidates is the actual injected root cause.

## Architecture family

A small **Graph Attention Network (GAT)**. Not yet implemented, not yet sized or
tuned — this names the architecture family only.

## Candidate set

All **13 BARO ranking candidates**, confirmed by running BARO's own unmodified
`robust_scorer()` + `to_service_ranks()` on real test cases: 10 application
microservices (`adservice`, `cartservice`, `checkoutservice`, `currencyservice`,
`emailservice`, `frontend`, `paymentservice`, `productcatalogservice`,
`recommendationservice`, `shippingservice`) + `redis` (datastore dependency) +
`frontend-external` (same backend as `frontend`, confirmed via the official
Online Boutique Kubernetes manifest's `Service`/`LoadBalancer` selector) +
`main` (strong evidence-backed inference: the official manifest names the
`loadgenerator` Deployment's container literally `main`, which uniquely explains
why `main_*` columns are cpu/mem-only).

## Ground truth

The injected-fault service, read directly from BARO's case-folder naming
convention: `<service>_<fault_type>/<run_id>/` (e.g. `cartservice_cpu/3` → ground
truth = `cartservice`). Confirmed: only 5 of the 13 candidates (`cartservice`,
`checkoutservice`, `currencyservice`, `paymentservice`, `productcatalogservice`)
are ever the injected fault target; the other 8 candidates never appear as ground
truth in this dataset.

## Input representation — 10-D node vector

No common metric vocabulary is shared by all 13 candidates (3 of them —
`frontend-external`, `main`, `redis` — are missing 3-4 of the 5 metric types that
the 10 application services have). Proposed fixed-dimensional representation per
node, identical shape for all 13:

| Dim | Field |
|---|---|
| 1 | `cpu` (z-scored, if present) |
| 2 | `mem` (z-scored, if present) |
| 3 | `workload` (z-scored, if present) |
| 4 | `latency-50` (z-scored, if present) |
| 5 | `latency-90` (z-scored, if present) |
| 6-10 | presence-mask bit for each of the 5 slots above (1 = real telemetry column exists for this node/metric, 0 = absent) |

The mask bits exist specifically so "metric absent" is never silently confused with
"metric value zero" for the 3 sparse-coverage candidates.

**No service-ID or service-name embeddings.** Node identity must never enter the
model as a learned or one-hot feature — only the 10-D telemetry vector above.

**Shared node transformation.** The same per-node scoring function (identical
weights) must be applied to every node regardless of its position in the graph;
node order must be randomized per training example so no position-to-label
shortcut can be learned.

## Graph topology

**Assumed Online Boutique topology**, reconstructed from a **pinned public version**
of `GoogleCloudPlatform/microservices-demo` (tag `v0.8.0`, 2023-06-15 — the most
version-relevant snapshot found: its `src/` service list has no extra services
beyond BARO's telemetry footprint, unlike the current `main` branch which has since
added a 12th service), cross-checked two independent ways (gRPC client source code
+ an exhaustive scan of every Kubernetes Deployment's env vars), and then mapped
onto BARO's 13 ranking candidates.

**This must never be called authoritative BARO topology.** BARO's own artifact
contains no topology file, version identifier, deployment manifest, or
service-call-graph anywhere (confirmed by exhaustive search of the BARO clone).
The topology above is an external, reconstructed assumption applied to BARO's
candidate set — not something BARO itself states or ships.

Proposed edges (all confirmed from the pinned public source/manifest, not
BARO's own artifact): `frontend` → 7 services; `checkoutservice` → 6 services;
`recommendationservice` → `productcatalogservice`; `cartservice` → `redis`;
`main` (loadgenerator) → `frontend`; `frontend-external` ↔ `frontend` as a
same-backend alias edge (not a call edge).

## Direct BARO RCA comparison — exact frozen Model 1 test cases

Model 2's planned evaluation reuses the **exact same 20 frozen Model 1 test cases**
(`data/model1/manifests/test_cases.json`) — not a separate split — so any future
Model 2 result is directly comparable to BARO's own coarse RCA performance on the
identical cases Model 1 was evaluated on.

**Verified BARO result on those 20 cases** (unmodified BARO code, run against the
real `fse-ob` artifact):

| Metric | Value |
|---|---|
| AC@1 | 0.700 |
| AC@3 | 0.900 |
| Avg@5 | 0.880 |

## Metric priority

- **Primary planned Model 2 metric: AC@1.**
- **Secondary: AC@3.**
- **Compatibility metric: Avg@5** — reported only for comparability with BARO's own
  published/reproduced numbers, **not treated as a primary success measure**, because
  only 5 of the 13 candidates can ever be a true positive: a method that does nothing
  but restrict its guesses to the known 5 fault-prone services already scores
  Avg@5's top-5 component at 100% by construction, independent of any real
  diagnostic skill. AC@1 and AC@3 still require discriminating among the 5
  plausible services using real signal, so they do not have this same structural
  inflation risk.

## Shortcut protections (required, not optional)

1. **No service-identity embeddings** — no learned or one-hot node-ID feature may
   enter the model (see Input representation above).
2. **Leave-one-target-service-out evaluation** — train with one of the 5
   fault-target services' positive examples entirely withheld (it is only ever seen
   as a quiet background node during training), then test whether the model can
   still rank it correctly when it is the true fault. This directly falsifies the
   identity-shortcut hypothesis by construction, since a model that only learned
   "node X is sometimes root cause" cannot get the held-out service's cases right.
3. **Topology-only ablation** — same graph structure, telemetry replaced with a
   non-informative placeholder (mask bits also neutralized) at every node; if
   accuracy stays anomalously high under this ablation, the model is relying on
   structure/identity rather than telemetry.

## Proposed extra comparator — planned, not implemented

A **non-learned graph/scoring baseline**: BARO's own per-column `robust_scorer`
deviation scores, aggregated per node and then propagated/re-ranked over the
reconstructed topology above (e.g. max- or sum-aggregating neighbor scores). This
is a **planned 298B comparator**, explicitly not implemented, not benchmarked, and
not guaranteed to outperform plain BARO ranking — it exists only as a proposed
non-learned reference point between raw BARO scores and a trained GAT.

## Timing limitation

BARO's own `naive_bocpd.json`-based changepoint path — used both by BARO's
published methodology and by the comparison numbers above — has its detection
window **cropped using the oracle `inject_time.txt`** fault-injection timestamp
before any "detection" happens (verified: every `naive_bocpd.json`'s maximum row
index was exactly 600 across multiple sampled cases, matching a `read_data(strip=True)`
oracle-cropped window, not the raw ~721-row series). Any Model 2 evaluation that
reuses this committed timing artifact as-is inherits this oracle dependency; it is
**not** a fully oracle-free reproduction of "detect first, then localize." A
genuinely oracle-free timing path does not currently exist as a committed artifact
in either repository and is unresolved 298B work.
