# BARO Baseline Reproduction — Evidence

Verified local reproduction of the published baseline selected in
[docs/baseline/README.md](README.md). This is a reproduction of BARO's own
**coarse-grained root-cause service localization** result — a different task from
Model 1's anomaly-detection work (see [docs/model1/README.md](../model1/README.md)).
**The two are not numerically compared anywhere in this repository.**

Reproduced: 2026-10-03, on branch `khushi/project-evidence-cleanup`.

## Paper / table / metric

- **Paper:** Luan Pham, Huong Ha, Hongyu Zhang, "BARO: Robust Root Cause Analysis for
  Microservices via Multivariate Bayesian Online Change Point Detection," Proc. ACM
  Softw. Eng., Vol. 1, No. FSE, Article 98 (July 2024). DOI: 10.1145/3660805.
- **Table:** Table 3 — coarse-grained root-cause service localization.
- **Metric:** Avg@5 (mean of Top-1 through Top-5 service-ranking accuracy).

## Exact dataset

- BARO's own Online Boutique telemetry artifact, Zenodo record
  `10.5281/zenodo.11046533`.
- Local path used: `~/298A_project/code/baro/data/fse-ob/` — **not part of this
  repository** (gitignored, see `docs/data/README.md`).
- 100 case folders: 5 target services (`cartservice`, `checkoutservice`,
  `currencyservice`, `paymentservice`, `productcatalogservice`) × 4 fault types
  (`cpu`, `mem`, `delay`, `loss`) × 5 repeated runs = 100, confirmed by direct
  directory listing.

## Command / environment used

Run from `~/298A_project/code/baro` (unmodified upstream BARO clone — zero code
changes), using BARO's own documented reproduction command:

```bash
python main.py --dataset OnlineBoutique --fault-type cpu
python main.py --dataset OnlineBoutique --fault-type mem
python main.py --dataset OnlineBoutique --fault-type delay
python main.py --dataset OnlineBoutique --fault-type loss
python main.py --dataset OnlineBoutique --fault-type all
```

Internally this calls `baro.reproducibility.reproduce_baro(dataset="fse-ob",
fault=<type>)`, which uses `baro.root_cause_analysis.robust_scorer()` and
`baro.utility.to_service_ranks()` — confirmed by reading `main.py`'s argument
dispatch directly.

**Environment:** Python 3.11.15, pandas 2.3.3, numpy 1.26.4, scikit-learn 1.8.0
(base conda environment; verified via `python3 --version` and direct import-version
checks — this is not the `model1_torch_env` used for Model 1, since BARO's own code
needs `scikit-learn`/`requests`, not `torch`).

`git status --porcelain` on `~/298A_project/code/baro` was clean both before and
after this reproduction — no files were modified in the BARO clone.

## Reproduced result

| Fault type | Cases | Reproduced Avg@5 | Published Avg@5 (Table 3) | Match |
|---|---|---|---|---|
| cpu | 25 | 0.91 | 0.91 | exact |
| mem | 25 | 0.96 | 0.96 | exact |
| delay | 25 | 0.95 | 0.95 | exact |
| loss | 25 | 0.62 | 0.62 | exact |
| **all** | **100** | **0.86** | **0.86** | **exact** |

All 5 values reproduced **exactly** match the numbers in `code/baro/README.md`'s own
"Reproduce RQ2" section ("BARO achieves Avg@5 of 0.91, 0.96, 0.95, 0.62, and 0.86 for
CPU, MEM, DELAY, LOSS, and ALL fault types on the Online Boutique dataset").

## Artifact / code paths

- `~/298A_project/code/baro/main.py` — CLI entry point used.
- `~/298A_project/code/baro/baro/reproducibility.py::reproduce_baro()` — RCA
  evaluation loop.
- `~/298A_project/code/baro/baro/root_cause_analysis.py::robust_scorer()` — RobustScaler-based
  deviation scoring.
- `~/298A_project/code/baro/baro/utility.py::to_service_ranks()` — metric-column →
  service-level rank reduction.
- `~/298A_project/code/baro/data/fse-ob/` — dataset (local, not committed to
  `team-repo`).

## Limitations

1. **Timing methodology is BARO's own, not oracle-free.** This reproduction uses
   BARO's committed `naive_bocpd.json` per-case changepoint files exactly as BARO's
   own `reproduce_baro()` does. That changepoint file's detection window is itself
   built using the oracle `inject_time.txt` fault-injection timestamp before any
   "detection" happens (confirmed in prior session inspection work, not yet a
   committed repo artifact). This reproduction is faithful to BARO's **published**
   methodology, not a claim that the methodology is oracle-free.
2. **Different task from Model 1.** This is BARO's coarse-grained **service-level
   root-cause ranking** task over a 13-candidate set (10 application services +
   `redis`, `frontend-external`, and `main`/loadgenerator). Model 1 is a
   **window-level anomaly-detection** task. The two use different units, different
   label spaces, and different success criteria — **they are not compared
   numerically here or anywhere else in this repository.**
3. **Single-machine verification.** This reproduction has only been run on one
   contributor's machine (see `docs/planning/compute-budget-and-risks.md`, risk #3).
   It is fast (~1.6s for all 100 cases) and should be trivially reproducible by any
   teammate with the dataset, but this has not yet been independently confirmed by
   a second person.
4. **Dataset not included in CI.** Because `data/fse-ob/` is gitignored and not part
   of this repository (see `docs/data/README.md`), this reproduction cannot currently
   be re-verified automatically; it requires a teammate to have the raw dataset
   locally.
