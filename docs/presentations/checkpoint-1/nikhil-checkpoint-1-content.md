# Nikhil Checkpoint 1 LLM Presentation Section

Task: 298-21. Two content slides, no cover. Suggested speaking time: approximately 3–4 minutes total. All proposed architecture and evaluation choices remain proposals.

## Slide 1: LLM diagnosis and remediation research

### Incident-text generation

Ahmed et al., ICSE 2023
Fine-tuning supports diagnosis and mitigation from incident text.
Private production data limits reproduction.

### Evidence and historical cases

RCACopilot, EuroSys 2024
GPT-4 root-cause category micro-F1: 0.766 (Table 2).
Production handlers and data limit portability.

### Public telemetry and analysis tools

OpenRCA, ICLR 2025
RCA-agent selectively analyzes logs, metrics, and traces with Python.
Public code and evaluation support a focused pilot.

Proposed LLM approach: selective evidence tools plus retrieval and summarization

### Speaker notes

My section asks how the LLM can turn operational evidence into a useful diagnosis and a proposed repair. Ahmed and colleagues studied incident titles and summaries using zero-shot, fine-tuned, and multitask language models. Their ICSE 2023 study supports domain adaptation, but the confidential incident corpus makes exact reproduction difficult.

RCACopilot collects diagnostic evidence through incident handlers and retrieves historical examples. In Table 2, its GPT-4 configuration reports micro-F1 of 0.766 and macro-F1 of 0.533 for root-cause category prediction, with average inference time of 4.205 seconds in that study. Those figures are published results, not our results or an end-to-end recovery guarantee.

OpenRCA provides code, telemetry download instructions, and evaluation scripts. RCA-agent uses Python to inspect logs, metrics, and traces selectively. This makes it the most practical LLM research starting point among these three works. I propose combining selective evidence tools with retrieval and summarization, initially without fine-tuning. The exact model and LLM evaluation dataset still need team agreement. CausalRCA remains our separate selected reproduction baseline.

## Slide 2: Proposed LLM component and controls

### Inputs and outputs

Inputs: anomaly window, candidate services, metrics, logs, traces, alerts, and runbooks.
Outputs: evidence-linked diagnosis, cause explanation, and remediation proposal.

### Grounding and safety

Filter evidence by time and service. Check cited support and allow abstention.
Pass proposals to the action-risk gate before any execution.

### Feasibility and evaluation

Start with API inference and bounded tool calls. Profile latency and token cost.
Full OpenRCA setup: 32 GB RAM, 80 GB storage. Subset needs measurement.

Pipeline role: follows detection and localization, then hands proposals to the risk gate

### Speaker notes

The anomaly detector first supplies the incident window. The service-graph component supplies candidate services. My LLM component then retrieves relevant metrics, trace neighborhoods, log excerpts, alerts, and runbooks using the same time window and service identifiers. SMD alone cannot support this stage because it has metrics without logs, distributed traces, or a service graph. OpenRCA and suitable RCAEval suites remain candidates for later diagnosis evaluation.

The output should contain a diagnosis, a root-cause explanation linked to evidence, and a remediation proposal with its target, preconditions, verification steps, and rollback requirements. If evidence is missing or contradictory, the model should state uncertainty and request review. The separate action-risk classifier and hard policy checks decide whether any proposal can execute. The LLM has no direct execution authority in the proposed first prototype.

Hallucination is a risk even when citations are present, so we must check whether cited evidence supports each claim. Time and service filtering reduce irrelevant context, but can omit useful evidence, so retrieval should be logged. We will cap tool rounds and tokens, cache reusable summaries, and report latency and inference cost. OpenRCA’s full setup recommends 32 GB RAM and 80 GB storage. A subset pilot must be profiled before we promise a smaller budget. API inference avoids local model training, but still incurs API cost. No LLM experiments have been run for this section. I hand the proposed action and its supporting evidence to the safety-gate section.

## References

- Ahmed et al. (ICSE 2023), Recommending Root-Cause and Mitigation Steps for Cloud Incidents Using Large Language Models. https://doi.org/10.1109/ICSE48619.2023.00149 ; https://arxiv.org/abs/2301.03797
- Chen et al. (EuroSys 2024), Automatic Root Cause Analysis via Large Language Models for Cloud Incidents. Table 2. https://doi.org/10.1145/3627703.3629553 ; https://arxiv.org/pdf/2305.15778
- Xu et al. (ICLR 2025), OpenRCA: Can Large Language Models Locate the Root Cause of Software Failures? https://openreview.net/forum?id=M4qNIzQYpd ; implementation and compute guidance: https://github.com/microsoft/OpenRCA
- Team baseline decision: https://github.com/sjsu-298a-team1/self-healing-cloud-systems/blob/8b4f6a7/docs/baseline/baseline-selection/causalrca-baseline-selection.md

## Integration notes

Place this section after detection/localization and before the safety gate. Retain CausalRCA as the selected published reproduction baseline. OpenRCA is an LLM pilot candidate. Bhoomika’s review reports that Template 2 specifies eight slides, with 17 minutes of presentation and 3 minutes of Q&A. This conflicts with the ten-slide limit in Linear. Plan for eight slides until the team confirms the current course instructions; keep Nikhil’s section within the agreed allocation. Include these notes in the presenter view, not as extra slides.

## Evidence coverage

Slide 1 covers the three studies, findings, promising approach, and references. Slide 2 and its notes cover operational inputs and outputs, grounding, hallucination, unsafe recommendations, compute, latency, and pipeline integration. Bhoomika’s PR review reports no changes needed to this LLM section. Final team-deck integration remains outstanding.
