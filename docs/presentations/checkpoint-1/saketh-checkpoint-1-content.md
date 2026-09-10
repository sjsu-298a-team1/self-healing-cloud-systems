# Saketh Checkpoint 1 Presentation Content

## Section Overview

This section summarizes:

- Findings from the multivariate time-series anomaly-detection literature review.
- The proposed modeling direction for Project 298A.
- The published baseline selected for future reproduction.
- The feasibility, risks, and next steps.

Recommended section length: 4 slides.

---

# Slide 1: Research Focus

## Cloud and Microservice Anomaly Detection

### Project problem

Cloud-native applications produce large volumes of operational telemetry from:

- Service latency.
- CPU and memory usage.
- Disk activity.
- Network traffic.
- Logs.
- Distributed traces.

An anomaly in one service can propagate through dependent services and make the original cause difficult to identify.

### Research objective

Identify an anomaly-detection and root-cause-localization direction that is:

- Relevant to cloud and microservice telemetry.
- Practical to implement during 298A.
- Reproducible using public benchmarks.
- Extensible toward automated incident response and self-healing.

### Key research observation

Anomaly detection identifies whether a system is abnormal. Root-cause localization identifies which service or metric caused the abnormal behavior. The literature shows that combining both tasks can improve operational diagnosis.

### Speaker Notes

Our project focuses on detecting abnormal behavior in cloud and microservice systems. These systems generate multiple telemetry streams, including service latency, CPU, memory, disk, network, logs, and traces.

The main challenge is that one fault can affect several services. A downstream service may show the symptom even though another service or resource caused the original problem.

The literature review therefore examined methods that detect anomalies, model relationships between telemetry signals, and rank possible root causes.

Our goal is to select a direction that is technically relevant but also realistic to reproduce and implement during 298A.

---

# Slide 2: Literature Review Findings

## Three Relevant AIOps Approaches

| Paper | Main focus | Key inputs | Important result | Main limitation |
|---|---|---|---|---|
| MicroRCA | Lightweight service-level root-cause localization | Service response time, container metrics, host metrics | PR@1 = 0.89, PR@3 = 1.00, MAP = 0.97 | Full experimental dataset is not clearly available |
| Eadro | Joint anomaly detection and root-cause localization | Logs, KPIs, traces, and service dependencies | F1 = 0.989 on TrainTicket and 0.986 on SocialNetwork | Complex supervised multi-source pipeline |
| CausalRCA | Metric-level causal root-cause localization | Service latency and resource metrics | Fine-grained AC@3 = 0.7190 and Avg@5 = 0.6681 | Primarily localization-focused rather than standalone anomaly detection |

### Main findings

- Multi-source telemetry can reveal anomalies that traces or metrics alone may miss.
- Service dependencies help explain how anomalies propagate.
- Metric-level approaches are easier to reproduce than log-trace-metric systems.
- Published results are not directly comparable because the papers use different datasets, metrics, and fault scenarios.

### Speaker Notes

MicroRCA provides a lightweight graph-based approach. It detects abnormal response times and combines service and host metrics to rank possible faulty services.

Eadro is the most comprehensive approach because it jointly uses logs, KPIs, and traces. It also directly evaluates anomaly detection using F1, precision, and recall. However, its preprocessing and supervised training requirements make it difficult to reproduce quickly.

CausalRCA focuses on causal relationships between monitoring metrics. It is not a complete anomaly detector, but it provides a useful metric-level root-cause ranking method and has a public repository containing code and data.

The important conclusion is that the numerical results should not be treated as a direct leaderboard. Each method was tested on a different benchmark and under different fault-injection conditions.

### References

- MicroRCA: https://ieeexplore.ieee.org/document/9110353
- Eadro: https://doi.org/10.1109/ICSE48619.2023.00150
- CausalRCA: https://doi.org/10.1016/j.jss.2023.111724

---

# Slide 3: Proposed Modeling Direction

## Metric-First Multivariate Anomaly Detection

### Initial modeling direction

Begin with a metric-first multivariate anomaly-detection pipeline using:

- Service latency.
- CPU utilization.
- Memory utilization.
- Disk read and write activity.
- Network receive and transmit activity.
- Time-based and rolling statistical features.
- Service-level dependency information where available.

### Candidate benchmark or project environment

- OpenTelemetry Demo or another representative cloud-native microservice benchmark.
- Prometheus or OpenTelemetry metrics.
- Controlled fault-injection scenarios for ground-truth labels.
- Sock Shop for compatibility checks with the selected published baseline.

### Initial evaluation metrics

The anomaly detector should be evaluated using:

- Precision.
- Recall.
- F1-score.
- False-positive rate.
- False-negative rate.
- Detection latency.

For downstream root-cause localization, the project can additionally report:

- Top-1 accuracy.
- Top-3 accuracy.
- Mean reciprocal rank.
- AC@1 and AC@3 where applicable.

### Development path

```text
Metric telemetry
      ->
Multivariate anomaly detector
      ->
Anomaly window and severity
      ->
Service or metric root-cause ranking
      ->
Candidate remediation action
