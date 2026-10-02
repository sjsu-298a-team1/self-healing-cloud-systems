# Reproducible Online Boutique EDA — 298-38

Start with [findings and figures](findings.md). This adds descriptive evidence to the frozen Model 1 pipeline based on main commit `0d2c88c` (PR #27).

## Data and provenance

Use the extracted `fse-ob` directory, with `<service>_<fault>/<run>/simple_data.csv` and `inject_time.txt` underneath it. The [team Drive folder](https://drive.google.com/drive/folders/1Q9eYQq-Gd6DdpCXLn4Cc5n8N-6xAqU_W) contains a private team archive and a README identifying [BARO's official Zenodo artifact](https://doi.org/10.5281/zenodo.11046533) as its source. These outputs were generated from the official `fse-ob.zip`, whose MD5 was checked against Zenodo metadata. The team ZIP itself was not used or asserted byte-identical. Raw data must stay outside git.

Per-file SHA256 hashes of the 60 training CSVs and injection timestamp files, package versions, selected examples, and aggregate results are in [summary.json](../../../data/model1/eda/summary.json). Reproduction requires the same raw inputs and frozen repository configuration.

## Reproduce

From the repository root, with Python 3.11 or newer:

```bash
python -m venv /tmp/model1-eda-env
source /tmp/model1-eda-env/bin/activate
python -m pip install numpy==2.3.5 pandas==2.2.3 matplotlib==3.10.8
python scripts/model1/eda/build_eda.py --data-dir /absolute/path/to/fse-ob
```

For a separate output directory:

```bash
python scripts/model1/eda/build_eda.py --data-dir /absolute/path/to/fse-ob --output-root /tmp/model1-eda-rerun
```

The script reads the committed train/val/test manifests to assert separation, but opens telemetry only for the 60 training cases. All-case coverage and missingness come from committed inspection CSVs. Distribution statistics, correlations and extreme values use only times strictly before injection: 360 rows per training case, 21,600 total. Only the four explicitly selected training timelines include post-injection observations. Existing `dataset.apply_scaler` supplies the frozen training-mean imputation and scaling for correlation, timeline and extreme-value calculations; raw distributions omit missing observations.

## Figure design

The nine main figures use a consistent 1920 × 1080 layout, descriptive titles, plain service labels, and larger text. Missingness, distributions, and extreme-value views are split into separate figures to avoid crowded panels. The correlation summary displays the six strongest pairs with direct values; the complete 55-feature matrix remains a separate technical appendix. Full feature names and all values remain in the CSVs. Plotting helpers are in `scripts/model1/eda/plot_style.py`.

## Artifact index

| Evidence | Figure | Machine-readable output |
|---|---|---|
| 5 services × 4 faults × 5 runs | [Coverage](figures/01_coverage.png) | [coverage.csv](../../../data/model1/eda/coverage.csv) |
| Raw missingness across 100 cases | [By feature](figures/02_missingness.png), [by case](figures/02b_missingness_cases.png) | [By feature](../../../data/model1/eda/missing_by_feature.csv), [by case](../../../data/model1/eda/missing_by_case.csv) |
| CPU, memory, latency, tails and constants | [Cart distributions](figures/03_distributions.png), [additional distributions](figures/03b_distributions_additional.png) | [All-feature statistics](../../../data/model1/eda/feature_statistics.csv) |
| All 55 common features | [Strongest pairs](figures/04_correlations.png), [full matrix](figures/04b_full_correlation_matrix.png) | [Matrix](../../../data/model1/eda/correlations.csv), [pairs](../../../data/model1/eda/correlation_pairs.csv), [low-correlation signals](../../../data/model1/eda/low_correlation_signals.csv) |
| CPU/memory/delay/loss training examples | [Timelines](figures/05_injection_timelines.png) | [Timeline summary](../../../data/model1/eda/timeline_summary.csv) |
| Descriptive frozen-scaler extreme values | [By feature](figures/06_extreme_values.png), [by service group](figures/06b_extremes_by_service.png) | [By feature](../../../data/model1/eda/extremes_by_feature.csv), [by case](../../../data/model1/eda/extremes_by_case.csv) |

## Verification

- Re-ran with only the 60 training case directories present: no validation or test raw telemetry was available. All 22 generated files matched the original run byte for byte.
- Confirmed 100 structurally covered cases, 2,630 missing cells, 21,600 known-normal training rows and 55 features.
- Reproduced the existing demo's 2,596 cells with `|z| > 5`; these affect 4.51% of known-normal training rows. This is a descriptive cutoff, not the model's anomaly threshold.
- Checked SHA256 hashes before/after processing: every input file read remained unchanged.
- Inspected all ten figures, including the fully labeled correlation appendix. The top-pairs figure is the more readable presentation view.

No scaler, features, preprocessing, splits, seed, model, threshold, labels, or evaluation artifacts are changed. No training or evaluation is run. The 360-second boundary marks injection; a fault-end timestamp is not available. Pooled correlations are associations, and the four training examples do not establish general fault effects. Review and merge of the linked PR are required before the Linear issue is Done.
