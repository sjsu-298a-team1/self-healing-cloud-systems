# START HERE

Onboarding index for the DATA 298A Team 1 repository. Every row says whether something is **implemented and run**, **documented only**, or **not available**. Commands marked *run* were executed in a fresh clone with a fresh virtual environment on macOS (Python 3.14) while writing the readiness audit; nothing here has been run on Linux or a GPU.

## What exists today

| Area | State | Where |
|---|---|---|
| ARMOR D1 acquisition and integrity evidence | Implemented, tested | `armor-system/data/tools/`, `armor-system/data/manifests/armor_d1/`, `armor-system/docs/d1_validation_report.md` |
| D1 preparation pipeline (inspection, split manifests, train-only preprocessing, EDA, validation) | Implemented, tested, deterministic | `armor-system/data/pipeline.py`, `armor-system/data/prep/`, `armor-system/data/artifacts/d1/` |
| Approved Model 1 case split 101 / 25 / 84 | Implemented, tested (validation has one Node Memory case: unstable) | `armor-system/data/artifacts/d1/splits/model1_split_101_25_84_v1.json` |
| Streamlit dashboard (7 pages) | Implemented, tested, browser-checked | `armor-system/dashboard/` |
| ARMOR baseline reproduction | **Not available** (no run has been performed; no baseline scripts) | `armor-system/baselines/` is empty |
| Model 1 (multimodal Transformer) | **Not available** (no specification, code or weights) | `armor-system/models/model1_transformer/` is empty |
| Evaluation harness | **Not available** (metric definitions are documented only) | `armor-system/evaluation/` is empty |
| Airflow, backend, frontend, deployment | **Not available** (empty folders; cloud provider undecided) | `armor-system/airflow|backend|frontend|deployment/` |
| GPU environment and collaboration rules | **Not available** | not documented anywhere |

Full assessment, open decisions and predicted questions: [`armor-system/docs/team_handoff_readiness_audit.md`](armor-system/docs/team_handoff_readiness_audit.md).

## Set up (CPU, tested)

```bash
git clone https://github.com/sjsu-298a-team1/self-healing-cloud-systems.git && cd self-healing-cloud-systems
python3 -m venv .venv
.venv/bin/python -m pip install -r armor-system/dashboard/requirements.txt
python3 -I armor-system/data/tools/fetch_d1.py                 # D1 only (62 MB); never D2; rewrites armor-system/data/manifests/armor_d1/ (run `git checkout armor-system/data/manifests` afterwards)
.venv/bin/python armor-system/data/pipeline.py --stage quality  # nine-stage validation; regenerates artifacts byte-identically
armor-system/dashboard/run_dashboard.sh                         # http://localhost:8501
```

Without the D1 release the pipeline stops with a clear message. `fetch_d1.py` itself was run during Linear 298-43; it was not re-run in the audit clone to avoid downloading again. Exact commands and troubleshooting: `armor-system/docs/d1_data_preparation_runbook.md`.

## Who works on what (approved)

- Khushi + Bhoomika: Model 1 (multimodal Transformer).
- Bhoomika: Airflow and cloud pipeline.
- Three other teammates: ARMOR baseline reproduction.

## Workflow rules (verified on GitHub)

- Work on a branch named from the Linear issue (Linear shows `gitBranchName`), open a PR to `main`. Ruleset "Protect main": 1 approving review and resolved review threads are required; direct pushes, force-pushes and deletion of `main` are blocked; no bypass actors. There are **no CI checks** (no GitHub Actions), so run the tests locally.
- Never commit raw data, checkpoints (`*.pt`, `*.pth`, `*.ckpt`, `*.safetensors`, `*.bin`), `.env`, keys or credentials. The repository is **public**. Note that `*.pkl` (e.g. ARMOR's `model.pkl`) is not ignored outside `armor-system/data/raw/`.
- Do not edit anything under `old/` (archived history).

## Key references

ARMOR paper [arXiv 2603.25538](https://arxiv.org/abs/2603.25538) - official artifacts [Zenodo 21744694](https://zenodo.org/records/21744694) - D1 origin [ART repo](https://github.com/bbyldebb/ART) - Linear: [298-43](https://linear.app/298a-team-1-self-healing-cloud/issue/298-43/acquire-and-validate-armor-d1-benchmark-dataset), [298-44](https://linear.app/298a-team-1-self-healing-cloud/issue/298-44/complete-armor-d1-data-preparation-eda-validation-and-streamlit).
