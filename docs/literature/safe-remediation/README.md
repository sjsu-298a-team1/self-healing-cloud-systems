# Literature Review: Safe Autonomous Remediation and Action-Risk Gating

This review is for Linear issue **298-16**. I wanted to understand how earlier work decides whether an automated repair action is safe enough to run without a person approving it first.

This question sits at the end of our pipeline. Our anomaly detector will flag a problem, and our root-cause model will name a service. At that point the system has to choose what to do about it, and that is where the risk appears. If the root-cause model ranks the wrong service, a repair aimed at that service does not fix the incident, and it adds a second disturbance while the first one is still active.

The core idea in this area is that the cost of an incorrect repair can be higher than the cost of doing nothing at all. A detector that is wrong produces a false alert. A remediation system that is wrong changes the running system during an incident.

Our own environment makes this concrete. In the OpenTelemetry Demo setup described in issue 298-12, some repairs are close to free. Turning off an injected feature flag restores the previous state immediately. Other repairs are not. Restarting a container makes the service unavailable for a short time. Changing a network policy can affect services we did not intend to touch, and it is harder to undo cleanly. A useful system should not treat these actions as if they carry the same risk.

## Remediation actions in our environment

Issue 298-12 lists the faults we can inject, but it does not list the actions our system would take to repair them. I have written that list here because a gating method needs an explicit set of actions before it can score them.

| Action | Reversible | Blast radius | Notes |
|---|---|---|---|
| Turn off a feature flag | Fully | One service | Direct undo for our injected faults |
| Restart a container | Yes, with short downtime | One service | Common first response |
| Scale replicas up | Yes | One service, extra resource cost | Suitable for CPU and latency faults |
| Roll back a deployment | Yes, if versions are kept | Service and its callers | Requires version history |
| Evict or drain a pod | Partly | Node level | Kubernetes phase only |
| Change a network policy | Difficult to undo cleanly | Possibly cluster wide | Highest risk in our set |

## Why I selected these papers

I chose the risk-constrained intervention paper by Dai et al., Narya, and Gandalf. These are not three versions of the same idea. Each one answers a different question that our system will have to answer.

The Dai paper asks **whether to act at all**. It treats safe remediation as a decision problem with an explicit risk budget.

Narya asks **which action to choose**. It runs in production and selects among several repair actions for predicted host failures.

Gandalf asks **when to stop**. It is a gate that decides whether an ongoing change should be allowed to continue or should be halted.

Together these cover the three decisions our system needs to make: whether to intervene, which action to use, and when to block or reverse an action that is going badly.

I also looked at MicroRemed, which is a benchmark for language-model-generated repair scripts. I did not include it as a main review because it measures whether a model can produce a working repair, not whether that repair is safe to run. I have kept it in the recommendation section because it is the only artifact in this area with code we could actually run.

I excluded a large amount of material that appears when searching for these terms. Much of what is written about action-risk gating, blast radius, and guardrails comes from vendor documentation and company blogs rather than peer-reviewed work. Those sources describe useful patterns, but they report no measurements and cannot be verified, so I have not cited them as evidence.

## What I verified

I read all three papers in full, including the published proceedings version of Gandalf and the extended technical report for Narya, and I checked whether code or data is available for each one. I did not run any implementation, and no implementation was available to run.

One result is worth stating at the start, because it changes what this review can conclude. **None of the three approaches offers a reproducible baseline.** Narya and Gandalf are production systems inside Microsoft Azure, and neither releases code or data. The Dai paper is recent and releases nothing. This is different from issue 298-9, where MicroRCA could be proposed as a baseline to reproduce.

This means our team cannot reproduce a published safety-gating result the way we can reproduce an anomaly-detection or root-cause result. I return to what we should do instead in the recommendation section.

## 1. Risk-Constrained Intervention Decision

