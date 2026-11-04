# ARMOR D1 baseline reproduction

**Status:**
- Tier A is complete.
- Tier B is complete: AD and RCL are reproduced exactly; FT is not.
- Tier C (independent training) has not been run.

Everything here uses ARMOR's official Zenodo release (record 21744694), its D1 data and its code. It uses no D2 data, no Model 1 training, and no tuning on any D1 split. The ARMOR baseline was assigned to the baseline teammates (`docs/team_handoff_readiness_audit.md`), so they should review this before it is cited. This folder does not touch Model 1, Airflow, deployment or any teammate folder.

## 1. What "reproduced" means here

| Tier | What runs | What it shows |
|---|---|---|
| A. Released predictions | ARMOR's own metric code on the authors' released output files (`pre_interval.json`, `pre_types.json`, `rank_df.csv`) | The published numbers follow from the released outputs. No ARMOR model is run. |
| B. Released checkpoint | ARMOR's unmodified `main.py` with the authors' released `model.pkl`, D1 data and config | The official evaluation pipeline regenerates those outputs. No training. |
| C. Independent training | ARMOR's `main.py` with no `model.pkl`, so it trains from scratch | Whether the method itself reproduces. **Not run** (section 5). |

## 2. Results

Populations: all are in the D1 test period, after ARMOR's `split_ts` 1651852800, which is also our validation|test boundary.
- **AD:** ARMOR's 98 post-split labels in `ad_cases.pkl`.
- **FT and RCL:** the 84 test cases, `cases.csv` rows 126–209.

| Task, metric | Published (ARMOR paper / `res.json`) | Tier A: released predictions | Tier B: released checkpoint, CPU |
|---|---|---|---|
| AD precision / recall / F1 | 0.9245 / 1.0 / 0.9608 | 0.9245 / 1.0 / 0.9608 | **0.9245 / 1.0 / 0.9608** (intervals identical to the released file) |
| FT weighted P / R / F1 | 0.9464 / 0.9405 / 0.938 | 0.9464 / 0.9405 / 0.938 | **0.8985 / 0.8929 / 0.884** (xgboost 1.6.2, 1.7.6); **0.9158 / 0.9048 / 0.8968** (xgboost 2.0.3, 2.1.4) |
| RCL Top@1..5 | 0.8214, 0.8929, 0.9405, 0.9405, 0.9524 | identical | **identical** (same node order in all 84 rankings; scores within 1.2e-7) |
| RCL Avg@5 | 0.9095 | 0.9095 | **0.9095** |

- **Tier B is deterministic on this CPU.** A second run in the recorded environment gave byte-identical outputs, with the same SPOT threshold 17.0983.
- **The FT gap is unresolved.** The checkpoint's representations match the released ones to about 1e-7: the AD intervals are identical and the RCL ranking order is identical.
  - Only 3 or 4 of the 84 FT predictions differ from the released ones (case indices 54, 60 and 72, plus 17 under xgboost 1.x).
  - FT is the one stage that trains a new model at evaluation time: an XGBoost classifier with `random_state=42`. ARMOR does not pin the XGBoost version, and the four versions tried give two different results.
  - The likely causes are the authors' XGBoost version or build, and GPU-vs-CPU float differences reaching XGBoost's split points. We did not search further: picking whichever environment hits 0.938 would be fitting to the published number.
  - **The released FT score 0.938 is therefore reproduced from released predictions only. From the released checkpoint we get 0.884–0.897.**

## 3. Comparison with frozen Model 1, same populations and metrics

Model 1 numbers are copied from the frozen `models/model1_transformer/results/test_v1/summary.json` (one-shot test, five seeds, mean ± SD). Nothing in Model 1 was re-run or re-scored. The ARMOR rows marked † were computed here, after the Model 1 test, from ARMOR's released outputs only. They do not change any Model 1 number.

**Detection, ARMOR's 98 official labels** (test plan section 5):

