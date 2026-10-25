"""ARMOR D1 data-preparation pipeline (Linear 298-44). CPU only; reads the verified local release.

    python armor-system/data/pipeline.py --stage all          # everything, including tests and evidence
    python armor-system/data/pipeline.py --stage splits       # run up to and including one stage

Stages: cache, inspect, splits, preprocess, eda, figures, augmentation, quality, tests, evidence.
`tests` and `evidence` run only when selected or with `all`.
"""
import argparse
import datetime
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from prep import (augmentation, eda, figures, inspect_stage, loader, paths, preprocess_stage, quality,  # noqa: E402
                  split_stage)
from prep.common import sha256_file, write_json  # noqa: E402

STAGES = ["cache", "inspect", "splits", "preprocess", "eda", "figures", "augmentation", "quality", "tests", "evidence"]
REPO = os.path.abspath(os.path.join(paths.ROOT, ".."))
SUITES = [("tests/data", "D1 acquisition tools (298-43)"), ("tests/prep", "D1 preparation pipeline (298-44)"), ("tests/dashboard", "Streamlit dashboard smoke tests")]


def run_tests():
    suites, totals = [], {"total": 0, "failures": 0, "errors": 0, "skipped": 0}
    for rel, label in SUITES:
        d = os.path.join(paths.ROOT, rel)
        if not os.path.isdir(d):
            continue
        p = subprocess.run([sys.executable, "-I", "-m", "unittest", "discover", "-s", d, "-p", "test_*.py"], capture_output=True, text=True, cwd=REPO)
        out = p.stderr + p.stdout
        n = int(re.search(r"Ran (\d+) tests?", out).group(1)) if re.search(r"Ran (\d+) tests?", out) else 0
        fail = int(m.group(1)) if (m := re.search(r"failures=(\d+)", out)) else 0
        err = int(m.group(1)) if (m := re.search(r"errors=(\d+)", out)) else 0
        skip = int(m.group(1)) if (m := re.search(r"skipped=(\d+)", out)) else 0
        ok = p.returncode == 0
        suites.append({"suite": label, "directory": f"armor-system/{rel}", "tests": n, "failures": fail, "errors": err, "skipped": skip, "result": "OK" if ok else "FAILED"})
        for k, v in (("total", n), ("failures", fail), ("errors", err), ("skipped", skip)):
            totals[k] += v
        print(f"{label}: ran {n}, failures {fail}, errors {err}, skipped {skip} -> {'OK' if ok else 'FAILED'}")
        if not ok:
            print(out[-2000:])
    return {**totals, "suites": suites, "ran_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "command": "python -I -m unittest discover -s armor-system/tests/<suite> -p 'test_*.py'"}


def git(*a):
    try:
        return subprocess.run(["git", *a], capture_output=True, text=True, cwd=REPO).stdout.strip()
    except Exception:
        return ""


def pr_info(selector):
    try:
        p = subprocess.run(["gh", "pr", "view", selector, "--json", "number,title,state,url,reviewDecision,headRefOid,headRefName,baseRefName"], capture_output=True, text=True, cwd=REPO, timeout=30)
        return json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
    except Exception:
        return None


def build_evidence(tests, splits_result, prior=None):
    art = paths.ART
    arts = []
    for root, _, files in os.walk(art):
        rel_root = os.path.relpath(root, art)
        if rel_root.split(os.sep)[0] == "evidence":
            continue
        for f in sorted(files):
            full = os.path.join(root, f)
            arts.append({"path": os.path.relpath(full, REPO), "category": rel_root.split(os.sep)[0] if rel_root != "." else "root",
                         "bytes": os.path.getsize(full), "sha256": sha256_file(full)[:16]})
    prs = []
    branch = git("rev-parse", "--abbrev-ref", "HEAD")
    for sel in ("34", branch):
        info = pr_info(sel)
        if info and info["number"] not in [p["number"] for p in prs]:
            prs.append({k: info[k] for k in ("number", "title", "state", "url", "reviewDecision", "headRefOid", "baseRefName")})
    if not prs and prior:
        prs = prior.get("prs", [])
    docs = [("armor-system/docs/d1_data_preparation_runbook.md", "engineering runbook: environment, pipeline, splits, EDA, validation, dashboard, troubleshooting"),
            ("armor-system/docs/d1_validation_report.md", "298-43 acquisition, labeling decisions and reconciliation"),
            ("armor-system/docs/d1_augmentation_assessment.md", "augmentation assessment generated from calculations"),
            ("armor-system/data/artifacts/d1/README.md", "index of generated artifacts")]
    cand = splits_result["candidate"]
    lim = []
    if not cand["usable"]:
        lim.append(("BLOCKED", "Decision needed: the proposed 100/26/84 Model 1 split fails hard checks. Approve the recommended alternative (or forward-chaining folds) before any Model 1 data use."))
    p34 = next((p for p in prs if p["number"] == 34), None)
    if not p34 or p34["state"] != "MERGED":
        lim.append(("PENDING", "PR #34 (acquisition and label decisions) awaits independent review; this work is stacked on it and cannot merge first."))
    lim += [("WARN", "The 21 AD-only and 7 case-only label discrepancies are unexplained (originated in the ART release)."),
            ("WARN", "No incident end times or durations exist, so no sample-level detection labels were built."),
            ("INFO", "Augmentation was assessed and not adopted; raw telemetry and D2 downloads remain deferred; no model was trained.")]
    return {"generated_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "git": {"branch": branch, "head": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain", "--", ".", ":!armor-system/data/artifacts/d1/evidence"))},
            "prs": prs, "tests": tests,
            "linear": [{"title": "298-44 Complete ARMOR D1 Data Preparation, EDA, Validation and Streamlit Dashboard", "url": "https://linear.app/298a-team-1-self-healing-cloud/issue/298-44/complete-armor-d1-data-preparation-eda-validation-and-streamlit", "note": "this work"},
                       {"title": "298-43 Acquire and validate ARMOR D1 benchmark dataset", "url": "https://linear.app/298a-team-1-self-healing-cloud/issue/298-43/acquire-and-validate-armor-d1-benchmark-dataset", "note": "dependency"}],
            "docs": [{"path": p, "purpose": d, "exists": os.path.exists(os.path.join(REPO, p))} for p, d in docs],
            "artifacts": arts, "limitations": lim}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", default="all", choices=["all"] + STAGES)
    args = ap.parse_args()
    last = len(STAGES) - 1 if args.stage == "all" else STAGES.index(args.stage)
    want = lambda s: STAGES.index(s) <= last  # noqa: E731
    paths.ensure_dirs()
    if not os.path.exists(paths.CACHE_FILE) or args.stage == "cache":
        print("building feature cache ...")
        loader.build_cache()
    if not os.path.exists(paths.D1_DIR):
        sys.exit(f"D1 release not found at {paths.D1_DIR}; run armor-system/data/tools/fetch_d1.py first")
    labels = loader.read_labels()
    ts, X, is_test = loader.load_arrays()
    state = {}
    if want("inspect"):
        s = inspect_stage.run(labels, ts, X, is_test)
        print("inspect:", s["counts"])
    if want("splits"):
        state["splits"] = split_stage.run(labels, ts, is_test)
        for k in ("official", "candidate", "alternative"):
            m = state["splits"][k]
            if m:
                print(f"splits: {m['name']}: {m['verdict']} usable={m['usable']}")
    if want("preprocess"):
        res, state["scalers"] = preprocess_stage.run(labels, ts, X, is_test, state["splits"])
        print("preprocess: config", res["config_sha256"][:12], "schema issues", res["schema_issues"])
    if want("eda"):
        for f in eda.run(labels, ts, X, is_test, state["splits"], state["scalers"]):
            print("eda:", f["id"])
    if want("figures"):
        print("figures:", len(figures.run(state["splits"])))
    if want("augmentation"):
        print("augmentation:", augmentation.run(labels, ts, X, is_test, state["splits"], state["scalers"])["decision"])
    if want("quality"):
        q = quality.run(labels, ts, X, is_test, state["splits"], state["scalers"])
        quality.print_table(q)
    tests = None
    if want("tests") and args.stage in ("tests", "evidence", "all"):
        tests = run_tests()
    if want("evidence") and args.stage in ("evidence", "all"):
        prior = None
        pe = os.path.join(paths.ART, "evidence", "evidence.json")
        if os.path.exists(pe):
            with open(pe) as fh:
                prior = json.load(fh)
        if tests is None and prior:
            tests = prior.get("tests")
        write_json(pe, build_evidence(tests, state["splits"], prior))
        print("evidence written")


if __name__ == "__main__":
    main()