**Paper:** Chengxiao Dai, Zhaokun Yan, Chenjun Lei, Qiao Li, and Luyan Zhang, "Safe Remediation as Risk-Constrained Intervention Decision in Microservice Systems," arXiv preprint arXiv:2607.20005, July 2026.
**Links:** [paper](https://arxiv.org/abs/2607.20005)

### How it works

This paper argues that most automated remediation work aims at the wrong question. Existing systems focus on generating a repair action, but the harder question is whether the system should intervene at all.

The authors model the problem as a Constrained Markov Decision Process. The policy maximises repair success subject to a hard limit on the false remediation rate, set as an operator-chosen threshold. This matters for us because it makes the safety budget an explicit setting rather than something buried inside a model.

Risk is decomposed into three parts, and each is computed separately:

- **Blast radius** spreads the influence of an action through the service dependency graph using a learned diffusion kernel, which estimates how far the effect of an action travels.
- **Reversibility** is a predicted probability that a rollback would succeed, trained on historical rollback logs. The risk contribution is one minus that probability.
- **Epistemic uncertainty** is measured as disagreement across an ensemble of five bootstrap-resampled outcome predictors, which flags states the model has not seen before.

The escalation gate is a contextual bandit rather than a fixed threshold. It takes on-call load, business criticality, incident severity, diagnosis confidence, and service centrality, and produces an escalation threshold that moves with conditions. The authors describe this as turning escalation from a binary failsafe into a bandwidth-aware control layer.

The policy is learned offline from historical incident logs, so it does not require experimenting on a live system.

### Experiment

The authors used the Train Ticket benchmark with 41 services on a three-node Kubernetes cluster. Faults were injected with Chaos Mesh across 11 categories aligned to the RCAEval taxonomy: CPU, memory, disk I/O, socket, network delay, packet loss, partition, pod kill, HTTP abort, clock skew, and DNS error.

This produced 8,320 decision records from 1,664 events, split 70/15/15 into training, validation, and test sets.

Baselines were a rule-based runbook, an LLM-based remediation approach, behaviour cloning, CQL, CPO, a vanilla CMDP, and three ablations.

### Results reported by the paper

| Method | Success | False remediation rate | Escalation % | Time to recovery (s) |
|---|---:|---:|---:|---:|
| Rule-Runbook | 0.761 | 0.183 | 0.0 | 138 |
| LLM-Remed | 0.724 | 0.214 | 0.0 | 154 |
| CQL | 0.778 | 0.138 | 49.5 | 146 |
| CPO | 0.776 | 0.132 | 28.4 | 131 |
| Proposed method | 0.786 | 0.112 | 36.5 | 126 |

The headline claim is a 39% reduction in false remediation rate against the runbook baseline, with repair success 2.5 points higher. At a matched escalation rate of roughly 34%, the method reports success of 0.784 and a false remediation rate of 0.114.

The escalation column is worth reading carefully. The two baselines that never escalate have the worst false remediation rates. The methods that do escalate get better safety results but push work onto on-call engineers. The contribution is not only accuracy, it is achieving a better safety result for less escalation.

### Repository check

The arXiv page links no code and no dataset, and the paper does not state whether either will be released. The Train Ticket benchmark and Chaos Mesh are both public, and the fault taxonomy follows RCAEval, so the environment could be rebuilt. The 8,320 decision records could not.

### Reproduction judgment

We cannot reproduce the reported numbers. There is no code, no data, and no released model.

What we can reuse is the framing. The three risk dimensions map directly onto the action table above, and the false remediation rate is a metric we could compute from our own fault labels.

The paper is also two months old and has not been through peer review. I would cite it as a design reference rather than as an established result.

**Difficulty for our team: reproduction not possible. Design reuse is low difficulty.**

## 2. Narya

**Paper:** Sebastien Levy, Randolph Yao, Youjiang Wu, Yingnong Dang, Peng Huang, Zheng Mu, Pu Zhao, Tarun Ramani, Naga Govindaraju, Xukun Li, Qingwei Lin, Gil Lapid Shafriri, and Murali Chintalapati, "Narya: Predictive and Adaptive Failure Mitigation to Avert Production Cloud VM Interruptions," USENIX Symposium on Operating Systems Design and Implementation (OSDI), 2020.
**Links:** [paper](https://www.usenix.org/conference/osdi20/presentation/levy) | [technical report](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/08/OSDI_tech_report.pdf)

### How it works

Narya runs inside Microsoft Azure. It predicts that a host is about to fail, then chooses a mitigation action before the failure happens.

Prediction uses two methods together. There are 51 hand-written rules based on hardware signals such as disk SMART attributes and CPU machine check errors. There is also a learned predictor, a gradient boosted tree using more than 2,000 engineered features drawn from over 100 time series, later extended with a deep model using spatial and temporal encoders. The prediction horizon is seven days.

The part that matters most for this review is the action set. Narya defines its actions explicitly, which is exactly the step missing from our own 298-12:

| Type | Actions |
|---|---|
| Primitive | Avoid, Mark Unallocatable, Live Migration, Service Healing, Soft Reboot, Human Investigate |
| Composite | UA-LM-HI, UA-SR, UA-LM-RH, Avoid-RH |
| Baseline | NoOp |

Two things stand out. First, **Human Investigate is an action inside the set**, not a separate escape hatch. Escalation is treated as one option among several, with its own cost. Second, the composite actions are ordered by decreasing priority, so the system holds a stated preference order rather than treating all repairs as equivalent.

Narya does not assume it knows which action is best. It runs A/B tests using production traffic to measure the real effect of each action, then moves to a multi-armed bandit to balance exploring new actions against using the one that has worked.

Section 6.4 of the paper is devoted to safeguards, and it is the most directly useful part of this review. Narya applies four separate mechanisms:

1. **Action overriding.** Actions carry a priority order. If the system tries to assign a node an action of lower priority than the one already applied, it skips it. Later predictions are often side effects of earlier ones, so the older decision is honoured.
2. **Safety constraints.** These are domain-specific rules that forbid particular actions in particular failure scenarios, regardless of what the learner recommends. Two examples are given. Soft reboot is prohibited when a rule flags hardware dysfunction with high confidence, because a reboot cannot help and causes a pause at best and VM reboots at worst. Service healing is not allowed to run on rules with low precision, because service healing has a strong effect on the interruption rate.
3. **A minimum observation count.** If the bandit has too little data it returns a premature flag, and the system falls back to the default action distribution rather than acting on a weak estimate.
4. **Minimum and maximum bounds on action probability.** The maximum bound limits how strongly the system can react to a high-cost signal. The minimum bound guarantees that some exploration continues. The paper reports that 10% exploration worked best when fewer than 100 nodes were flagged per day, and 5% above that.

A rate limit can also be set on any node of the mitigation policy tree to prevent excessive mitigation from causing capacity problems or cascading failures. That rate limit is a circuit breaker in the sense this review cares about.

The second mechanism deserves emphasis for our design. Narya ties **which actions are permitted to how precise the detecting rule is**. A low-precision detector is not allowed to trigger a high-impact repair. This links our gating design directly to the quality of the detector built in issue 298-8, and it means the two pillars cannot be designed independently.

### Experiment

Narya has run in production since June 2019, and the reported results cover 15 months of operation across Azure's fleet.

The main metric is the Annual Interruption Rate, defined as VM interruption count divided by total VM lifetime, scaled to 365 days and 100 VMs.

### Results reported by the paper

| Measure | Reported value |
|---|---:|
| AIR improvement over static strategy, March 2020 | 26.2% |
| Oracle optimal saving | 35.4% |
| Regret against optimal | 9.2% |
| Failure prediction precision | 79.49% |
| Failure prediction recall | 50.7% |
| False positive rate | 20.51% |
| Median ML prediction lead time | 2.44 days |
| Bandit over A/B testing, Feb to Mar 2020 | 14.4% fewer VM interruptions |

Two results are more useful to us than the headline number.

The safeguards section reports what happens without them. In one simulation the bandit without safeguards converged, with probability above 0.95, onto a single action in 27% of cases, and 19% of those converged onto the worst available action. A learning system left unconstrained confidently chose the wrong repair.

The convergence table shows that A/B testing took a median of 29.5 days to reach a conclusion, with a maximum of 140 days, and that two experiments never converged at all. Learning which repair is safe is slow even at Azure's scale.

### Repository check

No code and no data are released. This is a production system inside Azure and the paper offers no artifact.

Narya also runs as part of the Gandalf suite, and the two papers share six authors. They are components of one platform rather than independent results, which is worth stating when comparing them.

### Reproduction judgment

Reproduction is not possible. There is no artifact, and the result depends on a fleet of millions of VMs that we cannot approximate.

The transferable parts are the explicit action table, escalation treated as a costed action, and the rate limit as a circuit breaker. The safeguards result is the strongest single piece of evidence in this review for why gating is needed at all.

**Difficulty for our team: reproduction not possible. Design reuse is low difficulty.**

## 3. Gandalf

**Paper:** Ze Li, Qian Cheng, Ken Hsieh, Yingnong Dang, Peng Huang, Pankaj Singh, Xinsheng Yang, Qingwei Lin, Youjiang Wu, Sebastien Levy, and Murali Chintalapati, "Gandalf: An Intelligent, End-To-End Analytics Service for Safe Deployment in Large-Scale Cloud Infrastructure," USENIX Symposium on Networked Systems Design and Implementation (NSDI), 2020.
**Links:** [paper](https://www.usenix.org/conference/nsdi20/presentation/li)

### How it works

Gandalf decides whether a software rollout in Azure should continue or be stopped. It is a gate rather than a repair system, which is why I included it. Our system needs the same ability to halt an action that is going badly, not only to choose a reasonable action at the start.

Gandalf watches fault signals across the fleet and correlates them against every ongoing rollout. Log messages are clustered into fault signatures, and Holt-Winters forecasting over 30 days of history sets the expected baseline, so detection keeps working while the system itself keeps changing.

The correlation step uses ensemble voting across several time windows. A fault appearing after a component was deployed votes that the deployment caused it. A fault already present before the deployment vetoes that conclusion. Exponential decay weights closer and more recent events more heavily. The veto rule is the interesting part: evidence that something was already broken actively cancels the blame rather than merely failing to support it.

A classifier trained on historical deployment outcomes then judges the scope of impact, counting affected clusters, nodes, and customers, and returns a go or no-go decision. That decision is passed to Azure's deployment engine, which can halt the rollout.

The system runs two paths at once. A fast path decides within about five minutes using a one-hour window. A slower batch path reruns the analysis over three hours to catch problems that appear late.

### Experiment

Gandalf ran in production in Azure for more than 18 months, serving both data-plane and control-plane components, and the reported evaluation covers an eight-month window from January to November 2018. It processes on average 270,000 platform events daily, 770,000 on peak days, and 600 million API calls per day in the control plane, across more than 2,000 fault types, analysing more than 20TB per day.

Azure enforces a staged deployment policy, so a component update must pass through Stage, Canary, and Pilot environments before reaching production. Gandalf sits across those stages rather than at a single checkpoint.

### Results reported by the paper

| Component | Precision | Recall |
|---|---:|---:|
| Data plane | 92.4% | 100% |
| Control plane | 94.9% | 99.8% |

In the data plane, Gandalf captured 155 critical failures at the early stage of rollouts. For the control plane it made decisions on more than 1,200 region-level deployments, filed 39 incidents of which only 2 were false alarms, and missed 2 true issues. One of those misses was caused by incomplete logs, and the other by a component throwing generic timeout exceptions instead of specific errors.

Recall is the number to notice. Gandalf reports that no high-impact Azure Compute outage in the period was caused by a bad rollout it failed to stop. A gate should be judged first on what it fails to catch and only second on how often it stops something unnecessarily.

The paper also reports the number most relevant to blast radius: **99.2% of bad rollouts were blocked before reaching production**, with the remaining 0.8% blocked early in production. The authors state directly that this is how Gandalf limits the blast radius of a bad change. Containing an unsafe action early is treated as the goal, not preventing it perfectly.

The ablation results show which parts of the design carry the weight:

| Component removed | Effect on precision | Effect on recall |
|---|---|---|
| Spatial correlation | Precision is 77% higher with it | Also improves recall |
| Time decay | Precision drops 58.8% | Recall drops 12.7% |
| Veto mechanism | Precision drops 8.7% | Unchanged |

The veto contributes least, but it contributes to precision only and costs nothing in recall, which is the trade any gate should want.

Deployment times across the fleet were cut by more than half after Gandalf was introduced, which is evidence that a good gate can let a system move faster rather than slower.

Two points from the paper's lessons section are worth carrying into our own design. First, the authors argue that the precision and recall balance should be set per component rather than fixed globally: teams with limited engineering capacity prefer few false alarms, while teams running mission-critical services treat 100% recall as a strict requirement. Second, they report that a gate which cannot explain itself does not get adopted, even when its decisions are accurate, so Gandalf surfaces the evidence behind every decision. Explainability is presented as an adoption requirement rather than a nice addition.

### Repository check

No code and no data are released. As with Narya, this is an internal Azure system, and the paper offers no artifact. The figures above are taken from the published NSDI proceedings version, which is freely available through USENIX open access.

### Reproduction judgment

Reproduction is not possible, for the same reasons as Narya.

What transfers is the gate pattern itself, the veto rule for evidence that predates the action, the decision to treat recall as the primary metric, and the requirement that the gate explain its decisions.

**Difficulty for our team: reproduction not possible. Design reuse is low to medium difficulty, because the correlation logic assumes a fleet large enough for statistical comparison.**
## Comparison

| Question | Dai et al. | Narya | Gandalf |
|---|---|---|---|
| Venue and year | arXiv preprint, 2026 | OSDI 2020 | NSDI 2020 |
| Peer reviewed | No | Yes | Yes |
| Which decision does it make | Whether to intervene | Which action to take | Whether to stop an action |
| Main input signals | Dependency graph, rollback logs, ensemble disagreement, on-call context | Hardware and OS telemetry, control-plane operation signals | Log-derived fault signatures, deployment records |
| How risk is modelled | Explicit three-part score inside a constrained MDP | Learned action cost from production experiments | Correlation of faults to rollouts, then impact classification |
| Explicit action set | No, actions are abstract | Yes, six primitive and four composite | Not applicable, the action is go or stop |
| Type of gate | Adaptive threshold from a contextual bandit | Rate limit on the policy tree, plus safety constraints on exploration | Binary go or no-go from a trained classifier |
| How escalation is handled | Contextual bandit sets the escalation threshold | Human Investigate is an action in the set | Rollout is halted and handed to engineers |
| Primary reported metric | False remediation rate | Annual Interruption Rate | Precision and recall |
| Evaluated on | Train Ticket, 41 services, Chaos Mesh | Azure production fleet | Azure production fleet |
| Public code | None linked | None | None |
| Public data | None linked | None | None |
| License detected | Not applicable | Not applicable | Not applicable |
| Reproduction difficulty | Not possible, no artifact | Not possible, requires a fleet | Not possible, requires a fleet |

The three systems are not competitors and their numbers cannot be compared. They were measured on different systems, over different time spans, against different baselines, using metrics that do not convert into one another. What they share is a common shape: score the risk of an action, compare it to a threshold, and route the action to execution or to a human.

## Safety metrics found in the reviewed work

The issue asks for safety-related evaluation metrics. I have gathered them here rather than leaving them inside each paper section, and marked whether our team could compute each one in the OpenTelemetry Demo environment.

| Metric | What it measures | Source | Can we compute it |
|---|---|---|---|
| False remediation rate | Share of executed repairs that were unnecessary or wrong | Dai et al. | Yes, using our injected-fault labels |
| Repair success rate | Share of incidents actually resolved by the chosen action | Dai et al. | Yes |
| Escalation rate | Share of incidents handed to a human | Dai et al. | Yes |
| Time to recovery | Time from detection to restored service | Dai et al. | Yes, from fault start and stop times |
| Gate precision | Share of blocked actions that really were unsafe | Gandalf | Yes |
| Gate recall | Share of unsafe actions the gate successfully blocked | Gandalf | Yes |
| Annual Interruption Rate | Customer-facing interruption rate across a fleet | Narya | No, requires a production fleet |
| Regret against optimal | Gap between chosen actions and the best possible action | Narya | Partly, only where we know the correct repair |

The four metrics from Dai et al. are the most useful to us because our fault injection gives us ground truth for each one. Akhilesh's 298-12 already requires that we record the affected service, fault type, start time, and stop time for every experiment. That same record is what makes these metrics computable, so no extra instrumentation is needed.

Gate recall deserves emphasis. Gandalf reports 100% recall on data-plane rollouts, and the paper treats that as the number that matters. A gate that occasionally blocks a safe action is inconvenient. A gate that lets through an unsafe one is the failure the gate exists to prevent.

## Gaps in the literature

Six observations that shape what our team should attempt.

**There is no reproducible baseline.** None of the three papers releases code or data. This is the clearest difference between this area and the other pillars of our project. Anomaly detection has SMD, and root-cause localisation has RCAEval and several public implementations. Safety gating has neither.

The contrast is concrete rather than theoretical. Issue 298-13 was able to select CausalRCA as a published baseline and name the exact table and numbers to reproduce, because that paper ships code and experimental data. No paper in this review makes that possible.

**There is no shared benchmark.** Each paper evaluates on its own system: Train Ticket in one case, the Azure fleet in the other two. Because no common testbed exists, no two results in this area can be compared directly. Any number we produce will be a number about our own system and should be described that way.

**Two of the three papers come from the same group.** Narya and Gandalf share six authors, and Narya runs as part of the Gandalf suite. They are components of one platform at one company, not independent confirmations of a shared finding. Our review covers three systems but effectively two research programmes.

**Most writing in this area is not research.** Searching for action-risk gating, blast radius, or guardrails returns mainly vendor documentation and company blogs. Those sources describe the same patterns the papers do, but they report no measurements and cannot be checked, so I did not treat them as evidence.

**Metrics are not settled.** Each paper measures something different, and only the newest and least established one uses false remediation rate. If we adopt that metric we are following a single unreviewed preprint, and we should say so rather than presenting it as standard practice.

**The missing resource is labelled action outcomes.** The deeper reason no baseline exists is that these methods need data nobody publishes: histories of remediation actions with recorded outcomes, and rollback logs showing which repairs could be undone. Reversibility in Dai et al. is trained on exactly this. Our fault-injection setup can generate it, at small scale, because we control which fault was injected and can record what each repair did.

## Recommendation for our team

This section takes a position on each design question rather than leaving it open. Every recommendation below is a proposal for the team to accept or change, and I have said where a value is chosen rather than derived from evidence.

### What I recommend we adopt

We should adopt the **risk-scoring structure from Dai et al.**, because it is the only reviewed work that separates risk into parts we can actually compute in our environment, and because it makes the safety budget an explicit setting.

We should adopt **Narya's practice of writing the action set down explicitly**, including escalation as an action with its own cost rather than as an exception.

We should adopt **Gandalf's ordering of metrics**, treating gate recall as primary and gate precision as secondary, and **Gandalf's requirement that the gate explain itself**. That paper reports that an accurate but unexplainable gate was not trusted or adopted. Every automated decision our system makes should record which signals triggered it, which action was chosen, and why the action was permitted.

We should treat all three as design references. We should not claim to reproduce any of them.

### Proposed action policy

Applying the three risk dimensions to the actions available in our environment:

| Action | Reversibility | Blast radius | Proposed handling |
|---|---|---|---|
| Turn off a feature flag | High | One service | Automatic |
| Restart a container | High | One service | Automatic |
| Scale replicas up | High | One service | Automatic above a confidence threshold |
| Roll back a deployment | Medium | Service and callers | Escalate |
| Evict or drain a pod | Low | Node | Escalate |
| Change a network policy | Low | Possibly cluster wide | Never automated at this stage |

I recommend we adopt this split, with one addition taken from Narya. Narya does not permit a high-impact action to be triggered by a low-precision detection rule. We should apply the same principle: an action may only run automatically if the detector that triggered it meets a precision bar we have measured, not merely assumed. This makes the gating design dependent on the detector produced in issue 298-8, and the two should be specified together rather than separately.

Until that precision bar is measured, the conservative reading of the table above should apply, meaning only the first two actions run without a human.

### Proposed hard constraints

Two constraints should hold regardless of any score, both derived from Akhilesh's 298-12:

1. **Never remediate the observability plane.** No automated action may target the OpenTelemetry Collector, Prometheus, Jaeger, or log storage. His document already forbids injecting faults into these components because losing telemetry means losing the ability to understand the incident. The same reasoning applies more strongly to repairs, since we also need these components to verify that a repair worked.
2. **One remediation at a time.** No overlapping automated actions while an earlier one is still being evaluated. This follows his rule of testing one fault at a time.

I recommend the observability-plane exclusion be **absolute for automated actions and not overridable by the system under any score**. It should not restrict people. An engineer can still restart Prometheus by hand. The rule is that our system may never choose to do so, because the components it would be repairing are the ones it needs in order to tell whether the repair worked.

This follows Narya's use of safety constraints, which forbid specific actions in specific scenarios regardless of what the learned policy recommends. A constraint that a model can override when it is confident is not a constraint.

### Proposed circuit breaker

Narya applies a rate limit to prevent excessive mitigation causing cascading failures. We should do the same, but the paper does not give a number we can copy.

I recommend **no more than three automated actions within a fifteen-minute window**, after which the system stops acting and escalates until a person explicitly resumes it. The resume must be manual, because an automatic reset would defeat the purpose of tripping.

The number is a starting value rather than a derived one, and I want to be clear that no paper supports it. Narya sets rate limits but does not publish its thresholds. Three actions in fifteen minutes is chosen because our fault experiments inject one fault at a time, so more than three repairs in that window means the system is reacting to its own effects rather than to the injected fault. We should revise this once we have run enough experiments to see the real distribution.

Narya offers a second mechanism worth copying alongside the rate limit. When its learner has too few observations it raises a premature flag and falls back to default behaviour instead of acting on a weak estimate. Our gate should behave the same way when it has not seen a similar incident before.

### Proposed metric

I recommend we report **two metrics together**, because one of them alone can be gamed.

**False remediation rate** is the primary safety metric, following Dai et al. It is the share of executed repairs that were unnecessary or wrong, and our injected-fault labels give us the ground truth to compute it.

**Gate recall** is reported alongside it, following Gandalf. This is the share of unsafe actions the gate actually blocked. It matters because false remediation rate can be driven to zero by escalating everything, which would make our system useless rather than safe. Reporting escalation rate as well keeps that visible.

I recommend we **do not set a numeric target yet**. Issue 298-11 could commit to F1 at or above 0.85 because SMD has published results to anchor against. Nothing equivalent exists here, so any number we picked now would be invented. We should set the target after our first round of fault experiments, and say in the Checkpoint materials that this is why it is not yet fixed.

One further point from Gandalf: the authors argue the precision and recall balance should be chosen per component rather than globally. For us that means the bar for auto-remediating the checkout service need not equal the bar for a background worker.

### Position on baselines

I recommend we **state plainly that no reproducible baseline exists for safety gating**, and that our results will be measurements of our own system against our own recorded ground truth rather than a reproduction of a published number.

The alternative would be to propose MicroRemed as a reproduction target, since it is the only artifact in this area with public code. I do not recommend it. MicroRemed measures whether a language model can produce a repair script that works. It does not measure whether the repair was safe to attempt, which is the question this pillar exists to answer. Presenting it as our baseline would look rigorous while testing the wrong thing.

MicroRemed should be noted as a possible later comparison for the remediation-generation component in issue 298-21, where it does fit.

This position should appear in the Checkpoint 1 materials rather than being left out. A stated and explained gap is a stronger result than a mismatched benchmark, and it is also the honest description of the field.

### Practical order

1. Confirm the action list above with the team, since 298-12 does not define it.
2. Record every remediation attempt with the action taken, the injected fault, and the outcome. This is the data the reviewed methods depend on and none of them publish.
3. Implement the two hard constraints first, before any scoring. They are simple rules and they remove the worst outcomes.
4. Add the rate limit next.
5. Only after that, attempt any learned risk scoring.
6. Report our results as measurements of our own system, not as a reproduction.

This recommendation is preliminary. It is based on reading the papers and checking for released artifacts, not on any implementation or experiment.

## Sources

- [Safe Remediation as Risk-Constrained Intervention Decision in Microservice Systems](https://arxiv.org/abs/2607.20005)
- [Narya, OSDI 2020](https://www.usenix.org/conference/osdi20/presentation/levy)
- [Narya technical report](https://www.microsoft.com/en-us/research/wp-content/uploads/2020/08/OSDI_tech_report.pdf)
- [Gandalf, NSDI 2020](https://www.usenix.org/conference/nsdi20/presentation/li)
- [MicroRemed benchmark](https://arxiv.org/abs/2511.01166)
- [MicroRemed repository](https://github.com/LLM4AIOps/MicroRemed)
- Internal: `docs/infra/environment-evaluation/README.md`, issue 298-12
- Internal: dataset and benchmark evaluation for issue 298-11, currently in an open pull request
