# Literature Review: Cloud and Microservice Anomaly Detection

## 1. MicroRCA Literature Review

### Paper citation

Li Wu, Johan Tordsson, Erik Elmroth, and Odej Kao, “MicroRCA: Root Cause Localization of Performance Issues in Microservices,” Proceedings of the IEEE/IFIP Network Operations and Management Symposium, 2020.

Paper: https://ieeexplore.ieee.org/document/9110353
Open paper: https://inria.hal.science/hal-02441640/document
Code repository: https://github.com/elastisys/MicroRCA
Sock Shop benchmark: https://microservices-demo.github.io/

### Problem addressed

MicroRCA addresses the problem of locating the root cause of performance issues in containerized microservice applications. Performance problems can propagate across multiple services and hosts, producing several symptoms and false alarms. This makes it difficult to identify the service or infrastructure resource that originally caused the problem.

The paper focuses on application-agnostic root-cause localization using application-level and system-level metrics without requiring source-code instrumentation or distributed tracing.

MicroRCA includes an anomaly-detection step based on abnormal service response times, but its primary task is root-cause localization rather than standalone multivariate anomaly detection.

### Model and algorithm

MicroRCA uses the following processing pipeline:

1. Detect abnormal service response times using distance-based online BIRCH clustering.
2. Construct an attributed graph containing service nodes and host nodes.
3. Represent service-to-service communication and service-to-host placement relationships as graph edges.
4. Extract an anomalous subgraph containing anomalous services and related neighboring services and hosts.
5. Assign edge weights using anomaly confidence and Pearson correlation.
6. Calculate service anomaly scores using response-time and resource-utilization correlations.
7. Apply Personalized PageRank to rank the most likely faulty services.

The main components and workflow are shown in Figure 1, and the detailed root-cause-localization procedure is shown in Figure 2.

### Input telemetry and features

MicroRCA uses:

* Response times between communicating microservices.
* Container CPU utilization.
* Container memory utilization.
* Host CPU utilization.
* Host memory utilization.
* Host I/O utilization.
* Network utilization, represented partly through total sent bytes.
* Service-to-service communication relationships.
* Service-to-host deployment relationships.

Prometheus collected the metrics at five-second intervals. The system uses slow service response time as the definition of an anomaly.

### Dataset and benchmark

The authors evaluated MicroRCA using the Sock Shop microservice benchmark deployed on Kubernetes in Google Cloud Engine.

The testbed included:

* One Kubernetes master node.
* Four worker nodes.
* One separate workload-generator machine.
* Istio service mesh.
* Prometheus monitoring.
* Node Exporter for host-level metrics.
* Locust for workload generation.

The workload generator simulated approximately 500 users and approximately 600 queries per second. Request rates for the services are reported in Table II.

The evaluated fault types were:

* Network latency.
* CPU hog.
* Memory leak.

The faults were injected into different Sock Shop microservices. The paper reports an evaluation involving 95 test scenarios.

The detailed injected fault configurations are reported in Table III.

### Evaluation metrics

The paper evaluates root-cause localization using:

* PR@1: the proportion of cases in which the correct root cause is ranked first.
* PR@3: the proportion of cases in which the correct root cause appears within the top three results.
* Mean Average Precision (MAP): an aggregate measure of ranking quality across possible root-cause positions.
* F1-score: used to analyze the relationship between anomaly-detection quality and root-cause rank.

These metrics are defined in the evaluation section of the paper.

### Numerical results

The main MicroRCA results are:

* Overall PR@1: 0.89.
* Overall PR@3: 1.00.
* Overall MAP: 0.97.

For individual fault categories, the paper reports:

| Fault type      | PR@1 | PR@3 |  MAP |
| --------------- | ---: | ---: | ---: |
| Network latency | 0.89 | 1.00 | 0.97 |
| CPU hog         | 0.90 | 1.00 | 0.97 |
| Memory leak     | 0.90 | 1.00 | 0.98 |

The complete per-service and per-fault results are reported in Table IV.

