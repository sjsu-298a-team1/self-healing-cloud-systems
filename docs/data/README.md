# Data Documentation

General data-related documentation for the BARO Online Boutique artifact used by
Model 1 and the baseline reproduction. Dataset-inspection scripts, generated
summaries, and findings live under `scripts/model1/dataset_inspection/`,
`data/model1/dataset_inspection/`, and `docs/model1/dataset-inspection/`
respectively.

## Source

The dataset is BARO's own Online Boutique artifact:

- **Paper's code repository:** https://github.com/phamquiluan/baro
- **Data artifact (Zenodo record):** 10.5281/zenodo.11046533
- Within that artifact, the directory used by every script in this repo is
  `data/fse-ob` (referred to below and throughout the codebase as
  `<BARO_DATA_DIR>`).

## Obtaining the data

1. Download the artifact from the Zenodo record above (or clone
   `github.com/phamquiluan/baro` and follow its own instructions for obtaining
   `data/fse-ob`).
2. Extract it somewhere on your machine -- **not** inside this repository.
   `.gitignore` already excludes any `data/**/fse-ob/` or `data/**/raw/` path, and
   no script requires the data to live inside this repo.
3. Note the local path to the extracted `fse-ob` directory -- this is your
   `<BARO_DATA_DIR>`.

## Expected directory structure

```
<BARO_DATA_DIR>/<service>_<fault_type>/<run_id>/
    data.csv           # raw, 427 columns, untouched Prometheus/istio scrape names
    simple_data.csv    # the file every script in this repo actually reads
    inject_time.txt    # single Unix timestamp: fault injection time for this case
    plot.png
    postprocess.log
    birch.json, nsigma.json, spot.json, naive_bocpd.json,
    robust_bocpd.json, univariate_bocpd.json, bocpd_time.json
        # BARO's own baseline-algorithm outputs -- not ground-truth labels
```

100 case folders total: 5 target services × 4 fault types (`cpu`, `mem`, `delay`,
`loss`) × 5 repeated runs each. Full details (column counts, timestamp format,
sampling rate, missingness) are in
[docs/model1/dataset-inspection/findings.md](../model1/dataset-inspection/findings.md).

## Passing `<BARO_DATA_DIR>` to scripts

Every script that reads the dataset takes it as a `--data-dir <BARO_DATA_DIR>`
command-line argument -- never a hardcoded path. For example:

```bash
python3 scripts/model1/dataset_inspection/inspect_dataset.py --data-dir /path/to/fse-ob --out-dir data/model1/dataset_inspection
```

See [docs/model1/dataset-inspection/commands.txt](../model1/dataset-inspection/commands.txt)
for the exact dataset-inspection commands, and
[docs/model1/protocol/protocol.md](../model1/protocol/protocol.md) for the full
protocol-validation and training/evaluation pipeline.
