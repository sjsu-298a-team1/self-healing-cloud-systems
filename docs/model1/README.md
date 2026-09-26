# Model 1 Documentation

Model 1 is a multivariate LSTM encoder-decoder autoencoder for anomaly detection,
trained on the BARO Online Boutique telemetry artifact (see `docs/baseline/README.md`
for the separate baseline reproduction this dataset is shared with).

Dataset-inspection findings: see [dataset-inspection/](dataset-inspection/).

Protocol documentation (feature list, split strategy, normalization, windowing,
labeling, evaluation metrics, success criteria): see
[protocol/protocol.md](protocol/protocol.md).

**Status: complete.** Model 1 was implemented, validated, architecture/scoring-rule
compared, and evaluated once on held-out test data; merged via
[PR #24](https://github.com/sjsu-298a-team1/self-healing-cloud-systems/pull/24). See
`experiments/model1/model1_final_summary.json` for the frozen final configuration and
results, and `experiments/model1/failure_study/` for the validation-to-test
generalization-gap analysis.
