# DATA 298A Abstract and Declarations Package

Project: AI-Driven Incident Response and Self-Healing Cloud Systems

Revision: September 10, 2026. Team review required; submission unverified.

## Project members

Fnu Akhilesh; Khushi Donda; Nikhil Kanaparthi; Bhoomika Lnu; Saketh Prudhvi Marru.

Surname order follows the Canvas roster reported in the review. Registrar versus preferred names remain subject to team confirmation.

## Abstract

Cloud incidents produce fragmented telemetry that can delay diagnosis and make automated recovery risky. This project aims to detect anomalies, localize likely causes, explain incidents using supporting evidence, and recommend recovery actions with explicit safety controls. We will develop four models: a multivariate time-series anomaly detector; a service-graph root-cause localization model; an LLM diagnosis and remediation-plan generator; and an action-risk classifier gating autonomous execution. Initial anomaly detection will use the Server Machine Dataset (SMD) [1]. The prototype will use OpenTelemetry Demo, with controlled faults and synchronized metrics, logs, and traces. Retrieved incident evidence and runbooks will support LLM explanations, informed by prior research on incident generation, diagnostic retrieval, and telemetry analysis [2]–[4]. A separate risk gate will assess proposed actions before execution. Separately from the four models, we will reproduce CausalRCA’s published fine-grained metric-localization experiment within a known faulty service on its Sock Shop benchmark, using Table 4 of Xin et al. (2023) [5]. We target an initial anomaly-detection F1 of at least 0.85 on SMD under a documented scoring protocol. CausalRCA reproduction will report AC@1, AC@3, and Avg@5 against published averages of 0.2476, 0.7190, and 0.6681, respectively. These are planned targets and published reference values, not project results. Later evaluation will measure diagnosis grounding, latency, inference cost, and unsafe-action blocking. SMD detection and Sock Shop localization will remain separate evaluations. The system could assist cloud operations teams with incident triage and recovery planning. Initial validation will use offline data and a controlled microservice environment, with human review for uncertain or risky actions. Expected challenges include LLM inference cost and latency, incomplete telemetry, and errors propagated from detection into diagnosis and action selection. The reviewed safe-remediation systems do not provide a complete public reproduction package, so that component will require project-specific evaluation. We will record controlled-fault outcomes, retain evidence for proposed repairs, and assess safety separately from detection accuracy.

**Keywords:** Cloud incident response; multivariate anomaly detection; root-cause localization; large language models; safe remediation; microservices

## Project information

| Field | Information |
|---|---|
| Abstract word count | 309 words (whitespace count including citation markers; excludes title, names, keywords, table, and references). |
| Four project models | Multivariate time-series anomaly detector; service-graph root-cause localization model; LLM diagnosis and remediation-plan generator; action-risk classifier gating autonomous execution. |
| Published baseline | CausalRCA [5], fine-grained metric localization within a known faulty service. This is separate from the four project models. |
| Exact baseline result location | Table 4, average row: AC@1 = 0.2476; AC@3 = 0.7190; Avg@5 = 0.6681. Published values, not team measurements. |
| Datasets | SMD [1] for anomaly detection. CausalRCA’s collected Sock Shop metrics for the reproduction. OpenTelemetry Demo for controlled prototype experiments. LLM evaluation dataset remains to be selected. |
| Access status | 298-11 records an SMD training-file download and inspection. CausalRCA code/data are publicly listed; local loading and exact experiment coverage remain to verify. No reproduction run is claimed. |
| Evaluation metrics | Detection: precision, recall, F1. Baseline: AC@1, AC@3, Avg@5. Later: diagnosis grounding, latency, inference cost, and unsafe-action blocking. |
| Target criterion | Preliminary SMD F1 ≥ 0.85 under a fixed scoring protocol. For CausalRCA, compare reproduced averages with Table 4 and report deviations; the team must agree on a tolerance before evaluating reproduction success. Keep raw and point-adjusted F1 distinct. |
| GitHub URL | https://github.com/sjsu-298a-team1/self-healing-cloud-systems |
| Linear URL | https://linear.app/298a-team-1-self-healing-cloud/project/project-298a-ai-driven-incident-response-and-self-healing-cloud-24dc172293e0 |

## References

[1] NetManAIOps, “OmniAnomaly: ServerMachineDataset,” GitHub repository. Accessed: Sep. 10, 2026. [Online]. Available: https://github.com/NetManAIOps/OmniAnomaly/tree/master/ServerMachineDataset

[2] T. Ahmed, S. Ghosh, C. Bansal, T. Zimmermann, X. Zhang, and S. Rajmohan, “Recommending root-cause and mitigation steps for cloud incidents using large language models,” in Proc. 45th IEEE/ACM Int. Conf. Software Engineering (ICSE), 2023, pp. 1737–1749, doi: 10.1109/ICSE48619.2023.00149. https://doi.org/10.1109/ICSE48619.2023.00149

[3] Y. Chen et al., “Automatic root cause analysis via large language models for cloud incidents,” in Proc. 19th European Conf. Computer Systems (EuroSys), 2024, pp. 674–688, doi: 10.1145/3627703.3629553. https://doi.org/10.1145/3627703.3629553

[4] J. Xu et al., “OpenRCA: Can large language models locate the root cause of software failures?” in Proc. Int. Conf. Learning Representations (ICLR), 2025. [Online]. Available: https://openreview.net/forum?id=M4qNIzQYpd

[5] R. Xin, P. Chen, and Z. Zhao, “Causal inference based precise fine-grained root cause localization for microservice applications,” Journal of Systems and Software, vol. 203, Art. no. 111724, 2023, doi: 10.1016/j.jss.2023.111724. https://doi.org/10.1016/j.jss.2023.111724

## Declarations preparation

### Member names

Names and surname order follow the Canvas roster as reported in the PR review. Fnu and Lnu are registrar placeholders; the team must confirm whether to retain registrar names or use preferred names, then sort by the final surnames.

### AI assistance

ChatGPT assisted with literature synthesis, abstract revision, slides, speaker notes, and formatting. No model experiments or baseline reproduction were performed for this package. Complete the course’s required disclosure truthfully.

### Declarations and approvals

Complete the official course declarations and obtain each member’s required responses and signatures. Abstract approval and submission confirmation remain pending.

### Presentation integration

Bhoomika’s review reports that Template 2 specifies eight slides, with 17 minutes of presentation and 3 minutes of Q&A. This conflicts with the ten-slide limit in Linear. Plan for eight slides until the team confirms the current course instructions; keep Nikhil’s section within the agreed allocation.

## Finalization checklist

- [ ] Compare this revision with the actual DATA 298A Student Templates v5.docx before submission. The current revision follows the requirements quoted in the PR review; the template file itself has not been inspected.
- [ ] Confirm registrar versus preferred member names and the resulting surname order.
- [ ] Record each member’s review and approval, complete the official declarations, and retain the submission receipt.
- [ ] Confirm the eight-slide versus ten-slide discrepancy and the presentation time allocation.

## Review record

- Fnu Akhilesh: abstract approval and date pending.
- Khushi Donda: abstract approval and date pending.
- Nikhil Kanaparthi: abstract approval and date pending.
- Bhoomika Lnu: abstract approval and date pending.
- Saketh Prudhvi Marru: abstract approval and date pending.

## Revision basis and project evidence

- [Bhoomika’s review](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/16#issuecomment-5614512869)
- [Selected baseline](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/blob/8b4f6a7/docs/baseline/baseline-selection/causalrca-baseline-selection.md)
- [Dataset evaluation](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/5) and [access evidence](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/6).
