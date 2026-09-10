# 298-11 — Dataset & Benchmark Evaluation

## Objective

Identify and compare viable datasets and benchmark approaches for the AI-driven incident response and self-healing cloud systems project. The evaluation focuses on telemetry coverage, anomaly/root-cause ground truth, accessibility, reproducibility, and suitability for the project’s planned models.

## Candidate Summary

| Candidate | Primary Data | Ground Truth | Anomaly Detection | Root-Cause Analysis | Primary Use |
|---|---|---|---|---|---|
| SMD (Server Machine Dataset) | Multivariate metrics | Point-level anomaly labels and contributing dimensions | Strong | Limited | First anomaly-detection model |
| RCAEval | Metrics, logs, traces | Root-cause service and fault annotations | Possible | Strong | Service-graph RCA |
| Loghub HDFS_v1 | System logs / log-derived traces | Normal/anomaly labels | Strong for log anomaly detection | Limited | Later log/LLM diagnosis work |

---

## 1. SMD — Server Machine Dataset

**Source:** NetManAIOps/OmniAnomaly — `ServerMachineDataset`  
**Source link:** https://github.com/NetManAIOps/OmniAnomaly/tree/master/ServerMachineDataset

### Description

SMD is a five-week multivariate time-series dataset collected from a large Internet company. It contains telemetry from 28 machines divided into three groups.

Each machine is treated as a separate entity and contains 38 dimensions. The official dataset contains:

- 28 machine entities
- 38 dimensions per entity
- 708,405 training observations
- 708,420 testing observations
- Approximately 4.16% anomaly ratio in the test data
- Separate training and testing data
- Point-level anomaly labels
- Interpretation labels identifying dimensions contributing to anomalies

### Telemetry Availability

- Metrics: Yes
- Logs: No
- Distributed traces: No
- Explicit service topology/dependencies: No

### Ground Truth

The `test_label` directory identifies whether each test point is anomalous.

The `interpretation_label` directory identifies dimensions contributing to detected anomalies.

This provides direct ground truth for multivariate time-series anomaly-detection evaluation.

### Format

The repository is organized into:

- `train/`
- `test/`
- `test_label/`
- `interpretation_label/`

Individual machine data is stored in text files such as:

`machine-1-1.txt`

### Access Verification

**Access verified: September 9, 2026.**

The public OmniAnomaly repository and `ServerMachineDataset` directory were successfully accessed.

As an additional verification step:

1. `ServerMachineDataset/train/machine-1-1.txt` was opened in GitHub.
2. GitHub displayed the file as approximately 9.29 MB.
3. The file was downloaded successfully.
4. The downloaded file was opened locally and the numeric multivariate telemetry values were successfully viewed.

This confirms that the recommended dataset is not only publicly listed but can actually be obtained and inspected by the team.

### License / Access Restrictions

SMD is publicly accessible through the OmniAnomaly GitHub repository and is distributed under the MIT License. No registration is required.

### Strengths

- Direct fit for multivariate time-series anomaly detection
- Publicly accessible
- Clear train/test split
- Point-level ground-truth anomaly labels
- Interpretation labels
- Widely used in anomaly-detection research
- Multiple published methods have evaluated on SMD
- Relatively easy to obtain and begin experimenting with

### Limitations

- Metrics only
- No application logs
- No distributed tracing data
- No microservice dependency graph
- Not suitable by itself for service-level root-cause localization
- Individual metric meanings are anonymized/not fully documented

### Suitability

**Anomaly detection:** High  
**Root-cause localization:** Low  
**Reproducible experimentation:** High

---

## 2. RCAEval

**Source:** phamquiluan/RCAEval  
**Source link:** https://github.com/phamquiluan/RCAEval

### Description

RCAEval is an open-source benchmark for root-cause analysis in microservice systems.

The current benchmark provides:

- 9 datasets
- 735 failure cases
- 11 fault types
- 3 microservice systems:
  - Online Boutique
  - Sock Shop
  - Train Ticket
- 15 reproducible RCA baselines

Failure cases include annotated root-cause services and root-cause indicators.

### Telemetry Availability

RCAEval contains several benchmark suites.

**RE1**
- Metrics: Yes
- Logs: No
- Traces: No

**RE2 / RE3**
- Metrics: Yes
- Logs: Yes
- Traces: Available for supported systems/suites

The benchmark therefore provides substantially richer multi-source telemetry than SMD.

### Fault Types

Examples include:

- CPU
- Memory
- Disk
- Network delay
- Packet loss
- Socket faults
- Code-level faults in RE3