| Row | P | R | F1 | FP intervals | Alert coverage (raw / ±300 s) |
|---|---|---|---|---|---|
| ARMOR released intervals (= Tier B) | 0.9245 | 1.000 | 0.9608 | 8 † | 0.703 / 0.874 † |
| Model 1 v1 primary (A1, supervised) | 0.826 ± 0.024 | 0.661 ± 0.079 | 0.733 ± 0.052 | 13.6 | 0.201 / 0.428 |
| Model 1 v1 ensemble (secondary) | 0.833 | 0.714 | 0.769 | 14 | 0.202 / 0.458 |
| Model 1 D3 @ p90 (label-free) | 0.863 | 0.837 | 0.850 | 13.0 | 0.337 / 0.585 |
| Model 1 D3 @ p99 (A2, label-free) | 1.000 | 0.200 | 0.333 | 0 | 0.026 / 0.092 |

**Detection, the 84 documented test incidents** (Model 1's primary population):

| Row | P | R | F1 | FP intervals |
|---|---|---|---|---|
| ARMOR released intervals † | 0.8936 | 1.000 | 0.9438 | 10 |
| Model 1 v1 primary | 0.769 ± 0.028 | 0.693 ± 0.090 | 0.727 ± 0.056 | 17.4 |
| Model 1 v1 ensemble | 0.793 | 0.774 | 0.783 | 17 |
| Model 1 D3 @ p90 | 0.766 | 0.812 | 0.788 | 20.8 |

**Fault type, the 84 test cases:**

| Row | Weighted F1 (ARMOR's metric) | Macro-F1 (Model 1's primary) | Accuracy |
|---|---|---|---|
| ARMOR released predictions | 0.938 | 0.897 † | 0.940 † |
| ARMOR released checkpoint (Tier B) | 0.884–0.897 | 0.793–0.805 † | 0.893–0.905 † |
| Model 1 v1 | 0.827 ± 0.039 | 0.721 ± 0.055 | 0.833 ± 0.038 |
| Model 1 v1 ensemble | 0.826 | 0.703 | 0.833 |
| XGBoost control (Model 1 features) | 0.846 ± 0.013 | 0.710 ± 0.017 | 0.857 ± 0.015 |

How to read these tables:
- **Alert coverage.** ARMOR's detection numbers come with alert intervals that cover **70% of all test-period minutes** (2,879 minutes, raw). Model 1 v1 covers 20%. ARMOR's own log reports that 38% of the evaluation windows are outliers.
  - Interval-overlap scoring counts a label as hit whenever any interval reaches its ±300 s window. A detector that is "on" most of the time can therefore reach recall 1.0 with few false-positive intervals.
  - Precision, recall and F1 alone do not show this, so coverage should be reported with every comparison.
- **Calibration differs.** ARMOR sets its threshold with SPOT on 2,269 in-sample training minutes. Model 1 uses a percentile of 329 out-of-sample calibration windows.
- **Both FT methods are told when the incident happened.**
  - ARMOR's FT trains an XGBoost classifier on the first 126 cases. Its features are aggregated over [t − 59 s, t + 300 s) around each known case time.
  - Model 1 averages its window predictions over each case's windows.
  - Neither detects and classifies end to end. The FT rows compare classifiers, not systems.
- **Timestamp alignment is assumed.** ARMOR's sample timestamp convention (window start, end or sample time) is not stated. Placing Model 1 alerts at the target minute is an assumption (`DETECTION_PROTOCOL.md` 2.10).
- **Labels are weak.** 21 of ARMOR's 98 labels have no case record (`d1_validation_report.md` 9.2).
- **Missing data.** ARMOR released no missing-data outputs, so the missing-data rows have no ARMOR counterpart.

## 4. Commands

Run from the repository root. The data, checkpoint and run folders are all Git-ignored or outside the repository.

```bash
# 0. D1 data and ARMOR code (298-43). Already present if data/raw/armor_zenodo_21744694/ exists.
.venv/bin/python -I armor-system/data/tools/fetch_d1.py
# 1. Released D1 run: model.pkl + res.json + 3 prediction files. Range requests, CRC-checked, nothing from D2.
.venv/bin/python -I armor-system/baselines/armor/reproduction/fetch_released_d1_run.py
# 2. Tier A
.venv/bin/python -I armor-system/baselines/armor/reproduction/rescore_released.py --out armor-system/baselines/armor/reproduction/evidence/tierA_released_predictions.json

# 3. ARMOR environment (macOS: osx-64 under Rosetta, because DGL 0.9.0 has no arm64 build; Linux: follow ARMOR's README)
CONDA_SUBDIR=osx-64 conda create -n armor-repro python=3.9 -y
conda run -n armor-repro conda config --env --set subdir osx-64
conda run -n armor-repro pip install torch==1.12.1 dgl==0.9.0 scikit-learn==1.1.2 numpy==1.23.5 pandas==1.5.3 xgboost==1.7.6 pyyaml tqdm matplotlib
#    (for xgboost>=2.1 also: conda install -n armor-repro -c conda-forge llvm-openmp). Exact freeze: environment-armor-repro.txt

# 4. Isolated ARMOR copy, so ARMOR's writes never touch the released files
RAW=armor-system/data/raw/armor_zenodo_21744694; RUN=~/298A_project/armor_runs/tierB/ARMOR
mkdir -p $RUN/data $RUN/res/D1/20260113_101332
cp -R $RAW/ARMOR/{main.py,config,models,utils} $RUN/
cp -R $RAW/extracted/D1 $RUN/data/D1
cp $RAW/ARMOR/res/D1/20260113_101332/model.pkl $RUN/res/D1/20260113_101332/
# 5. Tier B: about 70 s on CPU, 2.1 GB RAM
(cd $RUN && /opt/anaconda3/envs/armor-repro/bin/python "$OLDPWD/armor-system/baselines/armor/reproduction/run_armor_cpu.py" --dataset D1 --run-id 20260113_101332)
.venv/bin/python -I armor-system/baselines/armor/reproduction/compare_runs.py --out /tmp/tierB.json xgboost_1.7.6=$RUN/res/D1/20260113_101332

# Tier C (not run): an ARMOR copy without model.pkl, then
#   (cd <copy> && <env python> .../run_armor_cpu.py --dataset D1 --run-id <new_run_name>)
# then step 5's compare_runs.py on <copy>/res/D1/<new_run_name>.
```

The only deviation from ARMOR's own command (`python main.py --dataset D1 --run-id 20260113_101332`) is `run_armor_cpu.py`:
- It maps the GPU-saved checkpoint's tensors to CPU at load time.
- It imports xgboost before torch (load order only).

No ARMOR file is edited.

## 5. Remaining work and blockers

1. **Tier C, independent training (not run).**
   - One epoch takes 321 s on this Mac's CPU under Rosetta (`evidence/tierC_training_cost.json`).
   - Early stopping with patience 50 means at least 50 epochs, so one run takes roughly 4.5 to 89 hours.
   - ARMOR sets no seeds, so several runs are needed to measure spread.
   - This needs a Linux CUDA machine (ARMOR's stated setup), or an agreed multi-day CPU run. It is not a code blocker.
2. **FT from the checkpoint.** It gives 0.884–0.897 against the released 0.938 (section 2). This needs either a Linux CUDA rerun of Tier B or the authors' exact XGBoost version.
3. **Review by the baseline teammates** before these rows go into the course report. The course report prose must be written by the team; this file is repository documentation.
4. **D2.** Not used; its licence is unclear (`models/model1_post_test_analysis/D2_CHECK.md`).

## 6. Files

| File | Purpose |
|---|---|
| `fetch_released_d1_run.py` | Fetches the five released D1 run files with CRC checks; writes `evidence/released_d1_run_fetch.json` |
| `rescore_released.py` | Tier A scoring (also scores any ARMOR run directory) |
| `run_armor_cpu.py` | CPU launcher for ARMOR's unmodified `main.py` |
| `compare_runs.py` | Tier B/C evidence: scores plus differences against the released outputs |
| `time_training.py` | Tier C timing probe |
| `environment-armor-repro.txt` | Exact package freeze of the ARMOR environment |
| `evidence/*.json` | Fetch hashes, Tier A, Tier B (five runs), Tier C cost |
