"""Tier B/C evidence: score ARMOR run directories exactly like the released run and compare their outputs with the released files.

    .venv/bin/python -I armor-system/baselines/armor/reproduction/compare_runs.py --out FILE LABEL=RUN_DIR [LABEL=RUN_DIR ...]

RUN_DIR is an ARMOR run directory produced by `run_armor_cpu.py` (it holds scenarios/full/{res.json,tmp/*}). For each run this
records the metrics from `rescore_released.score` and, against the released D1 run: whether the AD intervals are identical, how
many RCL rankings differ in node order, the largest absolute difference of an RCL similarity score, and the FT cases whose
predicted type differs. Reads only small JSON/CSV outputs; nothing is executed or unpickled.
"""
import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rescore_released import ARMOR_SYSTEM, RELEASED_RUN, score  # noqa: E402


def _tmp(run_dir, name):
    return os.path.join(run_dir, "scenarios", "full", "tmp", name)


def against_released(run_dir):
    with open(_tmp(run_dir, "pre_interval.json")) as a, open(_tmp(RELEASED_RUN, "pre_interval.json")) as b:
        same_intervals = json.load(a) == json.load(b)
    with open(_tmp(run_dir, "pre_types.json")) as a, open(_tmp(RELEASED_RUN, "pre_types.json")) as b:
        ta, tb = json.load(a), json.load(b)
    with open(_tmp(run_dir, "rank_df.csv"), newline="") as a, open(_tmp(RELEASED_RUN, "rank_df.csv"), newline="") as b:
        ra, rb = list(csv.reader(a))[1:], list(csv.reader(b))[1:]
    order = sum(1 for x, y in zip(ra, rb) if [c.split(":")[0] for c in x[4:]] != [c.split(":")[0] for c in y[4:]])
    diff = max(abs(float(c.rsplit(":", 1)[1]) - float(d.rsplit(":", 1)[1])) for x, y in zip(ra, rb) for c, d in zip(x[4:], y[4:]))
    return {"AD_intervals_identical": same_intervals, "RCL_rows_with_different_node_order": order, "RCL_max_abs_score_difference": diff,
            "FT_cases_with_different_type": [i for i, (x, y) in enumerate(zip(ta, tb)) if x != y]}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("runs", nargs="+", metavar="LABEL=RUN_DIR")
    a = ap.parse_args(argv)
    res = {}
    for item in a.runs:
        label, run_dir = item.split("=", 1)
        run_dir = os.path.abspath(os.path.expanduser(run_dir))
        s = score(run_dir)
        s["run_dir"] = os.path.relpath(run_dir, os.path.dirname(ARMOR_SYSTEM)) if run_dir.startswith(os.path.dirname(ARMOR_SYSTEM)) else "<outside repo>/" + "/".join(run_dir.split(os.sep)[-5:])
        res[label] = {"scores": s, "against_released": against_released(run_dir)}
        print(label, json.dumps({"AD": s["AD_official_98"]["f1"], "FT_weighted_f1": s["FT_cases_84"]["weighted"]["f1"],
                                 "RCL_avgK": s["RCL_cases_84"]["avgK"], **res[label]["against_released"]}))
    with open(a.out, "w") as fh:
        json.dump(res, fh, indent=1, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    main()
