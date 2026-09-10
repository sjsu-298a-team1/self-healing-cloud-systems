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


## 2. Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-Source Data

### Paper citation

Cheryl Lee, Tianyi Yang, Zhuangbin Chen, Yuxin Su, and Michael R. Lyu, “Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data,” Proceedings of the IEEE/ACM 45th International Conference on Software Engineering, 2023.

Paper: https://doi.org/10.1109/ICSE48619.2023.00150
Open paper: https://www.cse.cuhk.edu.hk/lyu/_media/conference/clee_icse2023_eadro.pdf
Code and data: https://github.com/BEbillionaireUSD/Eadro
Dataset record: https://doi.org/10.5281/zenodo.7615393

### Problem addressed

Eadro addresses automated troubleshooting in large-scale microservice systems. Existing approaches commonly treat anomaly detection and root-cause localization as separate tasks and rely primarily on traces. This can miss anomalies visible in logs or key performance indicators.

Eadro jointly performs anomaly detection and root-cause localization using logs, KPIs, and traces.

### Model and algorithm

Eadro contains three main stages:

1. Modal-wise learning:

   * Hawkes process and fully connected layers model log-event occurrences.
   * Dilated causal convolution models KPI time-series patterns.
   * Dilated causal convolution models trace-latency behavior.

2. Dependency-aware status learning:

   * The representations from logs, KPIs, and traces are fused.
   * A graph attention network models inter-service dependencies derived from historical invocations.

3. Joint detection and localization:

   * An anomaly detector predicts whether an observation window is normal or abnormal.
   * A root-cause localizer ranks microservices by their probability of being the culprit.
   * Both tasks share learned representations and a joint objective.

The overall architecture is shown in Figure 5 of the paper.

### Input telemetry and features

Eadro uses three telemetry sources:

* Logs:

  * Chronological log-event occurrences.
  * Log events parsed using Drain.
* KPIs:

  * CPU system usage.
  * CPU total usage.
  * CPU user usage.
  * Memory usage.
  * Working-set memory.
  * Received bytes.
  * Transmitted bytes.
* Traces:

  * Invocation latency.
  * Request duration.
  * HTTP response information.
  * Inter-service invocation relationships.

Each observation window contains the logs, KPI time series, and trace records aggregated for each microservice.

### Dataset and benchmark

The authors collected multi-source telemetry from two open-source microservice benchmarks:

1. TrainTicket:

   * 41 interacting microservices.
   * 27 business-related services.
   * Railway-ticketing application.

2. SocialNetwork:

   * 21 interacting microservices.
   * 14 business-related services.
   * Social-networking application using Thrift RPCs.

The testbeds used Docker containers and request simulators. Jaeger collected traces, cAdvisor and Prometheus collected KPIs, and Elasticsearch, Fluentd, and Kibana collected logs.

The paper reports 48,296 traces and 162 fault injections for TrainTicket, and 126,384 traces and 72 fault injections for SocialNetwork.

The injected faults included CPU exhaustion, network jam, packet loss, and other performance-degradation scenarios described in the evaluation section.

### Evaluation metrics

For anomaly detection, the paper uses:

* Precision.
* Recall.
* F1-score.

For root-cause localization, the paper uses:

* HR@1.
* HR@3.
* HR@5.
* NDCG@3.
* NDCG@5.

The anomaly-detection task uses binary labels based on whether a fault was injected during the observation window.

### Numerical results

The anomaly-detection results are reported in Table II:

| Dataset       |    F1 | Recall | Precision |
| ------------- | ----: | -----: | --------: |
| TrainTicket   | 0.989 |  0.995 |     0.984 |
| SocialNetwork | 0.986 |  0.996 |     0.977 |

The root-cause-localization results are reported in Table III. Eadro achieves the following average results:

* HR@1: 0.982.
* HR@5: 0.990.
* NDCG@5: 0.989.

The ablation results in Table IV show that removing KPIs, trace latency, logs, or the graph-attention component reduces performance. The largest HR@1 reductions occur when KPI or trace information is removed.

### Exact paper tables and figures

