# Root-Cause and Microservice Environment Presentation Section

This is my presentation section for Linear issue **298-20**. It uses the research completed in 298-9 and the environment evaluation completed in 298-12.

## Slide 1: Microservice environment and telemetry

The first slide explains why we selected OpenTelemetry Demo for the initial prototype. It shows the load generator, application services, OpenTelemetry Collector, and the three telemetry signals we need: metrics, logs, and traces.

The slide also explains how we will record each injected fault. The experiment ID, fault type, target service, timestamps, and demo version give us the known answer for later model evaluation.

### Speaker notes

I evaluated three possible environments and recommended OpenTelemetry Demo for our first prototype. It already includes a shopping application, a load generator, and the telemetry components we need. We will begin with Docker Compose because it is easier to reproduce than Kubernetes.

For every experiment, we will activate one controlled fault and store its target service and timestamps separately. That record becomes our ground truth. We then check whether the fault appears in the metrics, logs, and traces before accepting the experiment. The main limitation is resource use, so our first runs will use short retention windows and reduced traffic.

## Slide 2: Service-graph root-cause localization

The second slide uses a payment-service failure to explain why the service dependency graph matters. Checkout and frontend may both report symptoms even when payment caused the incident.

It summarizes the three reviewed approaches:

- MicroRCA is the practical first baseline candidate.
- Eadro is the closest design reference for combining logs, metrics, traces, and service dependencies.
- CausalRCA is the main causal-method alternative.

The slide defines Top-1 and Top-3 accuracy and keeps the recommendation conditional on a successful MicroRCA smoke test.

### Speaker notes

A single service failure can create errors in several upstream services. In the example, payment fails first, but checkout and frontend also become abnormal. The root-cause model uses the dependency graph and telemetry to rank payment as the original cause.

We will measure Top-1 accuracy when the correct service is ranked first and Top-3 accuracy when it appears among the first three results. MicroRCA is the most practical first candidate because it uses graph ranking and does not need neural training. Eadro is closer to our final multimodal design, but its released code and preprocessing are harder to reproduce. CausalRCA is useful for a later causal approach.

MicroRCA must pass a smoke test before the team selects it as the published baseline.

## References

- [OpenTelemetry Demo](https://opentelemetry.io/docs/demo/)
- [MicroRCA paper](https://inria.hal.science/hal-02441640/document)
- [Eadro paper](https://arxiv.org/abs/2302.05092)
- [CausalRCA paper](https://doi.org/10.1016/j.jss.2023.111724)
- [298-12 environment evaluation](../../infra/environment-evaluation/README.md)
- [298-9 root-cause literature review](../../literature/root-cause-localization/README.md)
