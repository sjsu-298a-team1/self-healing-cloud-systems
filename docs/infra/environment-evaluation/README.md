# Microservice and Fault-Injection Environment Evaluation

This evaluation is for Linear issue **298-12**. The purpose is to choose a practical test environment for our self-healing cloud project before we spend time deploying and configuring one.

Our project needs more than a group of containers. We need an application where a request passes through several services, because one of our models will try to locate the service that originally caused an incident. We also need metrics, logs, and traces from the same experiment. Finally, we need a controlled way to introduce failures so that we know the actual root cause and can compare it with the model's prediction.

I looked at three existing microservice applications: OpenTelemetry Demo, Google Online Boutique, and AWS Containers Retail Sample. I focused on what our team could realistically run, what telemetry is already available, and how much additional work would be required for fault injection.

## Environments considered

### OpenTelemetry Demo

[OpenTelemetry Demo](https://opentelemetry.io/docs/demo/), also known as Astronomy Shop, is a sample online store built from services written in different languages. A load generator is included, so the application can continuously produce traffic without us creating a separate test client.

The main advantage for our project is that observability is the purpose of this demo. It already uses the OpenTelemetry Collector and includes tools for viewing the data: Prometheus and Grafana for metrics, Jaeger for traces, and OpenSearch for logs. The trace spans show how a request moves between services, which gives us the information needed to build a service-dependency graph. The expected application structure is also shown in the official [architecture documentation](https://opentelemetry.io/docs/demo/architecture/).

Another useful feature is its built-in failure scenarios. Feature flags can cause high CPU usage, a memory leak, service errors, an unreachable payment service, slow image requests, increased traffic, and queue delays. Since each flag has a known target, it can give us the ground truth for an experiment.

The demo can run with Docker Compose or Kubernetes. Docker Compose looks like the better place for us to begin because it removes most of the Kubernetes setup while we confirm that we can collect and save the telemetry. The disadvantage is that the full demo and observability stack may use a large amount of memory on a laptop.

### Google Online Boutique

[Google Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo) is another online-store application. It has 11 services, mostly communicating through gRPC, and comes with a Locust load generator. It is a realistic example of how a user request can depend on several backend services.

The project provides a documented service architecture, but its local setup is mainly designed around Kubernetes. Metrics, logs, and traces can be collected, although we would have to configure more of the telemetry stack ourselves or use Google Cloud Operations. We would also need to create and manage our own repeatable fault scenarios.

Google's development guide recommends at least 4 CPUs, 4 GiB of memory, and 32 GB of storage for Minikube. For Docker Desktop with Kubernetes, it recommends at least 3 CPUs, 6 GiB of memory, and 32 GB of storage. These numbers cover the application, but our observability tools would require additional resources.

This is a good application, but it introduces extra setup before we can begin collecting useful experimental data. It may be more valuable later as a second environment for checking whether our model works on an application different from the one used during development.

### AWS Containers Retail Sample

[AWS Containers Retail Sample](https://github.com/aws-containers/retail-store-sample-app) includes UI, catalog, cart, checkout, and order services along with their supporting databases. It can run through Docker Compose or Kubernetes, and it includes a load generator.

The application exposes Prometheus metrics and OpenTelemetry traces. The traces can show runtime dependencies between the services. Container logs are also available, but a collector and shared log backend would still need to be configured if we want to search the logs in one place.

AWS provides deployment options for EKS, ECS, and App Runner. This would be convenient if the team decides to use AWS, but it could also tie our first prototype to one cloud provider and add account, permission, cost, and cleanup work. The application also does not provide a fault catalog comparable to the OpenTelemetry Demo feature flags.

## Comparison

| Area | OpenTelemetry Demo | Google Online Boutique | AWS Retail Sample |
|---|---|---|---|
| Local deployment | Docker Compose or Kubernetes | Mainly Kubernetes | Docker Compose or Kubernetes |
| Metrics | Prometheus included | Requires additional configuration | Prometheus metrics available |
| Logs | OpenSearch included | Collector and backend required | Collector and backend required |
| Traces | Jaeger included | Requires additional configuration | OTLP traces available; backend required |
| Service relationships | Visible through traces and documented architecture | Visible through traces or a service mesh | Visible through traces |
| Traffic generation | Included | Included | Included |
| Ready-made faults | Several feature-flag scenarios | Limited | Limited |
| Setup effort for our project | Low to medium | Medium to high | Medium |

The three applications are all suitable for demonstrating microservice behavior. The difference is how quickly they can give us usable telemetry and labelled failure data. OpenTelemetry Demo requires the least work in both areas.

## Fault-injection options

The simplest option is to begin with the [feature flags included in OpenTelemetry Demo](https://opentelemetry.io/docs/demo/feature-flags/). They cover several failures we already planned to evaluate, and we can turn them on and off without adding a separate chaos platform. This is enough for early data collection, although the flags mostly represent application-level failures.

[Chaos Mesh](https://chaos-mesh.org/docs/) is a stronger option once we move to Kubernetes. It can kill pods or containers, create CPU and memory stress, and introduce network delay, packet loss, or partitions. Its experiments are described in YAML, so the exact settings can be kept in Git and repeated. The main concern is safety: an incorrectly scoped experiment could affect more workloads than intended. We would need a separate test namespace, labels that select only the target service, and short experiment durations.

[LitmusChaos](https://docs.litmuschaos.io/docs/introduction/what-is-litmus) provides similar Kubernetes experiments and supports workflows and validation probes. It is useful for managing a larger chaos-testing program, but its additional services and ChaosCenter interface appear heavier than what we need for the first prototype. I do not see a clear reason to choose it over Chaos Mesh at this stage.

## Faults we can use in the prototype

We should start by running one fault at a time. This will make it easier to label the data and understand whether an alert came from the original failure or from a downstream service.

| Fault | Initial way to create it | Evidence we should collect |
|---|---|---|
| CPU overload | High-CPU flag on the ad service | CPU metric, request latency, and traces through the ad service |
| Memory pressure | Memory-leak flag on the email or recommendation service | Memory growth, garbage-collection activity, and service errors |
| Service error | Cart, product, payment, or ad failure flag | Error logs, error-rate metric, and failed spans |
| Dependency failure | Make the payment service unreachable | Checkout errors and failed calls from checkout to payment |
| Latency | Slow-image or queue-delay flag | Longer span durations and slower end-to-end requests |
| Service crash | Chaos Mesh PodChaos in the Kubernetes phase | Restart events, availability change, and upstream errors |

For every experiment, we should record the affected service, fault type, start time, stop time, and expected dependency path. These records will become the ground-truth labels used for detection time and Top-1/Top-3 root-cause accuracy.

## Resource estimate

The exact resource use will depend on traffic, sampling, and how long we retain the telemetry. For planning, I would allow approximately 4–6 CPU cores and 8–12 GiB of memory for an initial Docker Compose setup. Running the complete observability stack comfortably may require around 8 cores and 16 GiB of memory. A local Kubernetes setup with the application, telemetry tools, and Chaos Mesh may need 16–24 GiB of memory.

If laptop resources are not enough, we can use a small shared cloud VM or Kubernetes cluster. We should not estimate a fixed cloud price until the provider, region, machine size, storage, and experiment schedule are decided. Any cloud deployment should have a budget alert and a cleanup plan.

## Risks we need to manage

The largest immediate risk is that the full environment may be too heavy for the computer running it. We can reduce that risk by starting with Docker Compose, keeping experiments short, reducing traffic, and limiting telemetry retention.

There are also experimental risks. Trace sampling could hide a dependency, clocks could be misaligned, or the fault could interrupt the telemetry collector itself. Before injecting any fault, we should verify that metrics, logs, and traces use UTC timestamps and reach their storage backends. The collector and storage services should never be included as fault targets during the first experiments.

We also need to keep the fault labels separate from the telemetry given to a model. Otherwise, the model could indirectly receive the correct answer. Finally, we should pin the application version, container images, and experiment configuration so that a later run uses the same environment.

## Recommendation

My recommendation is to start with **OpenTelemetry Demo using Docker Compose and its built-in feature flags**.

This choice gives us the shortest path to the data our project actually needs. The application, traffic generator, metrics, logs, traces, dashboards, and several controlled faults are already available in one project. Instead of spending the first part of 298A assembling infrastructure, we can first confirm that the collected signals are useful for incident detection and root-cause localization.

Once that setup is stable, we can deploy the same application on a local or small cloud Kubernetes cluster and add **Chaos Mesh** for pod, resource, and network failures. Google Online Boutique can later serve as a second application if we want to test whether the models generalize beyond the OpenTelemetry Demo.

The first practical test should be small: run normal traffic, save a short period of healthy telemetry, enable one known fault, and confirm that its effect appears in at least two telemetry signals. If that works consistently, the team will have a reliable starting point for the later model and benchmark tasks.