* Figure 1: Example of anomaly propagation through microservices.
* Figure 2: Trace-latency behavior under different fault types.
* Figure 3: Log-event occurrence behavior during faults.
* Figure 4: KPI behavior during CPU exhaustion.
* Figure 5: Overview of Eadro.
* Figure 6: Visualization of Eadro’s troubleshooting output.
* Figure 7: t-SNE visualization of learned representations.
* Table I: Comparison of common anomaly detectors.
* Table II: Performance comparison for anomaly detection.
* Table III: Performance comparison for root-cause localization.
* Table IV: Experimental results of the ablation study.

### Code availability

The official repository is publicly available:

https://github.com/BEbillionaireUSD/Eadro

The repository contains model code, preprocessing code, requirements, and execution instructions. However, the repository uses older dependencies and the setup instructions do not fully explain every preprocessing step.

### Dataset availability

The authors state that the code and data are publicly released. The dataset is linked through Zenodo:

https://doi.org/10.5281/zenodo.7615393

The dataset should be downloaded and inspected to verify that all raw data, labels, preprocessing outputs, and required directory structures are present.

### Compute requirements

The paper reports experiments conducted on:

* Linux.
* Python 3.7.
* NVIDIA GeForce GTX 1080 GPU.
* PyTorch 1.12.1.
* DGL 0.9.1.
* tick 0.7.0.1.
* Adam optimizer.
* Learning rate of 0.001.
* Batch size of 256.
* 50 training epochs.

A modern GPU should be sufficient once the software environment and data pipeline are functioning.

### Reproduction difficulty

Overall reproduction difficulty: High.

Main risks include:

* Older Python and deep-learning dependencies.
* Incomplete preprocessing instructions.
* Apparent inconsistencies in the released code.
* Missing or unclear construction steps for the chunks directory.
* Need to validate the Zenodo archive.
* Need to reproduce logs, KPI windows, traces, and fault labels consistently.
* Need to adapt the framework to a different microservice benchmark if OpenTelemetry Demo is used.

A reasonable reproduction plan is to first validate the dataset and run one anomaly-detection experiment before attempting the full joint troubleshooting pipeline.

### Strengths

* Directly addresses both anomaly detection and root-cause localization.
* Uses logs, KPIs, and traces together.
* Models temporal behavior and service dependencies.
* Uses graph attention to represent anomaly propagation.
* Provides strong anomaly-detection F1 scores.
* Includes an ablation study demonstrating the contribution of each telemetry source.
* Highly relevant to cloud and microservice AIOps.

### Limitations

* Requires labeled fault windows and supervised training.
* Requires three synchronized telemetry modalities.
* Reproduction depends on older software libraries.
* The released repository may require debugging.
* The reported results come from TrainTicket and SocialNetwork and may not transfer directly to OpenTelemetry Demo.
* The model is more computationally and operationally complex than a metric-only baseline.
* The dataset and preprocessing pipeline require independent validation.

### Relevance to the 298A project

Eadro is the strongest conceptual fit for a project involving cloud or microservice telemetry because it combines anomaly detection with root-cause localization and uses logs, metrics, and traces.

It is a promising candidate for the first model if the team can obtain synchronized multi-source telemetry and labeled fault windows. Its complexity makes it less suitable as the first implementation if the team needs a lightweight or quickly reproducible baseline.

### Preliminary recommendation

Eadro should be considered the strongest candidate for the project’s long-term multi-source anomaly-detection and troubleshooting architecture. It should be implemented only after the team confirms data availability, labeling, and the feasibility of reproducing the preprocessing pipeline.

### Completion checklist

* [x] Problem addressed documented.
* [x] Model and algorithm documented.
* [x] Input telemetry and features documented.
* [x] Dataset and benchmarks documented.
* [x] Evaluation metrics documented.
* [x] Numerical results documented.
* [x] Exact paper tables and figures documented.
* [x] Code link documented.
* [x] Dataset link documented.
* [x] Compute requirements documented.
* [x] Reproduction difficulty assessed.
* [x] Strengths and limitations documented.
* [ ] Findings added to the GitHub literature-review file.
* [ ] Changes committed to GitHub.
* [ ] GitHub commit or pull request linked to the Linear issue.


## 3. CausalRCA: Causal Inference Based Precise Fine-Grained Root Cause Localization for Microservice Applications

### Paper citation

