# Published Baseline Selection for Project 298A

## 1. Baseline Selection Summary

### Selected published baseline

**CausalRCA: Causal Inference Based Precise Fine-Grained Root Cause Localization for Microservice Applications**

### Selected reproduction experiment

**Fine-grained root-cause metric localization within a known faulty service**

This experiment evaluates whether CausalRCA can rank the specific metric responsible for an anomaly when the faulty microservice is already known.

### Selected published result

The result will be reproduced from:

**Table 4: Localization accuracy of CI-based methods on localizing root-cause metrics in faulty services for different anomalies**

The main published results for CausalRCA are:

- Average AC@1: 0.2476
- Average AC@3: 0.7190
- Average Avg@5: 0.6681

### Selection decision

CausalRCA is selected as the single published baseline for Project 298A.

The baseline is selected because it has:

- A peer-reviewed published paper.
- A clearly defined metric-based experiment.
- A public official implementation.
- Publicly available experimental data.
- Clearly defined evaluation metrics.
- A reproducible microservice benchmark.
- A reasonable path toward a focused reproduction during 298A.

---

## 2. Full Paper Citation

Ruyue Xin, Peng Chen, and Zhiming Zhao, “Causal Inference Based Precise Fine-Grained Root Cause Localization for Microservice Applications,” *Journal of Systems and Software*, vol. 203, article 111724, 2023.

Published paper:

https://doi.org/10.1016/j.jss.2023.111724

Open-access paper:

https://pure.uva.nl/ws/files/166189852/CausalRCA.pdf

Publication information:

- Authors: Ruyue Xin, Peng Chen, and Zhiming Zhao
- Publication year: 2023
- Journal: Journal of Systems and Software
- Volume: 203
- Article number: 111724
- DOI: 10.1016/j.jss.2023.111724
- License: CC BY

---

## 3. Why CausalRCA Was Selected

The previous literature review considered MicroRCA, Eadro, and CausalRCA.

CausalRCA was selected as the published baseline for the following reasons:

1. The official repository contains implementation code and experimental data.
2. The paper provides both coarse-grained and fine-grained experiments.
3. The selected fine-grained experiment has a clearly defined evaluation target.
4. The input consists primarily of service and resource metrics, which are easier to collect and synchronize than logs, metrics, and traces.
5. The evaluation uses interpretable ranking metrics.
6. The benchmark application, fault types, and data-collection procedure are documented.
7. The experiment can be reproduced incrementally.
8. The method is relevant to cloud and microservice operations.
9. The method can support later root-cause analysis in an automated incident-response system.
10. The reproduction effort is more manageable than reproducing the full Eadro architecture.

CausalRCA is not selected because it is a complete anomaly-detection system. Its primary task is root-cause localization after an anomaly has been detected. It is selected as a metric-level root-cause-localization baseline that can complement the team’s planned anomaly-detection system.

---

## 4. Selected Experiment

### Experiment name

Fine-grained root-cause metric localization within a known faulty service.

### Experiment objective

Given:

- A known faulty microservice.
- Monitoring metrics from that service.
- A performance anomaly.

CausalRCA ranks the service’s monitoring metrics and attempts to identify the metric that caused the anomaly.

For example, if the faulty service is known to be the `orders` service, the method attempts to determine whether CPU usage, memory usage, disk activity, or network activity is the root-cause metric.

### Why this experiment was selected

This experiment is preferable to reproducing the full paper because it:

- Has a focused scope.
- Uses a clearly defined input.
- Has a clearly defined output.
- Uses publicly available fault data.
- Has a published result in Table 4.
- Requires fewer system-level assumptions than the full-service experiment.
- Can be tested before attempting the more difficult coarse-grained experiment.

### Important scope condition

The selected experiment assumes that the faulty service is already known.

The reproduction will evaluate metric-level ranking inside that known faulty service. It will not initially reproduce the complete process of discovering the faulty service across the entire application.

---

## 5. Baseline Model and Method

CausalRCA contains two primary stages:

1. Causal structure learning.
2. Root-cause inference.

### Causal structure learning

CausalRCA uses a gradient-based causal structure-learning method to learn a weighted directed acyclic graph.

In the graph:

- Each node represents a monitoring metric.
- Each edge represents a possible relationship between two metrics.
- Edge weights represent the strength of the learned relationship.
- The graph is intended to represent possible anomaly-propagation paths.

The method uses a two-layer multilayer perceptron encoder and decoder to learn nonlinear relationships between metrics.

### Root-cause inference

After learning the metric graph:

1. The graph edges are reversed.
2. The absolute values of the edge weights are used as transition strengths.
3. Personalized PageRank is applied to the graph.
4. Metrics are ranked according to their PageRank scores.
5. The ranked list is compared with the known root-cause metric.

The highest-ranked metric is treated as the most likely root cause.

### Baseline comparisons in the paper

The paper compares CausalRCA against causal-structure-learning methods combined with PageRank:

- PC-based method.
- GES-based method.
- LiNGAM-based method.

These methods provide comparison points for the published experiment.

---

## 6. Dataset and Benchmark

### Benchmark application

The selected benchmark is Sock Shop.

Sock Shop is an open-source microservice application that simulates an e-commerce website selling socks.

Sock Shop contains:

- 13 microservices.
- Heterogeneous service implementations.
- REST communication between services.
- Functional services such as frontend, catalogue, carts, user, orders, payment, and shipping.

Official Sock Shop repository:

https://github.com/microservices-demo/microservices-demo

### Testbed configuration

The paper deploys Sock Shop using Kubernetes on cloud virtual machines.

The reported testbed contains:

- One Kubernetes master node.
- Three Kubernetes worker nodes.
- Ubuntu 18.04.
- 4 vCPUs per virtual machine.
- 16 GB RAM per virtual machine.
- 80 GB disk per virtual machine.
- Prometheus for monitoring.
- Grafana for visualization.
- Locust for workload generation.

The deployment is illustrated in:

**Figure 3: The microservice application Sock Shop deployed on VMs with Kubernetes**

### Fault types

The paper evaluates three injected anomaly types:

- CPU hog.
- Memory leak.
- Network delay.

The faults are injected using Pumba.

#### CPU hog

CPU resources are consumed continuously for the target service.

#### Memory leak

Memory is allocated continuously so that the service gradually consumes more memory.

#### Network delay

Network packets are delayed using traffic-control mechanisms.

Each injected anomaly lasts:

- Five minutes of active fault injection.
- Ten minutes of cooldown before the next injection.

### Dataset access confirmation

The official CausalRCA repository is public:

https://github.com/AXinx/CausalRCA_code

The repository contains a `data_collected` directory:

https://github.com/AXinx/CausalRCA_code/tree/master/data_collected

The directory includes publicly accessible data files such as:

- `cpu-hog1_*.pkl`
- `memory-leak1_*.pkl`
- `latency1_*.pkl`

The repository README states that the authors collected service-level and resource-level data and stored the collected files in the `data_collected` directory.

The repository also includes data-collection notebooks and experiment scripts.

Therefore, the benchmark data is considered publicly obtainable for the selected reproduction experiment.

### Dataset limitations

Although the repository contains data files, the team must verify that:

- The files required for the selected experiment are present.
- The file names match the training scripts.
- The expected columns and metric formats are available.
- The data labels identify the injected fault and root-cause metric.
- The data can be loaded using the current software environment.

Dataset access is confirmed at the public repository level. Full reproduction should not begin until the files are locally downloaded and inspected.

---

## 7. Input Features

The selected experiment uses monitoring metrics collected from the known faulty service.

### Service-level metric

- Service latency.

### Resource-level metrics

- CPU usage.
- Memory usage.
- Disk read.
- Disk write.
- Network receive bytes.
- Network transmit bytes.

The metrics are collected at five-second intervals.

The collected metrics are listed in:

**Table 2: Collected monitoring metrics**

### Input format for reproduction

The reproduction should create an input time series containing the available monitoring metrics for the selected faulty service.

The input should preserve:

- Timestamp order.
- Five-second sampling interval.
- Metric names.
- Fault interval.
- Service identity.
- Root-cause metric label.

The data should not be randomly shuffled because the method relies on time-series relationships.

---

## 8. Evaluation Metrics

CausalRCA uses ranking-based localization metrics.

### AC@1

AC@1 measures whether the correct root-cause metric is ranked first.

A higher AC@1 indicates that the method identifies the correct metric as its top prediction more frequently.

### AC@3

AC@3 measures whether the correct root-cause metric appears within the top three ranked metrics.

This metric is useful because an operator may investigate a small set of top-ranked candidates rather than only the first prediction.

### Avg@5

Avg@5 measures the average localization accuracy across the first five ranked positions.

It summarizes the quality of the ranked list rather than evaluating only one position.

### Metrics selected for reproduction

The reproduction will report:

- AC@1.
- AC@3.
- Avg@5.

These are the same primary metrics used in the published Table 4 experiment.

---

## 9. Published Numerical Result

### Exact source

The selected result is reported in:

**Table 4: Localization accuracy of CI-based methods on localizing root-cause metrics in faulty services for different anomalies**

### CausalRCA results from Table 4

| Fault type | AC@1 | AC@3 | Avg@5 |
|---|---:|---:|---:|
| CPU hog | 0.2286 | 0.7286 | 0.6700 |
| Memory leak | 0.2714 | 0.7143 | 0.6771 |
| Network delay | 0.2429 | 0.7143 | 0.6571 |
| Average | 0.2476 | 0.7190 | 0.6681 |

### Target reproduction values

The primary target values for the reproduction are:

```text
Average AC@1 = 0.2476
Average AC@3 = 0.7190
Average Avg@5 = 0.6681
