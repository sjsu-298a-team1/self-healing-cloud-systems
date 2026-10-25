# old/ — archived DATA 298A implementation

This directory holds the complete previous project (LSTM autoencoder + BARO Online Boutique direction), moved with `git mv` so history is preserved (use `git log --follow`). File contents were not modified.

## Snapshot

- Git tag: `pre-armor-migration-2026-10-28` (annotated)
- Tagged commit: `31ffc3739e317eda3a828af2593b53479da53424` (merge of PR #32, the tip of `main` before migration)
- Restore the original runnable version: `git checkout pre-armor-migration-2026-10-28`

## Original path → archived path

| Original | Archived |
|---|---|
| `README.md` | `old/ORIGINAL_ROOT_README.md` |
| `requirements.txt` | `old/requirements.txt` |
| `models/` | `old/models/` (LSTM autoencoder) |
| `scripts/` | `old/scripts/` |
| `configs/` | `old/configs/` |
| `data/` | `old/data/` (inspection outputs, split manifests, EDA; no raw data) |
| `experiments/` | `old/experiments/` (runs, summaries, failure study) |
| `tests/` | `old/tests/` |
| `docs/` | `old/docs/` (abstract, baseline incl. BARO reproduction, Checkpoint 1, literature, presentations, model designs, team meeting 1) |

## Caveats

- The archived code uses relative `sys.path` hops and repo-root-relative paths, so it is **not expected to run from `old/`**. Check out the tag to run it.
- Model checkpoints and raw data were never committed (`.gitignore`). They were backed up outside the repository at migration time and are not recoverable from Git. The frozen candidate B checkpoint has SHA-256 `52a7f93400995f1166bee9989f210072e32f1842cdb88825b0943c3cb208b847`, matching `old/experiments/model1/model1_final_summary.json`.
- The BARO reproduction in `old/docs/baseline/` ran from an external clone; no reproduction script is in this repository.
- Documents here describing SMD, CausalRCA or the LSTM + BARO plan reflect the previous direction.