Ruyue Xin, Peng Chen, and Zhiming Zhao, “Causal Inference Based Precise Fine-grained Root Cause Localization for Microservice Applications,” Journal of Systems and Software, vol. 203, article 111724, 2023.

Published paper: https://doi.org/10.1016/j.jss.2023.111724
Open paper: https://pure.uva.nl/ws/files/166189852/CausalRCA.pdf
Code and data: https://github.com/AXinx/CausalRCA_code

### Problem addressed

CausalRCA addresses precise and fine-grained root-cause localization in microservice applications. Many existing approaches identify only the faulty service, while operators may also need to know which specific metric or resource caused the problem.

CausalRCA attempts to identify both:

* The faulty microservice.
* The root-cause metric within the faulty service.

The primary task is root-cause localization rather localization rather than standalone anomaly detection.

### Model and algorithm

CausalRCA consists of three main components:

1. Monitoring metrics:

   * Collect service-level and resource-level time-series metrics.

2. Causal structure learning:

   * Use a gradient-based causal structure-learning method.
   * Generate a weighted directed acyclic graph.
   * Represent possible cause-effect relationships between monitoring metrics.

3. Root-cause inference:

   * Reverse the learned graph edges.
   * Use the absolute edge weights as transition strengths.
   * Apply PageRank to rank candidate root-cause metrics.

The overall CausalRCA framework is shown in Figure 1. The learned metric graph and PageRank-based ranking process are illustrated in Figure 1 and the methodology section.

### Input telemetry and features

CausalRCA uses:

* Service latency.
* Container CPU usage.
* Container memory usage.
* Disk read.
* Disk write.
* Network receive bytes.
* Network transmit bytes.

The monitoring metrics are time-series data collected at five-second intervals.

The method supports:

* Coarse-grained localization using service latency.
* Fine-grained localization using resource metrics within a known faulty service.
* Fine-grained localization using all metrics across all services.

### Dataset and benchmark

The authors evaluate CausalRCA using the Sock Shop microservice benchmark.

The testbed includes:

* 13 microservices.
* One Kubernetes master node.
* Three Kubernetes worker nodes.
* Ubuntu 18.04.
* 4 vCPUs per VM.
* 16 GB RAM per VM.
* 80 GB disk per VM.
* Prometheus for monitoring.
* Grafana for visualization.
* Locust for workload generation.

The injected anomaly types are:

* CPU hog.
* Memory leak.
* Network delay.

Each anomaly lasts five minutes, followed by a ten-minute cooldown period. Pumba is used for fault injection.

The testbed configuration is illustrated in Figure 3, and the collected metrics are listed in Table 2.

### Evaluation metrics

CausalRCA uses ranking-based localization metrics:

* AC@1: whether the correct root cause is ranked first.
* AC@3: whether the correct root cause appears in the top three results.
* Avg@5: the average localization accuracy across the top five ranks.

The paper evaluates both coarse-grained faulty-service localization and fine-grained root-cause-metric localization.

### Numerical results

For coarse-grained faulty-service localization, the results are reported in Table 3.

CausalRCA achieves:

* Average AC@1: 0.2000.
* Average AC@3: 0.5749.
* Average Avg@5: 0.5815.

For fine-grained root-cause-metric localization within a known faulty service, the results are reported in Table 4.

CausalRCA achieves:

* Average AC@1: 0.2476.
* Average AC@3: 0.7190.
* Average Avg@5: 0.6681.

For the fine-grained task, CausalRCA improves the average Avg@5 over the compared causal baselines by approximately 9.43%.

The paper also reports statistical testing for the coarse-grained experiment. The ANOVA test produces a p-value of 0.0003. The pairwise comparison results are shown in Figure 4.

### Exact paper tables and figures

* Figure 1: CausalRCA framework overview.
* Figure 2: Example of anomaly propagation and metric relationships.
* Figure 3: Sock Shop microservice application deployed on virtual machines with Kubernetes.
* Figure 4: P-values of root-cause-localization methods.
* Figure 5: Localization accuracy with different gamma and eta parameters.
* Figure 6: CausalRCA performance for different anomaly types.
* Table 1: Classification of metric-based root-cause-localization research.
* Table 2: Collected monitoring metrics.
* Table 3: Localization accuracy for faulty-service localization.
* Table 4: Localization accuracy for root-cause-metric localization within faulty services.