The comparison against Random Selection, MonitorRank, and Microscope is reported in Table V. Overall results from Table V are:

| Method           | PR@1 | PR@3 |  MAP |
| ---------------- | ---: | ---: | ---: |
| Random Selection | 0.21 | 0.46 | 0.58 |
| MonitorRank      | 0.41 | 0.65 | 0.73 |
| Microscope       | 0.79 | 0.86 | 0.85 |
| MicroRCA         | 0.89 | 1.00 | 0.97 |

The authors report that MicroRCA improves overall PR@1 by approximately 13.3% over Microscope and improves MAP by approximately 14.7% over Microscope.

### Exact tables and figures containing important results

* Figure 1: Overview of MicroRCA components and workflow.
* Figure 2: MicroRCA root-cause-localization procedures.
* Table I: Hardware and software configuration used in the experiments.
* Table II: Request rates sent to the microservices.
* Table III: Detailed injected fault configurations.
* Figure 3: PR@1 and MAP results for different faults and microservices.
* Table IV: Detailed MicroRCA performance by fault type and microservice.
* Table V: Performance comparison against baseline algorithms.
* Table VI: MicroRCA execution and resource overhead.
* Figure 4: Comparison of PR@1, PR@3, and MAP for different microservices.
* Figure 5: Root-cause rank against anomaly-detection F1-score.
* Figure 6: Performance against anomaly-detection confidence parameter alpha.
* Figure 7: Performance against the anomaly-detection threshold.

### Code availability

The MicroRCA implementation is publicly available:

https://github.com/elastisys/MicroRCA

The repository contains:

* Python implementation files.
* An online version of the algorithm.
* Sock Shop deployment files.
* Example CSV input files.

The repository does not clearly contain the complete dataset for all 95 experimental scenarios.

The repository does not appear to contain a clearly detected software license. This should be considered before directly reusing code in the final project.

### Dataset availability

The Sock Shop application is publicly available, and the application can be redeployed using Kubernetes.

However, the complete processed telemetry and labels for all 95 experimental cases are not clearly available in the MicroRCA repository. The repository includes example CSV files, but reproducing the complete evaluation would likely require redeploying Sock Shop, collecting new telemetry, and injecting the faults again.

### Compute requirements

The experimental hardware and software configuration is reported in Table I.

The reported setup included:

* One master node with 1 vCPU and 3.75 GB RAM.
* Four worker nodes with 4 vCPUs and 15 GB RAM each.
* One workload-generator machine with 6 vCPUs and 12 GB RAM.
* Kubernetes 1.14.1.
* Istio 1.1.5.
* Prometheus 2.3.1.
* Node Exporter v0.15.2.
* Container-Optimized OS for the cluster nodes.
* Ubuntu 18.04.2 LTS for the workload generator.

The reported MicroRCA overhead is shown in Table VI:

* Data collection: 0.6 vCPU and 1511 MB RAM.
* Anomaly detection: approximately 0.01 seconds using eight CPU cores.
* Attributed graph construction: approximately 3.3 seconds using eight CPU cores.
* Root-cause localization: approximately 0.03 seconds using eight CPU cores.

The algorithm itself has low computational cost. The main infrastructure cost comes from continuously collecting service, container, and host metrics.

### Reproduction difficulty

Overall reproduction difficulty: Medium.

Running the included example may be feasible on a local machine after resolving the environment and input-format requirements. Reproducing the complete paper evaluation is more difficult because:

* The full 95-case dataset is not clearly included.
* The repository does not pin all dependency versions.
* The implementation uses older pandas APIs, including `DataFrame.iteritems()`.
* The code expects specific CSV filenames and column names.
* Sock Shop and Kubernetes must be redeployed to recreate the original testbed.
* New telemetry must be collected at the appropriate time interval.
* Fault injection must be repeated consistently.

A realistic reproduction strategy would be to run the algorithm on the included example data first, then reproduce one controlled CPU-hog or latency experiment using a newly deployed Sock Shop environment.

### Strengths

