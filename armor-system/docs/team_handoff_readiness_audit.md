# Team handoff-readiness audit

Audit of the repository for the team's next phase: ARMOR baseline reproduction, Model 1 (multimodal Transformer) and Airflow/cloud. It is a readiness audit only: no GPU work, no ARMOR run, no Model 1 or Airflow implementation was started, and no D2 or raw telemetry was downloaded.

Approved responsibilities (unchanged): Khushi + Bhoomika - Model 1; Bhoomika - Airflow and cloud pipeline; three other teammates - ARMOR baseline reproduction.

Evidence vocabulary used throughout: **Implemented** (code or files exist), **Documented** (written down, may be untested), **Tested** (an automated test or a recorded run exercised it), **Not available** (does not exist). A claim is only called verified when a command or file named here shows it.

## 1. Method and limits

Inspected: every tracked file outside `old/` (313 tracked files in total), root and sub-READMEs, `.gitignore`, the GitHub ruleset and repository settings (`gh api`), Linear issues (read only), Zenodo/PyTorch/DGL/ART URLs (HTTP HEAD only, nothing downloaded), ARMOR's source and configs (the copy fetched in Linear 298-43).

Executed: a **fresh-clone test** of this branch. A fresh clone, a fresh virtual environment from `armor-system/dashboard/requirements.txt` (numpy 2.5.3, scipy 1.18.1, matplotlib 3.11.2, pandas 3.0.6, streamlit 1.66.1, plotly 7.1.0; Python 3.14, macOS arm64), the existing D1 release linked in, then `pipeline.py --stage quality`. Results: the pipeline stopped with a clear message before the data were linked (this exposed a traceback bug, fixed here); after linking, 9/9 stages and 52/52 checks passed and **every regenerated artifact was byte-identical to the committed one** (`git status` clean apart from my test symlink); the three test suites passed there (37, 30 and 5 tests). Not executed: `fetch_d1.py` in the clone (it would download 62 MB again; it was run and verified in 298-43), anything on Linux, anything on a GPU, ARMOR itself.

## 2. Readiness verdicts

| Workstream | Verdict | Why, in one line |
|---|---|---|
| General GitHub/repository | **PARTIALLY READY** | D1 data layer, tests, runbook and dashboard are solid; no CI, no CONTRIBUTING/PR template, no top-level setup for non-D1 work, and PR #35 (which carries all of it) is not yet on `main`. |
| ARMOR baseline | **PARTIALLY READY** | D1 and ARMOR's code/config can be fetched and verified; the checkpoint fetch, data placement, Linux GPU environment, run/compare scripts and evidence conventions are not provided, and nothing has ever been run. |
| Model 1 | **PARTIALLY READY** (data and preprocessing contracts **READY**; model specification and detection-head training **BLOCKED**) | Split, schema, scaler, tensors, indicators and windows exist and are tested; there is no architecture spec, no approved detection target without incident durations, no evaluation harness, no GPU/experiment conventions. |
| Airflow and cloud | **BLOCKED** | Folders are empty; cloud provider, storage, credentials policy and budget are undecided, and the course demo must be cloud-deployed. A local Airflow dev environment could start without these decisions. |
| GPU collaboration | **BLOCKED** | Nothing is defined (hardware, drivers, reservation, storage); this needs team coordination, not just documentation. |

## 3. What exists (implemented / documented / tested)

| Item | Implemented | Documented | Tested | Where |
|---|---|---|---|---|
| D1 acquisition, checksums, safe zip/pickle readers | yes | yes | 37 tests (298-43) + recorded run | `armor-system/data/tools/`, `manifests/armor_d1/` |
| Label reconciliation (203 shared / 21 AD-only / 7 case-only) | yes | yes | tests | `label_reconciliation.csv/.json`, report section 9 |
| Split manifests (official 126/84, approved 101/25/84, rejected 100/26/84) | yes | yes | tests + 9-stage validation | `armor-system/data/artifacts/d1/splits/` |
| Train-only preprocessing, indicators, windows, `prepare_window` | yes | yes | unit tests + validation | `armor-system/data/prep/preprocess.py`, `preprocessing/` |
| EDA (11 items), augmentation assessment (not adopted) | yes | yes | artifact tests | `eda/`, `docs/d1_augmentation_assessment.md` |
| Nine-stage validation, 16 corruption cases | yes | yes | recorded run: 9/9, 52/52, 16/16 | `quality/nine_stage_validation.json` |
| Streamlit dashboard | yes | yes | 5 render tests + browser check (7 pages, 26 interactive steps, 0 errors) | `armor-system/dashboard/`, `evidence/dashboard_browser_check.json` |
| Reproducibility | yes | yes | two fresh-process runs identical (48 files hashed); fresh-clone regeneration identical | `evidence/evidence.json`, section 1 |
| ARMOR baseline scripts, Model 1 code, evaluation harness, Airflow DAGs, backend, frontend, deployment, shared configs | **no** | one-line "planned" READMEs | no | scaffolding only |