### Ground Truth

Each failure case includes an annotated root-cause service and root-cause indicator.

This makes RCAEval particularly suitable for evaluating whether a model correctly localizes the source of a microservice incident.

### Access Verification

**Access verified: September 9, 2026.**

The public RCAEval GitHub repository was successfully accessed.

The `Available Datasets` section was inspected directly and confirmed the availability of RE1, RE2, and RE3 datasets across Online Boutique, Sock Shop, and Train Ticket.

The dataset table also confirmed the availability of metrics, logs, and traces across the relevant benchmark suites.

The complete multi-GB dataset was intentionally not downloaded because RCAEval is not the primary dataset selected for the first Checkpoint 1 model.

### License / Access Restrictions

RCAEval is publicly accessible. The datasets and code implemented by the RCAEval authors are distributed under the MIT License. Some included baseline implementations use other licenses or have no stated license, so reuse of individual baseline code should be checked separately.

### Storage / Compute Considerations

The RCAEval project provides a Hugging Face Parquet distribution of approximately 3.4 GB and allows individual suites or cases to be downloaded instead of retrieving the entire dataset.

The project documentation recommends approximately:

- 8 CPU cores
- 16 GB RAM
- approximately 50 GB available disk space

This makes RCAEval feasible for later project work but substantially heavier than SMD.

### Strengths

- Designed specifically for microservice RCA
- Known injected failures
- Root-cause annotations
- Multi-source telemetry
- Multiple microservice environments
- Existing reproducible RCA baselines
- Directly relevant to the project’s future root-cause localization model

### Limitations

- Larger storage footprint than SMD
- More complex preprocessing and environment requirements
- Not necessary for the first anomaly-detection model
- Telemetry availability differs across benchmark suites

### Suitability

**Anomaly detection:** Medium  
**Root-cause localization:** High  
**Reproducible experimentation:** High

---

## 3. Loghub HDFS_v1

**Source:** logpai/loghub — `HDFS`  
**Source link:** https://github.com/logpai/loghub/tree/master/HDFS

### Description

HDFS_v1 is a system-log dataset generated in a private cloud environment using benchmark workloads.

The logs are manually labeled using handcrafted rules to identify anomalies. Logs are grouped into traces according to HDFS block IDs, and each resulting trace receives a ground-truth normal/anomaly label.

The full HDFS_v1 dataset contains approximately:

- 38.7 hours of logs
- 11,175,629 log lines
- approximately 1.47 GiB of raw data

### Telemetry Availability

- Metrics: No
- Logs: Yes
- Log-derived traces/groupings: Yes
- Distributed APM traces: No
- Explicit microservice dependency information: No

### Ground Truth

HDFS_v1 contains normal/anomaly labels associated with HDFS block traces.

Preprocessed resources described by Loghub include:

- `HDFS_templates.csv`
- `anomaly_label.csv`
- `Event_traces.csv`
- `Event_occurrence_matrix.csv`
- `HDFS.npz`

### Access Verification

**Access verified: September 9, 2026.**

The public Loghub repository and HDFS directory were successfully accessed.

The HDFS README was inspected directly and confirmed that HDFS_v1:

- was generated in a private cloud environment,
- contains manually assigned anomaly labels,
- assigns normal/anomaly ground truth to traces, and
- provides downloadable/preprocessed resources for research.

### License / Access Restrictions

Loghub datasets are freely available for research or academic work. For any usage or distribution, the Loghub repository should be referenced and the Loghub paper cited where applicable. The Loghub license notice should be retained with copies of the dataset.

### Strengths

- Realistic system-log data
- Ground-truth anomaly labels
- Widely used for log anomaly detection
- Appropriate for later log-analysis or LLM incident-diagnosis work
- Publicly accessible for research

### Limitations

- No multivariate infrastructure metrics
- No microservice service graph
- No root-cause service labels
- Approximately 1.47 GiB raw dataset is larger than needed for the first model
- Log-derived traces should not be confused with modern distributed APM traces

### Suitability

**Anomaly detection:** High for log-based anomaly detection  
**Root-cause localization:** Low  
**Reproducible experimentation:** High

---

# Comparison