* Designed specifically for containerized microservice environments.
* Uses both application-level and infrastructure-level telemetry.
* Does not require application source-code instrumentation.
* Includes both service-to-service and service-to-host relationships.
* Can identify root causes that are not obvious from front-end service symptoms.
* Uses an unsupervised BIRCH anomaly-detection component.
* Uses lightweight graph construction and Personalized PageRank.
* Reports strong PR@1, PR@3, and MAP results.
* Suitable for real-time or near-real-time diagnosis given the reported execution times.

### Limitations

* The primary objective is root-cause localization, not standalone anomaly detection.
* Evaluation uses one benchmark application and three injected fault types.
* Results may not transfer directly to OpenTelemetry Demo or real production systems.
* The full experimental dataset is not clearly available.
* Reproduction requires redeploying the benchmark and collecting new telemetry.
* The implementation depends on older libraries and outdated APIs.
* Pearson correlation does not necessarily establish true causal relationships.
* Performance depends on the quality of the initial anomaly-detection threshold and anomaly confidence parameter.
* The approach may be less effective when faults do not produce increased service response times.
* The repository does not clearly provide a software license.

### Relevance to the 298A project

MicroRCA is relevant as a lightweight and interpretable AIOps reference for service-level root-cause localization. Its use of response-time, resource-utilization, and service-topology information aligns with cloud and microservice telemetry.

It is not the strongest candidate as the primary anomaly-detection model because the anomaly-detection component is relatively simple and the paper’s main evaluation focuses on ranking root causes. It may be useful as:

* A lightweight rule-based or graph-based baseline.
* A post-anomaly root-cause-localization component.
* A conceptual reference for combining telemetry correlations with service topology.

The reported results should not be compared directly with Eadro or CausalRCA without evaluating all approaches on the same OpenTelemetry dataset, fault scenarios, labels, and metrics.

### Preliminary recommendation

MicroRCA should be retained as a relevant cloud/microservice AIOps paper and lightweight root-cause-localization baseline. It should not be selected as the main 298A anomaly-detection model unless the project scope explicitly includes root-cause localization and the team is willing to recreate the missing benchmark data.

### Completion checklist

* [x] Problem addressed documented.
* [x] Model and algorithm documented.
* [x] Input telemetry and features documented.
* [x] Dataset and benchmark documented.
* [x] Evaluation metrics documented.
* [x] Numerical results documented.
* [x] Exact paper table and figure references documented.
* [x] Code link documented.
* [x] Dataset availability assessed.
* [x] Compute requirements documented.
* [x] Reproduction difficulty assessed.
* [x] Strengths and limitations documented.
* [x] Findings added to the project literature-review Markdown file.
* [x] Changes committed to GitHub.
* [x] GitHub commit or pull request linked to the parent Linear issue.

## 4. Cross-Paper Comparison

The three papers address related but different AIOps problems. MicroRCA and CausalRCA primarily focus on root-cause localization, while Eadro jointly performs anomaly detection and root-cause localization. Therefore, their numerical results should not be interpreted as a direct leaderboard because they use different benchmarks, fault types, telemetry sources, labels, and evaluation metrics.