Counting units used by the pipeline (never added together): a **case** is one injection record (210); a **sample** is one minute of 46 x 130 features (7,200); a **window** is 7 consecutive samples lying inside one split; an **AD event** is one timestamp in `ad_cases.pkl` (224; 98 scored after the AD boundary). Approved Model 1 counts (cases / samples / 7-step windows): train 101 / 3,445 / 3,427, validation 25 / 875 / 869, test 84 / 2,880 / 2,868 (`preprocessing/split_counts_by_unit.csv`). Normal pretraining samples (from `train_samples.pkl`) per period: train 1,847, validation 421, test 1,446.

## 4. Audit A - general repository

| Check | Finding |
|---|---|
| Root README | Was stale (said no dataset work existed). **Fixed**: now states what is implemented, links the paper, Zenodo, ART and Linear, and points to `START_HERE.md`. |
| Entry point / onboarding | `START_HERE.md` created (this audit). Sub-READMEs for `data`, `tests`, `docs`, `baselines` corrected; `airflow`, `models`, `evaluation`, `backend`, `frontend`, `deployment`, `configs` remain one-line "planned" placeholders (accurate). |
| Fresh-clone setup | Tested for D1 data prep, the dashboard and the tests (section 1). Fresh clones contain only `README.md`, `START_HERE.md`, `armor-system/`, `old/`. The leftover local folders on Khushi's machine (`app`, `docs`, `experiments`, `models`, `scripts`, `tests`, `isa_*`) are untracked and ignored; they do not exist for teammates. |
| Dependencies | Only `armor-system/dashboard/requirements.txt` (top-level pins, no lock, no hashes, transitive packages float). `old/requirements.txt` is archived. There is no requirements file for ARMOR (needs Python 3.9), Model 1 or Airflow. |
| Branching and PR workflow | Ruleset "Protect main" (active, no bypass actors): 1 approving review, review-thread resolution required, force-push and deletion blocked. `dismiss_stale_reviews_on_push` and `require_last_push_approval` are **off**, so a later push does not invalidate an approval automatically. All three merge methods are allowed. **No GitHub Actions workflows (no CI)**, no CODEOWNERS, no PR template, no CONTRIBUTING. Linear provides branch names (`gitBranchName`). |
| Dataset download and checksums | `fetch_d1.py` (tested in 298-43). Gap: it rewrites the committed manifests (new timestamps), so a teammate who runs it gets a dirty tree. Documented in `START_HERE.md` and `data/README.md`; a safer default is a fix Claude can make. |
| Local vs committed artifacts | Convention exists: small generated outputs under `armor-system/data/artifacts/d1/` are committed; `data/raw/` and `data/processed/` are ignored. No convention for baseline or model outputs. |
| Shared configuration | None beyond `preprocessing/preprocessing_config_v1.json`; `armor-system/configs/` is empty. |
| Security and secrets | `.gitignore` covers `.env`, `.env.*`, `*.pem`, `*.key`, `credentials*.json`, `.streamlit/secrets.toml`, checkpoints `*.pt/*.pth/*.ckpt/*.safetensors/*.bin`. **The repository is public.** Gaps: `*.pkl` is not ignored (ARMOR's `model.pkl` or a `res/` folder outside `data/raw/` would be committable), no `.env.example`, no written secret-handling or cloud-credential guidance. |
| Links | Paper, Zenodo, ART and Linear links added to the root README and `START_HERE.md`. D2 licensing conflict is recorded in the 298-43 report. |
| Broken commands / paths | Found and fixed: pipeline traceback when D1 is missing; stale READMEs. No absolute `/Users/...` paths are tracked outside `old/`. Remaining: ARMOR's own README says to `unzip data/D2.zip` too (D2 is deliberately not downloaded, so that step fails harmlessly). |

## 5. Audit B - ARMOR baseline team

Facts verified from files and URLs:

- Official code, configs and data: Zenodo 21744694, `ARMOR.zip` (174,195,955 B). `fetch_d1.py` saves `ARMOR/data/D1.zip` plus 15 small code/config/README files to `armor-system/data/raw/armor_zenodo_21744694/ARMOR/` (ignored). It deliberately skips D2 and `ARMOR/res/`.
- Released checkpoint: `ARMOR/res/D1/20260113_101332/model.pkl` (15,016,756 B; CRC32 `82aebfc7`, listed in `manifests/armor_d1/outer_archive_listing.csv`) with the authors' outputs beside it (`res.json`, `tmp/*`). It was **not** fetched.
- ARMOR's stated environment: Python 3.9, PyTorch 1.12.1+cu116, scikit-learn 1.1.2, DGL 0.9.0 (CUDA 11.6 conda package), plus unpinned pandas, pyyaml, xgboost, matplotlib (and tqdm, used in code). Download links checked with HTTP HEAD on 2026-10-25: PyTorch cu116 wheel (about 1.9 GB) and the DGL conda package (about 215 MB) are both reachable.
- Run entry point: `python main.py --dataset D1 [--run-id <dir under res/D1>]` after unzipping `data/D1.zip` into `ARMOR/data/`. If the run directory has `model.pkl` it is loaded; otherwise it trains (1000 epochs, batch 4). **Without `--run-id`, `main.py` silently picks the newest run with a `model.pkl`, or trains** (`main.py:71-84`).
- Randomness: `grep` finds no seed anywhere in ARMOR's training code; SPOT uses unseeded `np.random`. Training reproduction will vary run to run; checkpoint evaluation may also vary slightly (SPOT) - not measured.
- Device: `device = "cuda" if available else "cpu"` for training; the checkpoint is a pickled model object loaded with `pickle` (arbitrary-code risk; use an isolated environment and only the official file). Whether it loads on CPU-only machines is **unverified**.
- Published numbers to compare against (ARMOR paper v3 Table 1, D1): AD precision 0.925 / recall 1.0 / F1 0.961; FT precision 0.946 / recall 0.941 / weighted F1 0.938; RCL Top1 0.821, Top3 0.941, Avg@5 0.910. The authors' released `res.json` agrees (AD 0.9245/1.0/0.9608; FT 0.9464/0.9405/0.938; RCL Top@1..5 0.8214, 0.8929, 0.9405, 0.9405, 0.9524, avg 0.9095). These are the authors' outputs, **not** an independent reproduction.
- Protocol facts the baseline team must preserve (verified from code and documented in `d1_validation_report.md`, sections 5 and 9): AD splits at 60% of samples (2022-05-06T16:00:00Z) and scores only 98 post-split `ad_cases.pkl` events with +/-300 s overlap matching; FT and RCL use `cases.csv` order (first 126 / last 84); the paper describes a case-based cutoff while the AD code is sample-based.

| Capability | Status |
|---|---|
| 1. Clone repository | Ready (tested). |
| 2. Obtain D1 | Ready: `fetch_d1.py` (D1 only). Extra step not scripted: unzip `ARMOR/data/D1.zip` into `ARMOR/data/` (ARMOR README step). |
| 3. Isolated Linux GPU environment | **Not available**: no environment file, Dockerfile or instructions beyond ARMOR's own README; GPU/driver compatibility unverified (section 8). |
| 4. Locate ARMOR source and checkpoints | Source: fetched copy exists locally (ignored); not placed under `armor-system/baselines/armor/`. Checkpoint: **no fetch script**; policy decision needed. |
| 5. Run released checkpoint | **Never attempted.** Command above is ARMOR's own and untested here. |
| 6. Evaluate AD, FT, RCL | Done inside `main.py`; outputs `res.json`. No wrapper or comparison script. |
| 7. Preserve official protocols | Documented (report sections 5, 9.4); our pipeline never alters official files. |
| 8. Record metrics vs Table 1 | Expected values listed above; no template or script for recording. |
| 9. Training reproduction | Config exists (`config/D1.yaml`); duration, hardware needs and variance unknown; unseeded. |
| 10. Evidence without large files | No convention: `.gitignore` ignores `armor-system/{experiments,outputs,runs}/` but not `*.pkl` or `res/`. |

Unresolved decisions for the baseline workstream: whether baseline teammates may fetch the released checkpoint (and the trust model for the pickle), which machines and CUDA stack to use, where evidence is stored, and whether to also attempt training (cost/time unknown).

## 6. Audit C - Model 1 team

| Needed | Status |
|---|---|
| Approved 101/25/84 split manifests | **Implemented, tested**: `splits/model1_split_101_25_84_v1.json` (status `approved`, hard checks pass, content hash verified in validation stage 5). Validation holds a **single Node Memory case**; Node Memory has 4 train and 4 test cases, so its metrics are statistically unstable. |
| Stable feature schema and modality order | **Implemented, tested**: `inspection/schema.json` (46 nodes x 130 channels; metric 110 / trace 9 / log 11; order fingerprints). |
| Preprocessing and scaling contract | **Implemented, tested**: `preprocessing_config_v1.json` (hash `e9aa3ccc776a...`), train-only per node-channel scaler fit on samples before the 101|25 boundary only, structural-absence handling, no feature selection. |
| Input tensors and masks | **Implemented**: window `inputs (6, 46, 130)`, `target (46, 130)`, `structural_absent (46, 3)`, `observed_all_zero_not_structural (6, 46, 3)` float32/uint8 (`prepare_window`; example in `prepared_example.json`). Not defined: training-time modality-dropout masks (ARMOR applies its own; Model 1 policy for simulated vs structural absence is not specified). |
| Self-supervised pretraining requirements | **Partly documented**: normal pool 1,847 samples before the validation boundary (strict chronological primary), whole-pool 3,714 as a sensitivity run (decision in 298-43); the 161 uncertain samples are all after the AD boundary. Not specified: pretext task, masking ratios, schedule. |
| Transformer architecture specification | **Not available.** |
| Detection and five-class objectives | Documented only as intent (README, 298-43 report): five-class labels are reconstructable from `cases.csv`; **detection supervision is undefined** because no incident durations exist and sample-level labels must not be invented. |
| Policy for unresolved detection labels | Documented: `cases.csv` authoritative; 21 AD-only events uncertain (masked from negatives); `ad_cases.pkl` kept for reproduction. No approved rule for constructing the detection target. |
| Event-level and fault-type evaluation | Documented: event-level F1 via ARMOR's matching (98 and 84 populations, scored separately, FP intervals and coverage reported); macro-F1 and weighted-F1. **No implemented harness** (`armor-system/evaluation/` is empty). |
| Validation and threshold selection | **Not available.** Validation is tiny (25 cases) and should not alone drive thresholds or per-class tuning. |
| GPU environment | Not available (section 8). |
| Checkpoint and experiment conventions | Only ignore rules for `armor-system/{experiments,outputs,runs}/`, `mlruns/`, `wandb/`; no naming scheme, config format or storage location. |
| Interfaces with inference services | Not available (`backend/` is empty); no tensor/JSON contract for serving. |

Smallest decisions that unblock real work: (1) detection target definition (for example event-proximity labels from `cases.csv` using ARMOR's [-59, +300) s case window, or an event-level, label-free detector scored with ARMOR's matching) - requires Khushi; (2) architecture spec owner and template; (3) evaluation harness design (Claude can draft once (1) is decided).

## 7. Audit D - Airflow and cloud

| Need | Status |
|---|---|
| Airflow development environment | Not available (`armor-system/airflow/` has only `.gitkeep` files). Airflow version and its supported Python versions are undecided and unverified; the pipeline here was tested on Python 3.14. |
| Ingestion workflow | D1 is a static, precomputed release: the ingest step is `fetch_d1.py` (verified, idempotent, stdlib only). No DAG. |
| Source-data and processed-data contracts | Partly: `schema.json`, split manifests, scaler `.npz`, `preprocessing_config_v1.json` and the NPZ feature cache are well defined; no formal contract document, no storage layout. |
| Reuse of validated preprocessing | Feasible: `pipeline.py --stage <name>` is a CLI with deterministic, hash-verified outputs (two fresh-process runs identical), so stages can be wrapped as tasks. Not wrapped. |
| Warehouse / analytical storage interface | Not available; storage technology undecided. |
| Scheduling, monitoring, retries, idempotency | Not designed. Idempotency of the data stages is evidenced (deterministic hashes); nothing else. |
| Integration with future model inference | Not available (no model, no service contract). |
| Local and cloud configuration | Not available; no Docker, compose or IaC; `deployment/README.md` says cloud provider and CI/CD are undecided. |
| November 12 demonstration | Course requirement recorded in the project notes (Team Meeting 2 on 2026-11-12: cloud-deployed prototype, team-trained model, live input, reproduced baseline; verify against the official schedule PDF). Nothing is built; cloud decisions are open. |

Unresolved decisions (not documentation gaps): cloud provider, object storage and warehouse, credentials and secret handling (public repository), deployment budget, Airflow version/executor, what the DAG ingests given D1 is static. A local Airflow environment wrapping the existing pipeline stages could begin without them.

## 8. Audit E - GPU collaboration

| Item | Finding |
|---|---|
| Environment isolation | Not defined. ARMOR needs an old stack (Python 3.9, torch 1.12.1+cu116, DGL 0.9.0 cu116); Model 1 will want a different stack, so separate environments are required in practice. |
| Driver / CUDA compatibility | Not documented. The cu116 wheels are old; whether they support a given GPU generation and driver must be checked on the actual hardware (`torch.cuda.get_arch_list()`), I could not verify it. |
| Resource sharing / reservation | Not defined. |
| Artifact and checkpoint storage | Only `.gitignore` rules; no shared location or retention policy. |
| Experiment naming / config conventions | Not defined. |
| Concurrent GPU conflicts | No guidance (for example `CUDA_VISIBLE_DEVICES` use, a booking sheet). |

Repository documentation gaps Claude can draft: environment files, a GPU-setup checklist, naming and config conventions. Decisions requiring team coordination: which GPUs exist and who can use them, how they are reserved, where large artifacts live.

## 9. Audit F - predicted teammate questions

Legend: **Can Claude fix?** Y = yes independently, P = partly (needs input), N = no. **Decision** = needs Khushi (K) or team (T). **Severity**: B Blocker, I Important, N Nice-to-have. "Verified" means the named file or command shows it.

### 9.1 General setup

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 1 | Where do I start? | Verified. | `START_HERE.md` | done | - | - |
| 2 | How do I set up on a fresh clone? | Verified (tested on macOS, Python 3.14). | `START_HERE.md`, runbook section 1 | done | - | - |
| 3 | Which Python version? | D1 tooling: 3.10+ (tested 3.14). ARMOR: 3.9. Model 1 and Airflow: unspecified. | runbook; ARMOR README | P | T | I |
| 4 | Where do I get the data? | D1 via `fetch_d1.py` (D1 only). Raw telemetry and D2 intentionally not available. | `armor-system/data/tools/fetch_d1.py` | done | - | - |
| 5 | Running fetch dirtied my git tree. | Known: it rewrites committed manifests. Documented workaround; a safer default is unimplemented. | `data/README.md` | Y | - | N |
| 6 | Can I use D2? | No: licensing/NDA conflict, deferred. | 298-43 report | - | K | I |
| 7 | Is there CI? | No GitHub Actions; run tests locally. | `gh api .../actions/workflows` = 0 | Y (add workflow) | K | I |
| 8 | Why are some folders empty? | They are planned scaffolds; labelled in their READMEs. | `START_HERE.md` | done | - | - |

### 9.2 ARMOR baseline

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 9 | Where is ARMOR's code? | Zenodo; a copy is fetched into the ignored raw folder. Not placed under `baselines/armor/`. | `data/raw/armor_zenodo_21744694/ARMOR/` | Y | K (location) | I |
| 10 | Where is the checkpoint? | In the Zenodo archive (`res/D1/20260113_101332/model.pkl`); **no fetch script**. | `outer_archive_listing.csv` | Y (small script) | K (allowed? trust) | B |
| 11 | How do I put the data where ARMOR expects it? | Unzip `ARMOR/data/D1.zip` into `ARMOR/data/` (ARMOR README); D2 unzip will fail by design. | ARMOR `README.md` | Y (document) | - | I |
| 12 | What environment do I install? | ARMOR README versions; no env file; unpinned extras; Python 3.9 is old. | ARMOR `README.md` | P | T | B |
| 13 | Which GPU/driver works with cu116? | Unknown here; must be checked on the machine. | - | N | T | B |
| 14 | What command runs the released checkpoint? | `python main.py --dataset D1 --run-id 20260113_101332` (ARMOR's own interface; **never run by us**). | ARMOR `main.py:23-27,71-84` | Y (runbook) | - | B |
| 15 | What happens if I forget `--run-id`? | It may start a 1000-epoch training run. | `main.py:71-84` | Y (warn in runbook) | - | I |
| 16 | What numbers should I get? | Table 1 D1 values and released `res.json` listed in section 5. | this audit; paper Table 1 | done | - | - |
| 17 | How do I compare to the paper? | No script or template; compare `res.json` to section 5. | - | Y | - | I |
| 18 | Will training reproduce exactly? | No: unseeded; duration unknown. | grep for seeds | N | K (attempt?) | I |
| 19 | Which protocol must I not change? | AD 98-event post-split scoring, FT/RCL case order. | report sections 5, 9.4 | done | - | - |
| 20 | Where do I save results without committing big files? | No convention. | - | Y (propose) | K | I |
| 21 | Is it safe to unpickle `model.pkl`? | It is arbitrary-code capable; official file only, isolated environment. | `pickle_symbolic.py` docstring | Y (document) | K | I |

### 9.3 Model 1

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 22 | Which split do I use? | Approved 101/25/84. | `splits/model1_split_101_25_84_v1.json`, runbook section 3 | done | - | - |
| 23 | Can I trust per-class validation metrics? | No for Node Memory (1 case) and weak for Node CPU (3). | manifest `statistical_limitations` | done | - | - |
| 24 | What are the input shapes and order? | `(6,46,130)` inputs + `(46,130)` target; order in `schema.json`. | `prepared_example.json` | done | - | - |
| 25 | How are zeros and absent modalities handled? | Zero is not missing; 6 trace and 16 log blocks structurally absent; indicators emitted. | `preprocessing_config_v1.json` | done | - | - |
| 26 | Which scaler do I use and what did it see? | Model 1 train-period scaler only (no validation or test). | `scaler_model1_train_period_v1.npz` | done | - | - |
| 27 | What is the detection target? | **Undefined**: no durations; sample labels must not be invented. | 298-43 report | P | K | B |
| 28 | How do I use the 21 AD-only events? | Uncertain: not positives, not clean negatives. | report 9.1 | done | - | - |
| 29 | How is detection scored? | ARMOR's event matching on 98 and 84 populations separately; no harness. | report 9.1; `evaluation/` empty | Y | K (after #27) | B |
| 30 | What is the Transformer architecture? | Not specified. | - | P | K | B |
| 31 | What is the pretraining task and set? | Pool sizes documented; pretext task unspecified. | section 6 | P | K | I |
| 32 | How do I select thresholds/hyper-parameters with 25 validation cases? | No procedure. | - | P | K | I |
| 33 | Label budgets 10/25/50/100%? | 10/25/51/101 train cases; Node Memory expected 0.4-4.0. | report section 6 | done | K (sampling rule) | I |
| 34 | Where do checkpoints and configs go? | Undefined (ignored dirs only). | `.gitignore` | Y | K | I |
| 35 | How will Model 1 be served? | Undefined. | - | N | K/T | I |

### 9.4 Airflow and cloud

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 36 | Which cloud and storage? | Undecided. | `deployment/README.md` | N | T | B |
| 37 | Where do credentials live? | Undefined; repo is public; ignore rules exist. | `.gitignore` | P | T | B |
| 38 | What is the budget? | Unknown. | - | N | T | B |
| 39 | Which Airflow version/Python? | Undecided; support for Python 3.14 unverified. | - | P | T | I |
| 40 | What does the DAG ingest if D1 is static? | Not defined; ingestion could be fetch+verify+prepare. | runbook | P | T | I |
| 41 | Can I reuse the preprocessing? | Yes: CLI stages, deterministic. Not wrapped. | `pipeline.py` | Y | - | I |
| 42 | What are the data contracts? | Partial (schema, manifests, scaler); no formal document. | `artifacts/d1/` | Y | - | I |
| 43 | What must the Nov 12 demo show? | Course notes: cloud-deployed, team-trained model, live input, reproduced baseline; check the official schedule. | project notes | N | K | I |

### 9.5 GPU access

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 44 | Which GPUs can I use and how do I book them? | Not documented. | - | N | T | B |
| 45 | CUDA/driver requirements? | ARMOR cu116 (old); Model 1 undefined. | ARMOR README | P | T | B |
| 46 | How do I avoid clobbering someone's job? | No guidance. | - | P | T | I |
| 47 | Where do I store checkpoints and results? | No shared location. | - | P | T | I |

### 9.6 GitHub and Linear

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 48 | How do I branch and open a PR? | Branch from the Linear issue; PR to `main`; 1 approval + resolved threads; no force-push. | `START_HERE.md` | done | - | - |
| 49 | Are there Linear issues for my work? | **No**: only 298-42..44 are current; none for baseline, Model 1 or Airflow. The course requires an assigned issue with a linked artifact. | Linear (read-only check) | N (not created, per instruction) | K | B |
| 50 | Does a new push invalidate approval? | No automatically (settings off); this audit's PR rule requires a fresh approval anyway. | ruleset | - | - | N |
| 51 | Is there a PR template or contribution guide? | No. | - | Y | K | N |

### 9.7 Evaluation and evidence

| # | Question | Answer / status | Where | Claude fix? | Decision | Sev |
|---|---|---|---|---|---|---|
| 52 | What counts as evidence? | A committed small artifact or recorded run plus a Linear link; e.g. `evidence.json`. | runbook | P | K | I |
| 53 | How were tests run? | Recorded in `evidence.json` (3 suites). | `data/artifacts/d1/evidence/` | done | - | - |
| 54 | Is the data pipeline reproducible? | Yes, verified (two runs and a fresh clone). | section 1 | done | - | - |
| 55 | How do I run the dashboard? | `armor-system/dashboard/run_dashboard.sh`. | runbook | done | - | - |
| 56 | What are known dataset limitations? | Listed in the runbook and dashboard. | runbook section 8 | done | - | - |

## 10. Prioritized checklist before distributing tasks

**P0 - decide or build before anyone starts**
1. Get PR #35 approved and merged so teammates clone a `main` that contains the pipeline, runbook and `START_HERE.md`.
2. Create Linear issues for the three workstreams with assignees and linked artifacts (not done here, as instructed) so work counts under the course rule.
3. Baseline: decide whether the released checkpoint may be fetched and under what trust model; then add a small fetch script and a baseline runbook (data placement, exact command, expected values, evidence template). Claude can write these after the decision.
4. GPU: decide hardware, driver/CUDA stack, reservation and storage; then document environments.
5. Model 1: decide the detection target without invented durations; assign an architecture-spec owner; then define the evaluation harness.
6. Airflow/cloud: decide provider, storage/warehouse, credentials handling and budget.

**P1**
7. Add CI (a workflow running the three test suites), a PR template and CONTRIBUTING (branch naming from Linear).
8. `.gitignore`: add `*.pkl` outside the data artifacts path (or `armor-system/baselines/**/res/`), and a `.env.example`.
9. Make `fetch_d1.py` not rewrite committed manifests by default.
10. Add environment files per workstream (ARMOR py3.9 stack, Model 1, Airflow) and a lock approach.
11. Define experiment naming, config format and checkpoint locations.

**P2**
12. Pin transitive dependencies; test on Linux; wrap pipeline stages as Airflow tasks; extend the dashboard for baseline/Model 1 results.

## 11. Fixes made during this audit

- `pipeline.py`: missing D1 now fails with a clear message instead of a traceback (found by the fresh-clone test).
- Root README and the `data`, `tests`, `docs`, `baselines` READMEs corrected to match reality; `START_HERE.md` added.
- `d1_validation_report.md`: label-budget row updated for the approved 101-case training set.
- `.gitignore` and ARMOR/Model 1/Airflow architecture were **not** changed (recommendations only).

## 12. Decisions requiring Khushi

1. Detection target and loss policy for Model 1 (no durations available).
2. Whether baseline teammates may fetch the released checkpoint and where baseline code and evidence live.
3. Linear issues and assignments for baseline, Model 1 and Airflow.
4. Whether to add CI and the `.gitignore` additions.
5. With the team: GPU resources, cloud provider/storage/credentials/budget, Python/Airflow versions.

## 13. Known nuances

- The Model 1 validation/test sample boundary equals the AD split timestamp; the sample at exactly 2022-05-06T16:00:00Z is in the Model 1 test period, whereas ARMOR's AD code counts it in its initialisation set (it scores only samples after it). Nothing is fitted on test data either way.
- Windows are counted on the contiguous 7,200-sample timeline; ARMOR windows its train and test files separately (fewer windows).
- The Model 1 scaler is a train-only second stage on ARMOR features that were scaled over the full timeline by an undocumented recipe.
