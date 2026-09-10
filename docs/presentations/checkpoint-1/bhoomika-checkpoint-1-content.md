# Bhoomika Checkpoint 1 Presentation Content

## Section Overview

This section summarizes:

- Why a self-healing system needs a safety gate before it acts.
- Findings from the safe autonomous remediation and action-risk gating literature review.
- The proposed gating design for Project 298A.
- The evaluation approach, the gap we found, and next steps.

This section continues directly from the anomaly detection and root-cause sections. Those sections end at a candidate remediation action. This section covers what happens between proposing an action and executing it.

Recommended section length: 4 slides.

---

# Slide 1: Research Focus

## Safe Autonomous Remediation and Action-Risk Gating

### Project problem

Once our system detects an anomaly and ranks a likely root-cause service, it can propose a repair. The remaining question is whether that repair should run automatically.

This matters because our upstream components are not perfect. Published root-cause methods report Top-1 accuracy well below 100%, and our own detector will produce false positives. A repair aimed at the wrong service does not fix the incident, and it changes a running system while the real fault is still active.

The central idea in this research area is that **the cost of an incorrect repair can exceed the cost of taking no action at all**.

### Research objective

Identify how prior work decides whether an automated remediation action is safe to execute, and select an approach that is:

- Applicable to the actions available in our environment.
- Measurable using the fault-injection ground truth we already plan to record.
- Realistic to implement during 298A.

### Where this section fits

```text
Detection -> Root-cause analysis -> Remediation proposal -> Risk gate -> Execute or escalate
```

The first two stages are covered by the anomaly detection and root-cause sections. This section covers the risk gate, which is the step between proposing a repair and running it.

### Key research observation

Not all repairs carry the same risk. Turning off an injected feature flag is fully reversible and affects one service. Changing a network policy is hard to undo and can affect services we did not intend to touch. A system that treats these as equivalent is unsafe regardless of how accurate its detection is.

### Speaker Notes

My section covers the last stage of our pipeline. The earlier sections detect that something is wrong and identify which service is responsible. My part is about what the system is then allowed to do about it.

The key point is that automation changes the risk profile. A detector that is wrong produces a false alert, which costs attention. A remediation system that is wrong modifies production during an incident, which can make the outage longer.

Because our root-cause model will sometimes rank the wrong service, we cannot assume the proposed repair is correct. The system needs a way to decide whether an action is safe enough to run without a person.

The literature calls this action-risk gating, and the research question I looked at is how prior work scores that risk and where it draws the line between acting automatically and asking a human.

---

# Slide 2: Literature Review Findings

## Three Approaches to Deciding Whether to Act

| Paper | Main focus | Key inputs | Important result | Main limitation |
|---|---|---|---|---|
| Dai et al. 2026 | Whether to intervene at all, as a risk-constrained decision | Dependency graph, rollback logs, ensemble disagreement, on-call context | False remediation rate 0.112 versus 0.183 for a runbook baseline, a 39% reduction | Preprint, not peer reviewed, no code or data released |
| Narya, OSDI 2020 | Which mitigation action to choose | Hardware and OS telemetry, control-plane operation signals | 26.2% reduction in VM interruption rate over 15 months in Azure production | Production system, no artifact, requires a large fleet |
| Gandalf, NSDI 2020 | When to stop an action that is going badly | Log-derived fault signatures, deployment records | 92.4% precision with 100% recall, and 99.2% of bad rollouts blocked before production | Production system, no artifact, assumes fleet-scale statistics |

### Main findings

- Risk can be decomposed into parts we can compute: **blast radius**, **reversibility**, and **epistemic uncertainty**.
- Escalation to a human should be treated as an action with its own cost, not as an exception. Narya includes Human Investigate directly in its action set.
- Safety constraints must not be overridable by the model. Narya forbids specific actions in specific scenarios regardless of what its learner recommends.
- Narya restricts high-impact actions to high-precision detection rules, which links this design directly to the quality of our anomaly detector.
- Narya reports that without safeguards its learner converged confidently on a single action in 27% of simulated cases, and 19% of those were the worst available action.
- Gandalf treats recall as the primary metric and explainability as a requirement for adoption, reporting that an unexplainable gate is not trusted even when accurate.