### Code availability

The official repository is publicly available:

https://github.com/AXinx/CausalRCA_code

The repository includes:

* Training scripts.
* Baseline implementations.
* Data-collection notebooks.
* Fault-data files.
* Experiment configurations.
* Pinned dependency information.

The repository does not clearly provide a permissive software license, so reuse terms should be reviewed before incorporating code directly into the final project.

### Dataset availability

The paper states that code and data are open-sourced in the GitHub repository:

https://github.com/AXinx/CausalRCA_code

The repository contains fault-data files for CPU, memory, and network experiments across several services. This makes CausalRCA more reproducible than MicroRCA because data and experiment scripts are available together.

The repository contents should still be checked to confirm that all files required for every published experiment are included.

### Compute requirements

The paper reports:

* A Kubernetes cluster with one master and three worker VMs.
* 4 vCPUs per VM.
* 16 GB RAM per VM.
* 80 GB disk per VM.
* Prometheus and Grafana monitoring.
* Locust workload generation.
* CUDA-enabled execution when available.
* A two-layer MLP encoder and decoder.
* Learning rate of 0.001.
* Adam optimizer.
* 1,000 training epochs.
* Ten experimental repetitions with averaged results.

The paper estimates that the framework requires tens of seconds for the Sock Shop benchmark. Runtime and memory requirements will increase as the number of metric nodes grows.

### Reproduction difficulty

Overall reproduction difficulty: Medium to High.

The repository is more complete than the MicroRCA repository because it includes data files, notebooks, and training scripts. However, reproduction still requires:

* Installing older Python and machine-learning dependencies.
* Deploying the Sock Shop benchmark.
* Recreating Prometheus metric collection.
* Recreating the fault-injection schedule.
* Resolving differences between the paper and repository configurations.
* Confirming whether the paper’s 1,000 epochs match the repository settings.
* Repeating the experiments ten times for comparable averages.

A practical reproduction plan is to reproduce one coarse-grained experiment first, then reproduce one fine-grained metric-localization experiment.

### Strengths

* Provides causal, metric-level root-cause analysis.
* Supports both service-level and metric-level localization.
* Uses only monitoring metrics and does not require logs or traces.
* Includes public code and fault-data files.
* Uses a widely recognized Sock Shop benchmark.
* Provides comparisons with PC, GES, and LiNGAM causal methods.
* More feasible as a focused baseline than Eadro.
* Produces interpretable ranked lists of candidate root causes.

### Limitations

* The primary objective is root-cause localization, not general anomaly detection.
* The method assumes anomalies manifest as increased service response time.
* The evaluation uses one benchmark application and three injected fault types.
* Causal discovery can become expensive as the number of metrics increases.
* The learned graph may not represent true causal relationships in every operational setting.
* Results depend on parameter choices such as gamma and eta.
* The repository uses older dependencies.
* The paper and repository may use different training-epoch configurations.
* The method does not directly use logs or traces.

### Relevance to the 298A project

CausalRCA is relevant if the project needs interpretable metric-level diagnosis after detecting an anomaly. Its use of service latency and resource metrics aligns well with cloud telemetry and can provide ranked root-cause candidates.

It is less suitable as the primary anomaly-detection model because its main output is a root-cause ranking rather than a normal/abnormal decision.

### Preliminary recommendation

CausalRCA is the strongest candidate among the three papers for a focused published-baseline reproduction. The repository contains both implementation code and experimental data, and the method can be tested using metric telemetry without requiring synchronized logs and traces.

### Completion checklist

* [x] Problem addressed documented.
* [x] Model and algorithm documented.
* [x] Input telemetry and features documented.
* [x] Dataset and benchmark documented.
* [x] Evaluation metrics documented.
* [x] Numerical results documented.
* [x] Exact paper tables and figures documented.
* [x] Code link documented.
* [x] Dataset link documented.
* [x] Compute requirements documented.
* [x] Reproduction difficulty assessed.
* [x] Strengths and limitations documented.
* [ ] Findings added to the GitHub literature-review file.
* [ ] Changes committed to GitHub.
* [ ] GitHub commit or pull request linked to the Linear issue.

