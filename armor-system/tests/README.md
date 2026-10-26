# Tests

**Status: IMPLEMENTED for the D1 work; 72 tests, all passing at the time of the last recorded run (see `data/artifacts/d1/evidence/evidence.json`).**

| Directory | Covers |
|---|---|
| `data/` | D1 acquisition tools (safe zip/pickle readers, checks, label reconciliation) |
| `prep/` | splits, preprocessing, validation detectors, and checks on the committed artifacts |
| `dashboard/` | headless render of every dashboard page |

Run: `for s in data prep dashboard; do .venv/bin/python -I -m unittest discover -s armor-system/tests/$s -p 'test_*.py'; done`. No tests exist yet for Airflow, baselines or models.