### Speaker Notes

I selected these three because they answer three different questions rather than being three versions of the same idea. Dai and colleagues ask whether to intervene, Narya asks which action to take, and Gandalf asks when to stop.

The Dai paper is the closest to our problem. It treats safe remediation as a constrained decision problem and splits risk into blast radius, reversibility, and uncertainty. Those three are computable in our environment.

Narya is the most useful for design because it writes its action set down explicitly and describes its safeguards. The most striking result is what happened without those safeguards. Their learning system converged with high confidence on the worst available action in a meaningful fraction of cases. That is the clearest evidence I found for why gating is necessary.

Gandalf is a gate rather than a repair system. It decides whether a rollout continues. Its most relevant number is that 99.2% of bad rollouts were blocked before reaching production, which the authors describe explicitly as limiting blast radius.

One caution on the table. These numbers are not comparable to each other. They come from different systems, over different periods, against different baselines, using metrics that do not convert into one another.

---

# Slide 3: Proposed Direction

## A Risk-Scored Gate Over an Explicit Action Set

### Recommended direction

Of the three reviewed systems, **the risk-constrained gating approach of Dai et al. is what we recommend adopting**. It is the only one that splits risk into parts we can compute in our own environment, and the only one that makes the safety budget an explicit setting rather than a value hidden inside a model. Narya and Gandalf contribute design patterns, the explicit action set and the stop-gate, but neither transfers to us as a method.

### Risk inputs the gate would use

| Input | Source | Available to us |
|---|---|---|
| Blast radius | Dai et al. | Yes, from the service dependency graph in our traces |
| Reversibility | Dai et al. | Yes, defined per action type |
| Epistemic uncertainty | Dai et al. | Yes, from ensemble disagreement in the detector |
| Diagnosis confidence | Dai et al. | Yes, from the root-cause ranking score |
| Service criticality | Dai et al. | Yes, assigned per service by the team |
| Rollback availability | Dai et al., trained on rollback logs | Partly, requires us to record rollback outcomes |
| Telemetry quality | Our addition | Yes, we can check that metrics, logs and traces are all present before acting |

Telemetry quality is our own addition rather than something taken from the papers. If telemetry is incomplete, the evidence behind a proposed repair is weaker. Gandalf offers a precedent through its veto rule, where evidence that does not hold up cancels an action instead of merely failing to support it.

### Remediation actions in our environment

Our environment evaluation defines the faults we can inject but does not define the repairs our system can attempt. This section proposes that list, scored by the risk dimensions above.

| Action | Reversibility | Blast radius | Proposed handling |
|---|---|---|---|
| Configuration change, such as turning off a feature flag | High | One service | Automatic |
| Restart a container | High | One service | Automatic |
| Scaling, adding replicas | High | One service, extra resource cost | Automatic above a confidence threshold |
| Rollback of a deployment | Medium | Service and its callers | Escalate to a human |
| Evict or drain a pod | Low | Node level | Escalate to a human |
| Routing change, such as a network policy | Low | Possibly cluster wide | Not automated at this stage |
| Observability-plane change | Not applicable | Removes our ability to verify any repair | Never automated |

### Hard constraints

Two rules should hold regardless of any risk score:

- **Never auto-remediate the observability plane.** No automated action may target the OpenTelemetry Collector, Prometheus, Jaeger, or log storage. Our environment evaluation already forbids injecting faults into these components. The same reasoning applies more strongly to repairs, because these are the components we need in order to verify that a repair worked.
- **One remediation at a time.** No overlapping automated actions while an earlier one is still being evaluated.

### Circuit breaker

