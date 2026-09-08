# Literature Review: Service-Graph Root-Cause Localization

This review is for Linear issue **298-9**. I wanted to understand how earlier work finds the original failed service when one problem creates errors in several connected microservices.

This is the situation we will have in our project. If payment becomes slow, checkout and frontend may also become slow. The model should use the dependency between these services and rank payment as the cause instead of only reporting the services that were affected later.

I chose MicroRCA, Eadro, and CausalRCA. These are not three versions of the same idea. MicroRCA is a lightweight graph-ranking method, Eadro is a multimodal deep-learning method, and CausalRCA learns causal relationships from metrics. All three were published in peer-reviewed venues and match a part of our proposed system.

I checked the full papers, the reported experiment tables, and the linked repositories. I did not run the implementations yet, so the reproduction notes below separate what I verified from the paper and repository from what still needs to be tested.

## 1. MicroRCA

**Paper:** Li Wu, Johan Tordsson, Erik Elmroth, and Odej Kao, “MicroRCA: Root Cause Localization of Performance Issues in Microservices,” IEEE/IFIP NOMS, 2020.  
**Links:** [paper](https://inria.hal.science/hal-02441640/document) | [repository](https://github.com/elastisys/MicroRCA)

### How it works

MicroRCA uses response time between services together with container and host metrics. It first finds abnormal service calls using BIRCH clustering. It then builds a directed graph with service nodes and host nodes.

A service-to-service edge comes from the runtime call path. A service is also connected to the host where it is running. The graph weights include the response-time anomaly and the correlation between service latency and CPU, memory, network, or I/O usage.

MicroRCA removes the normal parts of the graph, reverses the call edges, and runs Personalized PageRank. The final PageRank score is used to rank the services. The idea is to follow the failure backward through the same path where the symptoms propagated.

### Experiment

The authors used Sock Shop, a 13-service e-commerce application. It ran on Kubernetes in Google Cloud with Istio and Prometheus. The testbed had one master node, four worker nodes, and a separate workload-generator machine.

They tested three faults:

- network latency;
- CPU hog;
- memory leak.

Each fault lasted one minute and was repeated five times. The paper reports 95 fault cases.

### Results reported by the paper

| Metric | MicroRCA result |
|---|---:|
| PR@1 | 0.89 |
| PR@3 | 1.00 |
| Mean Average Precision | 0.97 |

PR@1 is the percentage of cases where the correct service is ranked first. PR@3 checks whether it is inside the first three results. These two measures match the Top-1 and Top-3 evaluation required by our project.

The result is strong, but it is based on one application and three performance faults. It should not be treated as proof that the same accuracy will transfer to OpenTelemetry Demo.

### Repository check

The repository is small. It contains:

- the main Python implementation;
- an online version;
- a Sock Shop Kubernetes file;
- four CSV files for one example involving a CPU fault in the carts service.

The README calls the CSV files an example. I did not find the complete 95-case experimental dataset in the repository. Therefore, the algorithm code is public, but the full paper dataset is not clearly available there.

The implementation does not pin dependency versions. It uses DataFrame.iteritems(), which was removed in pandas 2.0, and it expects specific CSV filenames and columns. We would need an older pandas environment or a small compatibility change. We would also need to convert our OpenTelemetry metrics and trace data into the format expected by the code.

The repository has no license detected by GitHub. We can study it and test academic reproduction, but we should clarify reuse terms before copying its code into the final project.

### Reproduction judgment

Running the algorithm on its example data should be possible on a laptop after fixing the Python environment. The paper reports 3.3 seconds for graph construction and 0.03 seconds for ranking on eight CPU cores, so model compute is not the main problem.

The difficult part is reproducing the input data and full experiment. Because only one example case is included, we would probably need to collect our own OpenTelemetry data and write an adapter.

**Difficulty for our team: medium.**

## 2. Eadro

**Paper:** Cheryl Lee, Tianyi Yang, Zhuangbin Chen, Yuxin Su, and Michael R. Lyu, “Eadro: An End-to-End Troubleshooting Framework for Microservices on Multi-source Data,” IEEE/ACM ICSE, 2023.  
**Links:** [paper](https://arxiv.org/pdf/2302.05092) | [repository](https://github.com/BEbillionaireUSD/Eadro) | [dataset record linked by the authors](https://doi.org/10.5281/zenodo.7615393)

### How it works

Eadro combines logs, metrics, and traces. It also trains anomaly detection and root-cause localization together instead of assuming that a separate detector always gives a correct answer.

For every service, Eadro creates:

- log-event features;
- KPI time-series features;
- latency features taken from traces.

The service call relationship comes from traces. Each graph node is a microservice, and each edge is a call between two services. A graph attention network learns how much attention to give to each neighbor. The final representation goes to one classifier that detects an incident and another classifier that ranks the root-cause service.

### Experiment

The authors built datasets from:

- TrainTicket, with 41 interacting services;
- SocialNetwork, with 21 services.

They collected traces with Jaeger, metrics with cAdvisor and Prometheus, and logs with Elasticsearch, Fluentd, and Kibana. ChaosBlade injected CPU exhaustion, network delay, and packet loss.

The paper reports 48,296 traces and 162 injections for TrainTicket, and 126,384 traces and 72 injections for SocialNetwork. The data was split into 60% training and 40% testing.

### Results reported by the paper

| Dataset | HR@1 | HR@3 | HR@5 |
|---|---:|---:|---:|
| TrainTicket | 0.990 | 0.992 | 0.993 |
| SocialNetwork | 0.974 | 0.988 | 0.991 |

The paper also reports anomaly-detection F1 scores of 0.989 for TrainTicket and 0.986 for SocialNetwork.

The ablation study is useful for our design. Performance dropped when logs, metrics, trace latency, or the graph component was removed. This supports our plan to collect all three telemetry signals.

These results still need careful interpretation. Eadro is supervised and is trained using labelled fault windows from the same benchmark systems. Its result does not show that a model trained on TrainTicket will automatically work on OpenTelemetry Demo.

### Repository and dataset check

The repository contains preprocessing files, model code, a requirements file, and a short run command. The dependencies are pinned to older versions, including PyTorch 1.12.1, DGL 0.9.1, and tick 0.7.0.1.

The dataset is not stored in the GitHub repository. The authors link a Zenodo record. We must download and inspect that archive before claiming that every file needed by preprocessing is present.

Static inspection also found code issues that make the repository risky as a direct baseline:

- chunkDataset is defined with an edges argument but is called without it;
- the trace and metric models refer to variables that are not defined in their constructors;
- the README does not explain how to produce the expected chunks directory;
- the repository has not been updated since February 2023.

These observations do not invalidate the paper, but they mean the released artifact should not be described as ready to run. It will likely require debugging and reconstruction of missing steps.

GitHub does not detect a software license for this repository either.

### Compute and reproduction judgment

The paper used Python 3.7 and an NVIDIA GTX 1080 GPU. It trained for 50 epochs with a batch size of 256. A modern GPU should be enough for the released model once the environment and data pipeline work.

The main difficulty is not GPU size. It is reproducing the preprocessing, resolving old dependencies, and fixing or understanding the code inconsistencies.

**Difficulty for our team: high.**

## 3. CausalRCA

**Paper:** Ruyue Xin, Peng Chen, and Zhiming Zhao, “Causal Inference Based Precise Fine-grained Root Cause Localization for Microservice Applications,” Journal of Systems and Software, volume 203, 2023, article 111724.  
**Links:** [published article](https://doi.org/10.1016/j.jss.2023.111724) | [open paper](https://arxiv.org/pdf/2209.02500) | [repository](https://github.com/AXinx/CausalRCA_code)

### How it works

CausalRCA uses metric time series. It tries to identify both the faulty service and the metric connected to the fault.

Each node in the graph is a metric from a service. A gradient-based causal discovery model learns a weighted directed acyclic graph. An edge means that the model found a possible cause-effect relationship between two metrics. CausalRCA reverses the edges, uses their absolute weights as transition probabilities, and applies PageRank to rank the possible causes.

This graph is not the same as a service call graph from traces. It is a learned metric-level causal graph. That fits the causal-inference part of our project, but it does not directly provide the actual caller-callee topology.

### Experiment

The paper used Sock Shop on Kubernetes. Its testbed had one master and three worker virtual machines. Each VM had 4 vCPUs, 16 GB of memory, and 80 GB of storage.

Prometheus collected service latency and container metrics every five seconds. Pumba injected CPU hog, memory leak, and network delay. Each fault ran for five minutes, followed by a ten-minute cooldown.

### Results reported by the paper

| Localization task | AC@1 | AC@3 | Avg@5 |
|---|---:|---:|---:|
| Faulty service | 0.2000 | 0.5749 | 0.5815 |
| Root metric inside a known faulty service | 0.2476 | 0.7190 | 0.6681 |

The fine-grained AC@3 result was around 10% higher than the causal baselines compared in the paper. The Top-1 results are much lower than the results reported by MicroRCA and Eadro, although the experiments are not directly comparable.

### Repository check

This is the most complete GitHub repository of the three. It contains:

- training scripts for the paper's three experiments;
- baseline notebooks;
- fault data files for CPU, latency, and memory experiments across several services;
- data-collection notebooks;
- pinned Python dependencies.

The dependencies are old, including PyTorch 1.10.2, NumPy 1.20.3, and NetworkX 2.6.3. The paper says the model was trained for 1,000 epochs, while the checked repository configuration currently sets 500 epochs. That difference must be resolved before claiming an exact reproduction.

The training scripts automatically use CUDA when it is available, but a GPU requirement is not reported clearly in the paper. The learned graph becomes more expensive as the number of metric nodes grows. Running ten repetitions, as done in the paper, will add time.

No license is detected for this repository.

### Reproduction judgment

The included fault files and experiment scripts make this artifact more complete than MicroRCA and Eadro. However, the dependency age, parameter mismatch, and causal training make an exact reproduction more involved than simply running one command.

It is still a realistic candidate for a focused reproduction if we first create a clean environment and reproduce one experiment before trying the full paper.

**Difficulty for our team: medium to high.**

## Comparison

| Question | MicroRCA | Eadro | CausalRCA |
|---|---|---|---|
| Peer-reviewed venue | NOMS 2020 | ICSE 2023 | Journal of Systems and Software 2023 |
| Main input | Service latency and resource metrics | Logs, metrics, and traces | Metric time series |
| Relationship model | Runtime service/host graph | Trace-derived service graph | Learned metric causal graph |
| Ranking method | Personalized PageRank | Supervised neural classifier | PageRank on learned causal graph |
| Needs labelled training data | No | Yes | No fault-class labels for graph learning, but uses fault windows for evaluation |
| Public code | Yes | Yes | Yes |
| Data status | One example case confirmed | External Zenodo record; archive still needs validation | Multiple fault files confirmed in repository |
| Repository concerns | No pinned versions, old pandas API, hard-coded input format | Incomplete setup instructions and apparent code inconsistencies | Old dependencies and paper/code epoch mismatch |
| License detected | No | No | No |
| Reproduction difficulty | Medium | High | Medium to high |

The accuracy values cannot be compared as if all three papers ran the same test. They use different systems, fault durations, telemetry, labels, and evaluation procedures. Our final comparison must run the selected methods on the same OpenTelemetry Demo dataset.

## Decision for our project

Eadro is the best **design reference** because it uses metrics, logs, traces, and a trace-based service graph. That is close to the data we plan to collect. However, after inspecting its repository, I do not recommend selecting Eadro as our first reproduction. The released artifact needs too much debugging before we can trust an exact result.

MicroRCA is still the best **baseline candidate**, but with a condition: we should first perform a small feasibility test. The method is simple, has no neural training, uses service dependencies, and reports PR@1 and PR@3. We need to confirm that we can map OpenTelemetry trace latency and resource metrics into its expected CSV format. We should not claim that the paper is reproduced until we run that test and match at least one provided example.

CausalRCA is the best **causal-method candidate** for further investigation. Its repository includes more experimental data, and its metric-level output could help explain whether CPU, memory, or network behavior caused the incident. It is not my first baseline choice because the model is more complex and its reported service-level Top-1 accuracy is 0.20.

The practical order is:

1. Run a MicroRCA smoke test using the repository's example CSV files.
2. Document every compatibility change instead of silently changing the method.
3. Map one OpenTelemetry fault experiment into the same input structure.
4. Only after that test, ask the team to approve MicroRCA as the published baseline.
5. Keep Eadro as the architecture reference and CausalRCA as the causal alternative.

This recommendation is preliminary. It is based on paper and repository inspection, not a completed reproduction.

## Sources

- [MicroRCA paper](https://inria.hal.science/hal-02441640/document)
- [MicroRCA repository](https://github.com/elastisys/MicroRCA)
- [Eadro paper](https://arxiv.org/pdf/2302.05092)
- [Eadro repository](https://github.com/BEbillionaireUSD/Eadro)
- [Eadro dataset record](https://doi.org/10.5281/zenodo.7615393)
- [CausalRCA published article](https://doi.org/10.1016/j.jss.2023.111724)
- [CausalRCA open paper](https://arxiv.org/pdf/2209.02500)
- [CausalRCA repository](https://github.com/AXinx/CausalRCA_code)
