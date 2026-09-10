298-18 — Khushi Checkpoint 1 Presentation Content

Issue: 298-18 — Prepare Project Setup, Dataset & Benchmark Presentation Section
Presenter: Khushi Donda
Project: AI-Driven Incident Response and Self-Healing Cloud Systems
Course: DATA 298A — Checkpoint 1

Project Setup

GitHub repository: https://github.com/sjsu-298a-team1/self-healing-cloud-systems

Linear board: https://linear.app/298a-team-1-self-healing-cloud/team/298/all

Shared GitHub organization and repository are active.

main is protected.

Pull requests are required before merging.

At least one teammate approval is required before merge.

Linear and GitHub are used together so each issue can be traced to its supporting artifact.

Slide — Data & Benchmark Strategy

SMD — Primary Dataset for 298A

Five-week server telemetry collection

28 machines

38 metrics per machine

Training and test data provided

Point-level anomaly labels available

Access verified on September 9, 2026

A real telemetry file, machine-1-1.txt, was downloaded and inspected locally

Why SMD first:
SMD gives the team immediately accessible, labeled, multivariate time-series telemetry. This makes it suitable for implementing and evaluating the first 298A model without first building the full microservice environment.

RCAEval — Root-Cause Analysis Benchmark

Public RCA benchmark for microservice troubleshooting

Includes multi-source telemetry across benchmark environments

Contains labeled failure cases and root-cause information

Planned for later root-cause localization experiments

Useful for evaluating service-level and metric-level RCA methods

Role in the project:
RCAEval complements SMD because it provides the richer microservice context needed for later root-cause localization work.

OpenTelemetry Demo + Chaos Mesh — Planned Testbed

OpenTelemetry Demo will provide the planned microservice environment

Chaos Mesh will be used for controlled fault injection

Intended to generate metrics, logs, traces, and labeled incident scenarios

Supports later end-to-end testing of detection, RCA, diagnosis, and remediation

Current status:
This is the planned testbed for later stages. It is not the primary dataset for the first 298A model.

First Model and Evaluation Target

First model: Multivariate time-series anomaly detector
Selected dataset: SMD
Primary metric: F1-score
Preliminary target: F1 >= 0.85

The target is defined before model experimentation so the team has a clear numerical success criterion.

Published Baseline

Selected published baseline: CausalRCA
Paper: Xin, Chen & Zhao (2023)
Experiment to reproduce: Table 4 — fine-grained root-cause metric localization

Published results selected for reproduction:

AC@1 = 0.2476

AC@3 = 0.7190

Avg@5 = 0.6681

The CausalRCA reproduction is separate from the team's first anomaly-detection model. It serves as the published reference point required by the course.

Data Strategy by Project Stage

Stage

Data / Environment

Purpose

298A first model

SMD

Multivariate anomaly detection

298A baseline reproduction

CausalRCA released data/code

Reproduce published RCA result

Later RCA evaluation

RCAEval

Root-cause localization benchmark

Later end-to-end testing

OpenTelemetry Demo + Chaos Mesh

Controlled faults and multi-source telemetry

Known Limitation

SMD contains multivariate server metrics but does not provide the full logs, distributed traces, and service topology needed for end-to-end microservice root-cause analysis.

That is why the project starts with SMD for the first model and expands to RCAEval and the OpenTelemetry/Chaos Mesh testbed for later components.

Presenter Talking Points

We selected SMD because it is accessible now and gives us labeled multivariate telemetry for the first model.

We verified access by downloading and inspecting an actual SMD telemetry file.

Our first numerical target is F1 >= 0.85 on held-out SMD test data.

RCAEval is reserved for later RCA work because it contains the richer microservice context that SMD lacks.

OpenTelemetry Demo plus Chaos Mesh is our planned controlled testbed for generating multi-source telemetry and injected fault scenarios.

CausalRCA is our published reproduction baseline, specifically the fine-grained Table 4 result.

The baseline reproduction and the first anomaly-detection model are separate evaluation tasks.

Evidence

Supporting project evidence is available in the repository under:

docs/data/dataset-benchmark-evaluation/

docs/baseline/baseline-selection/

docs/infra/environment-evaluation/

docs/checkpoint-1/

This file documents Khushi Donda's Checkpoint 1 presentation contribution for Linear issue 298-18.