| Requirement | SMD | RCAEval | HDFS_v1 |
|---|---|---|---|
| Publicly accessible | Yes | Yes | Yes |
| Access verified by team | Yes | Yes | Yes |
| Metrics | Yes | Yes | No |
| Logs | No | Yes | Yes |
| Traces | No | Yes in relevant suites | Log-derived grouping only |
| Anomaly labels | Yes | Fault/root-cause annotations | Yes |
| Root-cause labels | Limited to contributing dimensions | Yes | No |
| First anomaly model fit | Excellent | Moderate | Moderate |
| Future RCA model fit | Poor | Excellent | Poor |
| Later LLM/log work fit | Poor | Strong | Strong |
| Setup complexity | Low | Medium/High | Medium |

---

# Recommendation

## Primary Checkpoint 1 Dataset: SMD

SMD is the recommended primary dataset for the first 298A model.

The first planned model focuses on multivariate time-series anomaly detection, and SMD directly supports that task with 38-dimensional machine telemetry, explicit train/test splits, anomaly labels, and interpretation labels.

SMD also has the lowest access and setup barrier of the three candidates. The team has already downloaded and opened an actual SMD training file, confirming that the dataset is immediately usable.

Therefore:

**Primary dataset for first model:** SMD

## Secondary Benchmark Direction: RCAEval

RCAEval is the recommended dataset/benchmark for the future service-graph root-cause localization component because it provides microservice failure cases, root-cause annotations, multiple telemetry sources, and reproducible RCA baselines.

## Additional Dataset Direction: Loghub HDFS_v1

HDFS_v1 is retained as a candidate for later log-anomaly analysis and LLM-assisted incident-diagnosis work.

---

# Preliminary Checkpoint 1 Evaluation Metric and Success Target

For the first anomaly-detection model:

**Dataset:** SMD  
**Primary metric:** F1-score  
**Preliminary target:** F1 >= 0.85

This is a preliminary Checkpoint 1 success target and may be refined after the team completes issue `298-13 — Select Published Baseline & Exact Result to Reproduce`.

The final evaluation protocol must use the same scoring procedure as the selected baseline so that results are directly comparable. In particular, raw and point-adjusted F1 scores should not be mixed without clearly identifying the evaluation method.

---

# Compute and Storage Assessment

## SMD

SMD has relatively low infrastructure requirements compared with the other candidates.

The dataset can be downloaded directly from GitHub and inspected locally. Training requirements will depend on the selected anomaly-detection model, but no specialized distributed infrastructure is required simply to access and prepare the dataset.

## RCAEval

RCAEval has greater resource requirements because of its larger multi-source telemetry.

A subset-based download strategy should be used rather than downloading all telemetry when it is not required.

## HDFS_v1

The raw HDFS_v1 dataset is approximately 1.47 GiB. Additional disk space will be needed for processed files and model artifacts.

CPU-based preprocessing is feasible; later model-training requirements depend on the selected approach.

---

# Preliminary Benchmark Strategy

1. Use **SMD** for the first multivariate time-series anomaly-detection model.
2. Evaluate anomaly detection primarily using **F1-score**.
3. Use **F1 >= 0.85** as the preliminary Checkpoint 1 success target.
4. Coordinate with `298-13` before locking the exact published baseline and evaluation protocol.
5. Use **RCAEval** later for root-cause localization and multi-source telemetry evaluation.
6. Retain **HDFS_v1** as a candidate for later log/LLM incident-diagnosis evaluation.
7. Keep dataset-specific evaluation separate rather than claiming that a single dataset supports all four system components.

---

# Access Evidence

Access verification was performed on September 9, 2026.

Evidence captured:

- SMD repository and dataset directory accessible
- SMD `machine-1-1.txt` training file opened on GitHub
- SMD `machine-1-1.txt` successfully downloaded and opened locally
- RCAEval Available Datasets table accessed
- RCAEval metrics/logs/traces coverage verified
- Loghub HDFS_v1 repository and README accessed
- HDFS normal/anomaly labeling documentation verified

### Supporting Evidence

- [SMD access verification](evidence/smd-access-evidence.pdf) — shows the SMD repository, the `machine-1-1.txt` file accessible on GitHub, and the downloaded telemetry file opened locally.

---

# Conclusion

All three candidate datasets are viable for different portions of the project.

SMD is the strongest immediate choice because it directly supports the first multivariate time-series anomaly-detection model, has labeled anomalies, is easy to access, and has a mature body of published benchmark results.

RCAEval is the strongest future choice for microservice root-cause localization, while HDFS_v1 provides an additional realistic source for later log-based incident analysis.

The recommended Checkpoint 1 direction is therefore to proceed with **SMD as the primary dataset**, use **F1-score with a preliminary target of at least 0.85**, and coordinate the final baseline/evaluation protocol with issue `298-13`.