| Criterion | MicroRCA | Eadro | CausalRCA |
|---|---|---|---|
| Primary task | Root-cause localization with anomaly detection | Joint anomaly detection and root-cause localization | Coarse- and fine-grained root-cause localization |
| Main telemetry | Service response time, container metrics, and host metrics | Logs, KPIs, traces, and service dependencies | Service latency and resource metrics |
| Model type | BIRCH, attributed graph, correlation weighting, and Personalized PageRank | Hawkes process, dilated causal convolution, gated fusion, GAT, and joint learning | Gradient-based causal graph learning and PageRank |
| Supervision | Unsupervised anomaly detection; fault labels used for evaluation | Supervised anomaly detection and localization | Fault scenarios used for evaluation; no standalone anomaly classifier |
| Anomaly-detection result | Primarily evaluated through localization metrics | TrainTicket F1 = 0.989; SocialNetwork F1 = 0.986 | Not primarily evaluated as a binary anomaly detector |
| Localization result | PR@1 = 0.89, PR@3 = 1.00, MAP = 0.97 | HR@1 = 0.982, HR@5 = 0.990, NDCG@5 = 0.989 | Coarse AC@1 = 0.2000, AC@3 = 0.5749, Avg@5 = 0.5815; fine-grained AC@1 = 0.2476, AC@3 = 0.7190, Avg@5 = 0.6681 |
| Benchmark | Sock Shop on Kubernetes | TrainTicket and SocialNetwork | Sock Shop on Kubernetes |
| Multi-source telemetry | No; primarily metrics | Yes; logs, KPIs, and traces | No; metric-only |
| Public code | Yes | Yes | Yes |
| Public dataset | Complete dataset is not clearly available | Dataset linked through Zenodo | Code and fault data available |
| Compute requirements | Relatively lightweight | NVIDIA GTX 1080, batch size 256, 50 epochs | Three-worker Kubernetes testbed, 1,000 epochs |
| Reproduction difficulty | Medium | High | Medium to High |
| Interpretability | High | Moderate | Moderate to High |
| Main strength | Lightweight graph-based diagnosis | Comprehensive multi-source troubleshooting | Reproducible metric-level causal baseline |
| Main limitation | Limited anomaly-detection sophistication | Complex supervised pipeline | Primarily localization-focused |
| Fit for 298A | Lightweight RCA reference | Strongest long-term architecture | Practical published baseline |

### Comparative Interpretation

MicroRCA is the simplest approach to understand and deploy. It uses abnormal service response times and combines service and host information in an attributed graph. Its low computational cost makes it attractive for real-time monitoring. However, its evaluation focuses mainly on root-cause ranking, and the complete experimental dataset is not clearly available.

Eadro is the most comprehensive approach. It directly addresses both anomaly detection and root-cause localization while combining logs, KPIs, traces, and inter-service dependencies. Its strong F1 scores and ablation study make it highly relevant to cloud and microservice AIOps. However, Eadro requires synchronized multi-source telemetry, labeled fault windows, a GPU-based environment, and substantial preprocessing.

CausalRCA is a metric-only causal approach. It produces interpretable ranked root-cause metrics and has a more complete repository containing code and fault data. This makes it a realistic candidate for a focused published-baseline reproduction. However, it is not a complete anomaly-detection solution and does not use logs or traces.

### Comparison Limitations

The reported scores cannot be compared directly because:

- MicroRCA uses PR@1, PR@3, and MAP.
- Eadro uses F1, precision, recall, HR@k, and NDCG@k.
- CausalRCA uses AC@k and Avg@k.
- The papers use different microservice systems.
- The fault injection procedures and durations are different.
- The observation windows and labels are different.
- The telemetry sources are different.
- The evaluation tasks are not identical.

A fair comparison would require running the selected approaches on the same OpenTelemetry dataset, using the same anomaly windows, ground-truth labels, fault scenarios, and evaluation metrics.

## 5. Recommendation for the 298A Project

### Recommended First-Model Direction

The recommended first-model direction is a staged, metric-first approach inspired by MicroRCA, CausalRCA, and Eadro:

1. Begin with a multivariate metric-based anomaly detector using service latency, CPU, memory, disk, and network measurements.
2. Establish reliable time-window labels.
3. Evaluate anomaly detection using precision, recall, F1-score, and false-alarm rate.
4. Add service-dependency information for anomaly propagation and root-cause ranking.
5. Add logs and traces after the metric pipeline is stable.
6. Progress toward an Eadro-inspired multi-source model if synchronized logs, metrics, traces, and labels are available.

This direction is appropriate because it matches the telemetry that can realistically be collected from a cloud or OpenTelemetry-based environment while keeping the first implementation manageable.

### Most Promising Overall Approach

Eadro is the most promising overall approach for the long-term 298A system because:

- It directly includes anomaly detection.
- It jointly performs detection and root-cause localization.
- It combines logs, metrics, and traces.
- It models temporal behavior and inter-service dependencies.
- It provides strong anomaly-detection and localization results.
- Its ablation study demonstrates the value of multiple telemetry sources.
- It aligns closely with automated cloud troubleshooting and self-healing.

However, Eadro should be treated as a target architecture or later-stage model if the team does not yet have synchronized labeled multi-source telemetry.

### Most Feasible First Implementation

A metric-first approach is the most feasible initial implementation.

MicroRCA contributes a lightweight anomaly-detection and graph-localization design, while CausalRCA contributes causal metric relationships and metric-level ranking. A practical first version could:

- Detect anomalies from multivariate service and resource metrics.
- Use service latency as a high-level symptom signal.
- Use CPU, memory, disk, and network metrics as supporting features.
- Represent service dependencies using the available service topology.
- Rank possible root causes using correlation, causal structure, or graph-based scores.

This approach reduces data and compute requirements while leaving a clear path toward incorporating logs and traces later.

### Recommended Published Baseline

CausalRCA is the strongest candidate for the separately reproduced published baseline because:

- The repository contains implementation code and experimental data.
- The paper provides coarse-grained and fine-grained localization experiments.
- The method uses metric telemetry that is easier to collect and synchronize.
- Its causal graph and PageRank procedure are interpretable.
- It can be tested using a focused experiment before attempting the full paper reproduction.
- Its configuration and evaluation metrics are documented clearly.

The reproduction should begin with one coarse-grained Sock Shop experiment before attempting all anomaly types and fine-grained metric localization.

### Role of Each Paper

- **Eadro:** Long-term multi-source anomaly-detection and troubleshooting architecture.
- **CausalRCA:** Published metric-level causal baseline for focused reproduction.
- **MicroRCA:** Lightweight graph-based reference and possible post-detection localization component.

### Final Recommendation

The team should not immediately attempt to reproduce Eadro in full because its multi-source preprocessing, supervised labels, old dependencies, and neural architecture create substantial project risk.

The recommended strategy is:

1. Build and evaluate a metric-first multivariate anomaly-detection pipeline.
2. Use CausalRCA as the focused published baseline for metric-level root-cause localization.
3. Use MicroRCA as a lightweight graph-based comparison method.
4. Extend the system toward an Eadro-inspired architecture after reliable synchronized logs, metrics, traces, and labels are available.
5. Evaluate all selected approaches on the same project telemetry and fault scenarios whenever possible.

This strategy balances feasibility, research relevance, reproducibility, and alignment with the 298A objective of automated cloud incident response and self-healing.

### Project Limitations and Future Work

The recommendation is based on published experiments using controlled benchmark systems. Additional work is needed to determine how well these approaches transfer to the target project environment.

Future evaluation should investigate:

- OpenTelemetry Demo or another representative cloud-native benchmark.
- Unseen fault types.
- Naturally occurring anomalies.
- Missing or noisy telemetry.
- Class imbalance.
- False-alarm costs.
- Detection latency.
- Resource overhead.
- Cross-service and cross-environment generalization.
- Whether project telemetry can be released without violating data restrictions.

### Final Decision Summary

| Decision | Selected approach |
|---|---|
| Long-term architecture | Eadro-inspired multi-source model |
| First practical model direction | Metric-first multivariate anomaly detector |
| Published baseline reproduction | CausalRCA |
| Lightweight comparison/reference | MicroRCA |
| Immediate implementation | Out of scope for this literature-review issue |

### Completion Checklist

- [x] Three papers compared.
- [x] Strengths and limitations compared.
- [x] Numerical results interpreted with metric differences.
- [x] Most promising overall approach identified.
- [x] Most feasible first-model direction identified.
- [x] Published-baseline candidate identified.
- [x] Project-specific recommendation documented.
- [ ] Final Markdown file committed to GitHub.
- [ ] Pull request updated.
- [ ] Pull request link added to the parent Linear issue.
- [ ] Parent Linear issue moved to Done after team review.

