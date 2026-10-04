# Compute Budget, Resource Gaps & Top Project Risks

Evidence artifact for Linear issue 298-17 ("Document Compute Budget, Resource Gaps &
Top Project Risks"). This issue was marked Done without a committed artifact; this
file closes that gap using only currently verified facts. It does not attempt to
reconstruct unrecorded Checkpoint-1-era specifics that were never captured.

Created: 2026-10-03, on branch `khushi/project-evidence-cleanup`.

## 1. Available development/compute resources

Verified on the one development machine this was authored from (Khushi Donda's).
**Other team members' hardware has not been surveyed and is not claimed here.**

| Resource | Verified value | How verified |
|---|---|---|
| CPU | Apple M4, 10 physical / 10 logical cores | `sysctl -n machdep.cpu.brand_string`, `sysctl -n hw.physicalcpu hw.logicalcpu` |
| RAM | 16.0 GB | `sysctl -n hw.memsize` |
| GPU | Apple M4 integrated GPU (no discrete/CUDA GPU) | `system_profiler SPDisplaysDataType` |
| Disk free (at time of writing) | 115 GiB free of 460 GiB | `df -h` |
| OS | macOS 26.5.2 (build 25F84) | `sw_vers` |
| Cloud resources | **None established** — no cloud account/credits/provider selected anywhere in the repo | repo-wide search, see `docs/project/semester_scope.md` and `docs/infra/environment-evaluation/README.md` (historical, superseded) |
| Local dataset storage | BARO `fse-ob` extracted artifact: 477 MB | `du -sh ~/298A_project/code/baro/data/fse-ob` |

## 2. Measured compute needs (not estimated — actually run)

| Component | Measured compute | Evidence |
|---|---|---|
| Model 1 training — baseline (h64/z32, 10 epochs) | 7.26 sec, CPU | `experiments/model1/baseline_seed42_h64_z32/run_metadata.json` |
| Model 1 training — baseline mean-impute (h64/z32, 100 epochs) | 72.68 sec, CPU | `experiments/model1/baseline_seed42_h64_z32_mean_impute/run_metadata.json` |
| Model 1 training — Candidate B (h32/z16, 100 epochs, 22,727 params, **frozen final model**) | 41.96 sec, CPU | `experiments/model1/candidate_B_h32_z16_seed42/run_metadata.json` |
| Model 1 training — Candidate C (h64/z16, 100 epochs) | 70.33 sec, CPU | `experiments/model1/candidate_C_h64_z16_seed42/run_metadata.json` |
| Model 1 training — Candidate D (h128/z32, 100 epochs, largest tested, 242,263 params) | 120.61 sec, CPU | `experiments/model1/candidate_D_h128_z32_seed42/run_metadata.json` |
| BARO Table 3 reproduction (all 100 cases, `--fault-type all`) | ~1.6 sec, CPU | measured directly this session running `python main.py --dataset OnlineBoutique --fault-type all` in `~/298A_project/code/baro` |
| BARO Table 3 reproduction (single fault type, 25 cases each) | ~0.4–0.5 sec each, CPU | same session, `cpu`/`mem`/`delay`/`loss` runs |

**No GPU was required for any committed Model 1 training run or the BARO reproduction** —
all recorded `device` fields are `"cpu"` (`run_metadata.json`, every experiment directory).

**Not yet measured / not applicable (design-only in 298A, see `docs/project/semester_scope.md`):**
- LLM diagnosis/remediation generation (Model 3) — no model selected, no compute measured.
- Action-risk classifier (Model 4) — no model selected, no compute measured.
- Service-graph RCA (Model 2) — design-only; no training run exists.

## 3. Resource gaps identified

1. **No team-wide compute survey exists.** Only one contributor's machine is verified
   here (see §1 caveat). Whether other team members can reproduce Model 1 training or
   the BARO baseline on their own hardware is unconfirmed.
2. **No cloud compute/storage account is established.** `docs/infra/environment-evaluation/README.md`
   discusses candidates only (AWS mentioned conditionally: "useful if our team decides
   to use AWS") and is itself marked historical/superseded (`README.md:9`). No
   replacement decision has been made.
3. **No compute/cost budget exists for 298B's LLM-based components** (Models 3 and 4).
   Nothing in the repo estimates token costs, API costs, or GPU needs for an LLM
   diagnosis/remediation generator or an action-risk classifier, because neither has
   been designed yet beyond the role description in the abstract.

Approximate cost: **not applicable / unknown** for all three gaps above — everything
measured in §2 ran on local, already-owned hardware at no incremental cost.

## 4. Top 3 project risks

| # | Risk | Why it matters | Likelihood/impact | Mitigation | Backup/fallback |
|---|---|---|---|---|---|
| 1 | Model 1 generalization gap: all 3 locked held-out-test targets (F1≥0.82, delay≤10s, FPR≤5%) **failed**, despite passing on validation | The only complete model in the project does not meet its own pre-registered success criteria on genuinely unseen data | Already realized (not hypothetical) / high — affects every claim about Model 1 being "successful" | `experiments/model1/final_model_selection.json` froze the architecture/threshold **before** this test was run, so the result could not be hidden or silently re-tuned; `experiments/model1/failure_study/` analyzes the gap descriptively | Report the failure honestly (already done, `model1_final_summary.json.final_outcome`); treat architecture/data improvements as 298B scope, not a 298A patch |
| 2 | No established compute/cost budget for the two LLM-dependent models (3 and 4) | 298B cannot be planned or costed without this | Not yet realized / medium-high if left unresolved into 298B | None yet | Defer LLM model selection and cost estimation explicitly to 298B (`docs/project/semester_scope.md`), rather than guessing a budget now |
| 3 | Model 1 training and the BARO reproduction have only been verified on one contributor's machine | If another teammate cannot reproduce these results, the "reproducible" claim throughout the docs is unverified at the team level | Low probability (both run in seconds on modest CPU hardware, per §2) but currently untested | Exact repro commands are documented (`README.md`, `docs/data/README.md`, `docs/baseline/baseline_reproduction.md`) so any teammate can attempt it | This gap is now explicitly logged here rather than assumed away; closing it only requires another teammate to run the documented commands, no new tooling needed |

## 5. Required-evidence checklist (from Linear 298-17)

- [x] Current team compute resources documented (one machine verified; team-wide gap explicitly flagged, §1/§3)
- [x] Expected compute requirements documented (measured, not estimated, §2)
- [x] GPU requirements identified where applicable (none needed for any current component, §2)
- [x] Storage requirements estimated (477 MB local dataset, §1)
- [x] Cloud/resource gaps identified (§3)
- [x] Approximate cost noted where applicable (§3: not applicable, local hardware only)
- [x] Top 3 project risks identified (§4)
- [x] Impact of each risk documented (§4)
- [x] Mitigation for each risk documented (§4)
- [x] Backup/fallback strategy documented for each risk (§4)
- [ ] Information summarized for the Checkpoint 1 presentation — **not applicable retroactively**; Checkpoint 1 has already passed. This artifact closes the evidence gap for the record, not for a past presentation.
- [x] Evidence committed to GitHub and linked to Linear (this file, linked to 298-17 via comment on this branch's commit)
