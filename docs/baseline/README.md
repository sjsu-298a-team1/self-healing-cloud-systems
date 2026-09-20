# Published Baseline

- **Selected published baseline:** BARO.
- **Paper:** Luan Pham, Huong Ha, Hongyu Zhang, "BARO: Robust Root Cause Analysis for
  Microservices via Multivariate Bayesian Online Change Point Detection," Proc. ACM
  Softw. Eng., Vol. 1, No. FSE, Article 98 (July 2024). DOI: 10.1145/3660805.
- **Code:** https://github.com/phamquiluan/baro
- **Dataset:** BARO original Online Boutique artifact. Zenodo record: 10.5281/zenodo.11046533.
- **Published reproduction target:** Table 3, coarse-grained root-cause service
  localization, Online Boutique column, Avg@5 = 0.86.
- BARO baseline reproduction is separate from the four project models (multivariate
  time-series anomaly detector; service-graph root-cause localization model; LLM
  diagnosis and remediation-plan generator; action-risk classifier).

See `docs/model1/` for Model 1 (multivariate LSTM encoder-decoder autoencoder)
implementation, which uses the same BARO Online Boutique dataset but is a distinct
work item from the baseline reproduction above.
