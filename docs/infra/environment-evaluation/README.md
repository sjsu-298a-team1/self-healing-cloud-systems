# Microservice, Telemetry, and Fault-Injection Environment Evaluation

This document is for Linear issue **298-12**. I compared a few microservice environments that we can use for our self-healing cloud project. The environment needs to give us metrics, logs, traces, and service dependency information. It should also allow us to create controlled faults so that we know which service caused the incident.

This is important because our later models need real test data. For example, if the payment service fails, the checkout service may also show errors. Our root-cause model should identify payment as the original problem instead of selecting checkout only because it also reported an error.

## Environments I compared

### 1. OpenTelemetry Demo

[OpenTelemetry Demo](https://opentelemetry.io/docs/demo/), also called Astronomy Shop, is a sample shopping application made of several microservices. It includes a load generator, so it can continuously send requests through the services while we collect data.

This environment already supports the telemetry we need:

- Prometheus and Grafana can be used for metrics.
- OpenSearch can be used for logs.
- Jaeger can be used for distributed traces.
- Trace spans show which service called another service.

The official [architecture page](https://opentelemetry.io/docs/demo/architecture/) also shows the expected connections between the services. This will help us check whether the service graph created from our trace data is correct.

The biggest advantage is its built-in fault feature. We can enable faults such as high CPU usage, memory leak, service failure, payment service failure, slow requests, and queue delay. We will know which fault was enabled and which service was affected, so it gives us the ground truth needed for evaluation.

It supports both Docker Compose and Kubernetes. We can begin with Docker Compose because it is easier to set up. The full application and telemetry tools may still require a laptop with enough CPU and memory.

### 2. Google Online Boutique

[Google Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) is another shopping application with 11 microservices. Most of the services communicate using gRPC, and a Locust load generator is included.

It is a realistic microservice application and its architecture is documented. However, the local setup mainly uses Kubernetes. We can collect metrics, logs, and traces, but we would need to configure more of the observability tools ourselves or use Google Cloud Operations. It also does not include the same number of ready-to-use faults as OpenTelemetry Demo.

Google's development guide recommends at least 4 CPUs, 4 GiB of memory, and 32 GB of storage for Minikube. Docker Desktop with Kubernetes needs at least 3 CPUs, 6 GiB of memory, and 32 GB of storage. Our telemetry tools would need additional resources.

This environment could be useful later for testing our models on a different application, but it requires more setup for the first stage.

### 3. AWS Containers Retail Sample

[AWS Containers Retail Sample](https://github.com/aws-containers/retail-store-sample-app) includes UI, catalog, cart, checkout, and order services. It has a load generator and can run with Docker Compose or Kubernetes.

The services expose Prometheus metrics and OpenTelemetry traces. We can use the traces to identify the connections between services. Container logs are available, but we would still need to configure a collector and log-storage tool to search all service logs together.

AWS provides deployment options such as EKS, ECS, and App Runner. This is useful if our team decides to use AWS. For the first prototype, it also adds cloud-account setup, permissions, cost, and cleanup work. We would also need to create our own repeatable fault scenarios.

## Overall comparison

| Area | OpenTelemetry Demo | Google Online Boutique | AWS Retail Sample |
|---|---|---|---|
| Local setup | Docker Compose or Kubernetes | Mainly Kubernetes | Docker Compose or Kubernetes |
| Metrics | Included with Prometheus | Additional setup needed | Prometheus metrics available |
| Logs | OpenSearch included | Log backend needed | Log backend needed |
| Traces | Jaeger included | Additional setup needed | OTLP traces available |
| Service dependencies | Available from traces | Available from traces or service mesh | Available from traces |
| Load generator | Included | Included | Included |
| Built-in faults | Several faults available | Limited | Limited |
| Setup difficulty | Low to medium | Medium to high | Medium |

All three environments can be used for a microservice project. OpenTelemetry Demo is more suitable for us because most of the telemetry and fault setup is already included.

## Fault-injection approaches

### OpenTelemetry Demo feature flags

The built-in [feature flags](https://opentelemetry.io/docs/demo/feature-flags/) are the easiest option for our first experiments. We can turn a fault on, collect the telemetry, and then turn it off. This does not require a separate chaos-testing tool. The limitation is that these are mostly application-level faults.

### Chaos Mesh

[Chaos Mesh](https://chaos-mesh.org/docs/) is made for Kubernetes. It can kill pods or containers, create CPU and memory stress, and introduce network delay, packet loss, or network partitions.

Chaos Mesh is a good option after we move the application to Kubernetes. The experiments can be written in YAML and saved in Git, which makes them repeatable. We need to be careful with permissions and fault targets because a wrong configuration could affect more services than we planned.

### LitmusChaos

[LitmusChaos](https://docs.litmuschaos.io/docs/introduction/what-is-litmus) is another Kubernetes fault-injection platform. It supports pod failure, container failure, CPU load, memory load, and network faults. It also supports workflows and validation checks.

It has useful features, but it requires more components than we need for our first prototype. Chaos Mesh looks simpler for the Kubernetes phase.

## Faults we can test

| Fault | How we can create it | Telemetry we expect |
|---|---|---|
| CPU overload | Enable the high-CPU fault for the ad service | Increased CPU and request latency |
| Memory pressure | Enable a memory-leak fault | Increasing memory usage and possible service errors |
| Service failure | Enable a cart, product, payment, or ad service fault | Error logs, failed traces, and higher error rate |
| Dependency failure | Make the payment service unreachable | Checkout errors and failed payment calls |
| Latency | Enable a slow-request or queue-delay fault | Longer trace spans and response time |
| Service crash | Use Chaos Mesh after moving to Kubernetes | Pod restart events and upstream service errors |

We should test one fault at a time in the beginning. For each experiment, we need to save the affected service, fault type, start time, and stop time. This information will be used as the correct answer when we calculate detection time and root-cause Top-1 and Top-3 accuracy.

## Setup and resource estimate

For the first Docker Compose setup, I estimate that we will need around 4–6 CPU cores, 8–12 GiB of memory, and at least 20 GB of free storage. Running all the observability tools may work better with around 8 CPU cores and 16 GiB of memory.

A Kubernetes setup with Chaos Mesh will require more resources. We may need around 8 CPU cores, 16–24 GiB of memory, and at least 50 GB of storage. These are planning estimates because the actual usage will depend on traffic, trace sampling, and how long we store the telemetry.

If our laptops cannot run the complete setup, we can use a shared cloud VM or a small Kubernetes cluster. Before using cloud resources, we should decide the provider and set a budget limit so that unused resources do not continue creating charges.

## Risks and limitations

The first risk is resource usage. The application and telemetry tools may be too heavy for some laptops. We can start with fewer services, reduce the generated traffic, and store data only for short experiments.

Another risk is incomplete telemetry. Trace sampling may hide some service calls, or timestamps may not match across logs, metrics, and traces. We should use UTC and verify that all three types of telemetry are being collected before running a fault.

We should not inject faults into the OpenTelemetry Collector, Prometheus, Jaeger, or log-storage services during the first experiments. If the monitoring tools fail, we may lose the data needed to understand the incident.

We also need to store the fault labels separately from the data used by the models. Otherwise, the model may accidentally receive information about the correct root cause. Finally, we should pin the demo version and container images so that each team member runs the same setup.

## Recommendation

I recommend that we start with **OpenTelemetry Demo using Docker Compose and its built-in feature flags**.

It already provides the microservices, load generator, telemetry tools, service traces, and several faults needed for our project. This will allow us to spend more time collecting useful data and working on the models instead of building the complete environment from the beginning.

After the Docker Compose setup is stable, we can move the same application to Kubernetes and add **Chaos Mesh** for pod crashes, CPU and memory stress, and network faults. Google Online Boutique can be used later as a second environment if we want to check whether our models also work on another application.