No more than three automated actions within a fifteen-minute window. After that the system stops acting and escalates until a person resumes it manually. Narya uses a rate limit for the same purpose, though it does not publish a threshold, so this value is a starting point to be revised once we have experimental data.

### Speaker Notes

The first thing this section contributes is the action list itself. Our environment document defines what faults we inject, but nobody had written down what the system is allowed to do in response. You cannot gate actions that have not been enumerated.

The proposed split is deliberately conservative. Only the fully reversible, single-service actions run automatically at this stage. Anything that affects more than one service, or that we cannot cleanly undo, goes to a human.

The observability exclusion is the constraint I would argue hardest for. If our system restarts Prometheus during an incident, we lose the telemetry we need to understand both the incident and whether our repair helped. This should not be overridable by a confidence score, because a constraint a model can override when confident is not really a constraint.

The circuit breaker exists because our experiments inject one fault at a time. If the system is taking more than three actions in fifteen minutes, it is reacting to its own effects rather than to the injected fault.

On the risk inputs, six of the seven come from the Dai paper. Telemetry quality is ours. We added it because our whole pipeline depends on telemetry being complete, and acting on partial evidence is exactly the situation where an automated repair is most likely to be wrong.

---

# Slide 4: Evaluation, Gap, and Next Steps

## How We Will Measure Safety

### Proposed evaluation metrics

| Metric | What it measures | Can we compute it |
|---|---|---|
| False remediation rate | Share of executed repairs that were unnecessary or wrong | Yes, from injected-fault labels |
| Gate recall | Share of unsafe actions the gate blocked | Yes |
| Escalation rate | Share of incidents handed to a human | Yes |
| Repair success rate | Share of incidents actually resolved | Yes |
| Time to recovery | Time from detection to restored service | Yes, from fault start and stop times |

We should report false remediation rate and gate recall together. Reporting the first alone is misleading, because it can be driven to zero by escalating everything, which would make the system safe and useless at the same time.

### The gap we found

**No reproducible baseline exists for safety gating.** None of the three reviewed systems releases code or data.

This is different from the rest of our project. Our dataset evaluation could select SMD with published results. Our baseline selection could name CausalRCA and an exact table to reproduce. Neither is possible here.

The underlying reason is that these methods depend on data nobody publishes: histories of remediation actions with recorded outcomes, and rollback logs. Our fault-injection setup can generate exactly that, at small scale, because we control which fault was injected and can record what each repair did.

### Next steps

1. Confirm the proposed action list with the team.
2. Record every remediation attempt with the action taken, the injected fault, and the outcome.
3. Implement the two hard constraints first, before any risk scoring.
4. Add the circuit breaker.
5. Only then attempt learned risk scoring.
6. Report results as measurements of our own system, not as a reproduction of a published result.

### Speaker Notes

For evaluation, the metric I propose as primary is false remediation rate, which is the share of repairs that were wrong or unnecessary. Our fault injection gives us the ground truth to compute it, and the recording our environment document already requires is enough. We do not need extra instrumentation.

I want to be clear about the gap. Unlike the other parts of the project, I cannot propose a published baseline to reproduce, because no system in this area releases code or data. I think stating that plainly is stronger than presenting a benchmark that measures something else.

I am also not proposing a numeric target yet. Our dataset work could commit to an F1 of 0.85 because SMD has published results to compare against. There is no equivalent anchor here, so any number I picked now would be invented. I would set the target after our first round of fault experiments.

The practical order matters. The two hard constraints are simple rules that remove the worst outcomes, and they should be implemented before any scoring model. The learned parts come last.

### References

- Safe Remediation as Risk-Constrained Intervention Decision in Microservice Systems: https://arxiv.org/abs/2607.20005
- Narya, OSDI 2020: https://www.usenix.org/conference/osdi20/presentation/levy
- Gandalf, NSDI 2020: https://www.usenix.org/conference/nsdi20/presentation/li
- Full literature review: `docs/literature/safe-remediation/README.md`
