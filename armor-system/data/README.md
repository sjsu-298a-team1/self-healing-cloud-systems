# Data

**Status: IMPLEMENTED for ARMOR D1 (Linear 298-43 and 298-44); tested.** Raw data is never committed.

| Path | Contents |
|---|---|
| `tools/` | D1 acquisition and verification tools (`fetch_d1.py`, safe zip/pickle readers, inspection and validation). Running `fetch_d1.py` rewrites the committed files in `manifests/armor_d1/` (timestamps change): use `--manifest-dir <tmp>` or `git checkout armor-system/data/manifests` afterwards. |
| `manifests/armor_d1/` | Provenance, checksums, file inventory, label mappings and reconciliation evidence (298-43). |
| `prep/`, `pipeline.py` | CPU preparation pipeline: inspection, split manifests, preprocessing, EDA, augmentation assessment, nine-stage validation. |
| `artifacts/d1/` | Small generated outputs (about 1 MB) incl. split manifests and train-only scalers. See its `README.md`. |
| `raw/`, `processed/` | Git-ignored: the downloaded D1 release and a 28 MB feature cache. |
| `schemas/` | Empty placeholder (the schema lives in `artifacts/d1/inspection/schema.json`). |

D2 and raw telemetry are not downloaded. See `../docs/d1_data_preparation_runbook.md` for exact commands.
