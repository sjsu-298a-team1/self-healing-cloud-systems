# DATA 298A Abstract and Declarations Package

Project: AI-Driven Incident Response and Self-Healing Cloud Systems

Revision: September 10, 2026. Team review required; submission unverified.

## Project members

Draft order is alphabetical by displayed given name. Akhilesh Tandur; Bhoomika (full name to confirm); Khushi Donda; Nikhil Kanaparthi; Saketh Prudhvi Marru (official spelling to confirm).

# Abstract

## Purposes

Cloud incidents produce fragmented telemetry that can delay diagnosis and make automated recovery risky. This project aims to detect anomalies, localize likely causes, explain incidents using supporting evidence, and recommend recovery actions with explicit safety controls.

## Tasks

We will develop four models: a multivariate time-series anomaly detector; a service-graph root-cause localization model; an LLM diagnosis and remediation-plan generator; and an action-risk classifier gating autonomous execution. Initial anomaly detection will use the Server Machine Dataset (SMD). The prototype will use OpenTelemetry Demo, with controlled faults and synchronized metrics, logs, and traces. Retrieved incident evidence and runbooks will support LLM explanations. A separate risk gate will assess proposed actions before execution.

Separately from the four models, we will reproduce CausalRCA’s published fine-grained metric-localization experiment within a known faulty service on its Sock Shop benchmark, using Table 4 of Xin et al. (2023).

## Outcomes

We target an initial anomaly-detection F1 of at least 0.85 on SMD under a documented scoring protocol. CausalRCA reproduction will report AC@1, AC@3, and Avg@5 against published averages of 0.2476, 0.7190, and 0.6681, respectively. These are planned targets and published reference values, not project results. Later evaluation will measure diagnosis grounding, latency, inference cost, and unsafe-action blocking. SMD detection and Sock Shop localization will remain separate evaluations.

## Applications

The system could assist cloud operations teams with incident triage and recovery planning. Initial validation will use offline data and a controlled microservice environment, with human review for uncertain or risky actions.

# Declarations preparation

This worksheet supports completion of the official course form.

| Item | Information or action |
|---|---|
| Course and topic | DATA 298A, Topic 6. Confirm section and any identifiers requested by the official form. |
| Members | Five contributors appear in current task assignments. Confirm the roster above and the department’s alphabetical sorting convention. |
| Published baseline | CausalRCA, selected in 298-13. Reproduce Table 4 metric localization within a known faulty service. It does not evaluate discovery of the faulty service. |
| Benchmarks and targets | SMD: preliminary F1 ≥ 0.85. CausalRCA: Sock Shop data and AC@1 / AC@3 / Avg@5. Fix raw versus point-adjusted F1 and aggregation before reporting comparisons. |
| Data access | 298-11 records an SMD file download and inspection. CausalRCA notes confirm public data availability, with local loading and exact experiment coverage still to verify. |
| AI assistance | ChatGPT assisted with literature synthesis, abstract revision, slide content, speaker notes, and formatting. No new model experiments or baseline reproduction were performed for this package. |
| Authorship and approvals | Every member must review the text, verify their contribution, and complete their own required declarations. Review dates and approvals remain pending. |
| Official declarations | Transfer confirmed information to the official course form. Required wording, additional declarations, and signatures remain pending the form. |
| Submission | Deadline recorded in Linear: September 9, 2026. Submission status is unverified. Retain the final file, destination, timestamp, and confirmation receipt. |

# Finalization checklist

- [ ] Confirm Bhoomika’s full name, Saketh’s official spelling, all five members, and required name sorting.
- [ ] Approve the revised abstract and the preliminary SMD F1 target. Record each member’s dated review.
- [ ] Complete the official declarations form and any required signatures using each member’s own responses.
- [ ] Confirm the submission destination and current submission status, then retain the submission receipt.
- [ ] Keep the final deck consistent: CausalRCA is the selected baseline. Earlier MicroRCA recommendations and OpenRCA proposals do not supersede 298-13.
- [ ] Agree on slide allocation: existing Saketh and Bhoomika drafts propose four slides each, and Akhilesh has two. Nikhil’s two slides plus Khushi’s section require consolidation to meet the team’s ten-slide maximum.

# Sources

- [Baseline selection and exact published values](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/blob/8b4f6a7/docs/baseline/baseline-selection/causalrca-baseline-selection.md)
- [Dataset evaluation and preliminary SMD target](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/5)
- [Dataset access evidence](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/6)
- [CausalRCA paper](https://doi.org/10.1016/j.jss.2023.111724)
- [Abstract task requirements](https://linear.app/298a-team-1-self-healing-cloud/issue/298-14)
