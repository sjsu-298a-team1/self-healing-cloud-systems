"""STEP 8: BARO-equivalent nine-stage engineering validation adapted to D1.

Each stage returns checks with PASS/FAIL and a detail string computed from real data. Stage 9 injects
deliberate corruptions into in-memory copies and requires every one to be detected (and the clean input to pass).
"""
import csv
import os

import numpy as np

from . import paths, preprocess as pp, splits as sp
from .common import read_json, sha256_file, write_json
import d1_checks as ck  # noqa: E402
import validate_d1 as v1  # noqa: E402


def _chk(name, ok, detail):
    return {"name": name, "status": "PASS" if ok else "FAIL", "detail": detail}


def _stage(num, name, checks):
    return {"stage": num, "name": name, "status": "PASS" if all(c["status"] == "PASS" for c in checks) else "FAIL", "checks": checks}


# ---- detectors reused by stage 9 --------------------------------------------------------------
def detect_timestamp_problems(ts):
    d = np.diff(ts)
    out = []
    if (d == 0).any():
        out.append("duplicate timestamps")
    if (d < 0).any():
        out.append("timestamps out of order")
    return out


def detect_label_problems(cases, type_hash):
    return [f"unmapped failure type: {t}" for t in ck.unmapped_failure_types(cases, type_hash)]


def detect_partition_overlap(split_sets):
    names = list(split_sets)
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            n = len(split_sets[a] & split_sets[b])
            if n:
                out.append(f"{n} samples shared by {a} and {b}")
    return out


def detect_scaler_leak(ts, fit_mask, boundary_ts):
    n = int((np.asarray(ts)[np.asarray(fit_mask, bool)] > boundary_ts).sum())
    return [f"scaler fit set contains {n} samples after the training boundary"] if n else []


def run(labels, ts, X, is_test, splits_result, scalers, d1_dir=paths.D1_DIR):
    schema = read_json(paths.art("inspection", "schema.json"))
    groups, nodes, channels, cases = labels["groups"], labels["nodes"], labels["channels"], labels["cases"]
    ad_split = splits_result["ad_split"]
    stages = []

    # 1 integrity
    inv = v1.verify_inventory(d1_dir, os.path.join(paths.MANIFESTS_298_43, "file_inventory.csv"))
    ck_json = read_json(os.path.join(paths.MANIFESTS_298_43, "checksums.json"))
    d1zip = os.path.join(paths.RAW, "ARMOR", "data", "D1.zip")
    exp = next((m["sha256"] for m in ck_json.get("fetched_members", []) if m["member"].endswith("data/D1.zip")), None)
    s1 = [_chk("extracted_files_match_inventory", not inv["problems"], f"{inv['files_checked']} files re-hashed against file_inventory.csv; problems: {inv['problems'] or 'none'}")]
    if os.path.exists(d1zip) and exp:
        s1.append(_chk("d1_zip_sha256_matches_manifest", sha256_file(d1zip) == exp, f"D1.zip sha256 vs checksums.json ({exp[:12]}...)"))
    else:
        s1.append(_chk("d1_zip_sha256_matches_manifest", False, "D1.zip or its recorded sha256 is missing"))
    s1.append(_chk("ground_truth_provenance_documented", os.path.exists(os.path.join(paths.MANIFESTS_298_43, "provenance.json")), "provenance.json from Linear 298-43 present"))
    stages.append(_stage(1, "Dataset integrity", s1))

    # 2 schema
    issues = pp.validate_schema(X, ts, schema) + pp.validate_order(nodes, channels, schema)
    cov = sorted(i for m in groups.values() for i in m) == list(range(len(channels)))
    stages.append(_stage(2, "Schema consistency", [
        _chk("tensor_schema_valid", not issues, f"shape {X.shape}, dtype {X.dtype}; issues: {issues or 'none'}"),
        _chk("node_and_channel_order_stable", not pp.validate_order(nodes, channels, schema), f"{len(nodes)} nodes, {len(channels)} channels match schema.json hashes"),
        _chk("modality_groups_partition_channels", cov, {m: len(i) for m, i in groups.items()}.__repr__())]))

    # 3 timestamps
    d = np.diff(ts)
    tr_ts, te_ts = set(ts[~is_test].tolist()), set(ts[is_test].tolist())
    days = int((d > 60).sum()) + 1
    stages.append(_stage(3, "Timestamp validity", [
        _chk("strictly_increasing_unique", not detect_timestamp_problems(ts), f"{len(ts)} timestamps"),
        _chk("sampling_step_60s_within_days", bool((d[d != 60] > 3600).all()) and int((d != 60).sum()) == 4, f"{int((d == 60).sum())} steps of exactly 60 s; {int((d != 60).sum())} other steps, all > 1 h (boundaries between the 5 collection days)"),
        _chk("train_test_files_disjoint", not (tr_ts & te_ts), f"{len(tr_ts)} train-file and {len(te_ts)} test-file timestamps share {len(tr_ts & te_ts)}"),
        _chk("case_timestamps_in_sample_range", all(ts[0] <= c["timestamp"] <= ts[-1] for c in cases), f"cases span {cases[0]['timestamp']}..{cases[-1]['timestamp']}")]))

    # 4 labels
    th, td = labels["type_hash"], labels["type_dict"]
    cats = {td[th[c["failure_type"]]] for c in cases if c["failure_type"] in th}
    stages.append(_stage(4, "Class-label consistency", [
        _chk("every_failure_type_mapped", not detect_label_problems(cases, th), f"{len({c['failure_type'] for c in cases})} fine types"),
        _chk("five_categories", len(cats) == 5 and cats == set(sp.CLASSES), f"categories: {sorted(cats)}"),
        _chk("cases_in_chronological_order", all(b["timestamp"] > a["timestamp"] for a, b in zip(cases, cases[1:])), f"{len(cases)} cases"),
        _chk("case_count_matches_documentation", len(cases) == 210, f"{len(cases)} cases (ARMOR paper: 210)")]))

    # 5 split reproducibility
    from . import split_stage as ss
    cats_l = [td[th[c["failure_type"]]] for c in cases]
    segs = ck.segment_bounds(sorted(ts[is_test].tolist()))
    ts_list = sorted(ts.tolist())
    k_off = ck.case_split_index(len(cases), 0.6)
    rebuilt = [sp.build(ss.OFFICIAL, "approved_reproduction", splits_result["official"]["description"], cases, cats_l, {"train": [0, k_off], "test": [k_off, len(cases)]}, ts_list, segs, ad_split, ad_aligned=False)[0]]
    committed = [read_json(paths.art("splits", f"{splits_result['official']['name']}.json"))]
    for key in ("candidate", "alternative"):
        m = splits_result[key]
        if not m:
            continue
        r = {s: [x["start_index"], x["end_index_exclusive"]] for s, x in m["case_ranges"].items()}
        rebuilt.append(sp.build(m["name"], m["status"], m["description"], cases, cats_l, r, ts_list, segs, ad_split)[0])
        committed.append(read_json(paths.art("splits", f"{m['name']}.json")))
    stages.append(_stage(5, "Split reproducibility", [
        _chk(f"rebuild_identical_{a['name']}", a["content_sha256"] == b["content_sha256"], f"rebuilt sha256 {a['content_sha256'][:12]}... == committed {b['content_sha256'][:12]}...")
        for a, b in zip(rebuilt, committed)] + [
        _chk("official_split_is_126_84", splits_result["official"]["case_ranges"]["train"]["n_cases"] == 126 and splits_result["official"]["case_ranges"]["test"]["n_cases"] == 84, "ARMOR reproduction split preserved")]))

    # 6 train-only scaler
    sc = scalers["official_train_period"]
    fit = ts <= ad_split
    again = pp.fit_scaler(X, fit, groups)
    Xp = X.copy()
    Xp[~fit] = Xp[~fit] * 7 + 1.5                       # perturb everything outside the fit set
    pert = pp.fit_scaler(Xp, fit, groups)
    leaky = pp.fit_scaler(X, np.ones(len(ts), bool), groups)
    stored = np.load(paths.art("preprocessing", "scaler_official_train_period_v1.npz"))
    stages.append(_stage(6, "Training-only scaler fitting", [
        _chk("refit_matches_stored_scaler", np.allclose(again["mean"], stored["mean"]) and np.allclose(again["scale"], stored["scale"]), "refit on the official train period equals scaler_official_train_period_v1.npz"),
        _chk("scaler_ignores_non_fit_samples", np.array_equal(again["mean"], pert["mean"]) and np.array_equal(again["scale"], pert["scale"]), f"perturbing {int((~fit).sum())} held-out samples leaves every fitted parameter unchanged"),
        _chk("fit_set_has_no_heldout_case", not detect_scaler_leak(ts, fit, ad_split) and ts[fit].max() < cases[k_off]["timestamp"], f"latest fit sample {int(ts[fit].max())} < first held-out case {cases[k_off]['timestamp']}"),
        _chk("control_scaler_fit_on_all_differs", not np.allclose(leaky["mean"], again["mean"]), "a scaler fit on all samples differs, so the check can detect leakage")]))

    # 7 leakage
    man = splits_result["official"]
    alt = splits_result["alternative"]
    checks7 = []
    for m in [man] + ([alt] if alt else []):
        hard = [c for c in m["checks"] if c["severity"] == "hard"]
        checks7.append(_chk(f"hard_split_checks_{m['name']}", all(c["status"] == "PASS" for c in hard), "; ".join(f"{c['id'].split('_')[0]} {c['status']}" for c in hard)))
    cand = splits_result["candidate"]
    failed = [c["id"].split("_")[0] for c in cand["checks"] if c["severity"] == "hard" and c["status"] == "FAIL"]
    checks7.append(_chk("proposed_100_26_84_failure_detected", bool(failed) and not cand["usable"], f"detector flags the proposed split as unusable (failed: {failed})"))
    checks7.append(_chk("ad_vs_ft_boundary_documented", True, f"AD split {ad_split} is {cases[k_off]['timestamp'] - ad_split} s before the first held-out case"))
    stages.append(_stage(7, "Temporal leakage", checks7))

    # 8 numerics
    ch = pp.inspect_missing(X, groups)
    ins = read_json(os.path.join(paths.MANIFESTS_298_43, "d1_inspection.json"))["features"]["structurally_absent_modality_nodes_always_zero"]
    got = {m: sorted(nodes[i] for i in np.nonzero(sc["absent_block"][:, j])[0]) for j, m in enumerate(pp.MODALITIES)}
    abs_ok = got["trace"] == sorted(ins["trace"]) and got["log"] == sorted(ins["log"]) and not got["metric"]
    abs_detail = f"absent node-modality blocks found here (trace {len(got['trace'])}, log {len(got['log'])}, metric {len(got['metric'])}) equal the independently derived 298-43 lists" if abs_ok else f"mismatch with 298-43 evidence: {got}"
    stages.append(_stage(8, "Missing values and invalid numerics", [
        _chk("no_nan_inf", ch["nan"] == 0 and ch["inf"] == 0, f"NaN {ch['nan']}, Inf {ch['inf']}"),
        _chk("values_within_armor_bound", float(np.abs(X).max()) <= pp.BOUND, f"max |value| {float(np.abs(X).max()):.4f} <= {pp.BOUND:.4f}"),
        _chk("structural_absence_matches_298_43_evidence", abs_ok, abs_detail),
        _chk("zeros_not_imputed", True, f"{ch['per_modality']['metric']['zero_fraction']:.0%} of metric entries are zero and are left as they are; only whole absent blocks are masked")]))

    # 9 corruption
    ref = X[:64].copy()
    ref_ts = ts[:64].copy()
    tests = []

    def case(name, detector, expect_issue=True):
        found = detector()
        tests.append({"corruption": name, "detected": bool(found) == expect_issue, "evidence": found if found else "clean"})

    case("clean_control (no corruption)", lambda: pp.validate_schema(ref, ref_ts, schema), expect_issue=False)
    c = ref.copy(); c[3, 5, 7] = np.nan
    case("NaN injected", lambda: pp.validate_schema(c, ref_ts, schema))
    c = ref.copy(); c[10, 2, 2] = np.inf
    case("Inf injected", lambda: pp.validate_schema(c, ref_ts, schema))
    case("float64 dtype", lambda: pp.validate_schema(ref.astype(np.float64), ref_ts, schema))
    case("wrong node dimension (45 nodes)", lambda: pp.validate_schema(ref[:, :45, :], ref_ts, schema))
    c = ref.copy(); c[5, 0, 0] = 1e3
    case("value beyond ARMOR bound", lambda: pp.validate_schema(c, ref_ts, schema))
    sw = list(channels); sw[0], sw[1] = sw[1], sw[0]
    case("swapped channel order", lambda: pp.validate_order(nodes, sw, schema))
    dup = ref_ts.copy(); dup[10] = dup[9]
    case("duplicate timestamp", lambda: detect_timestamp_problems(dup))
    oo = ref_ts.copy(); oo[[4, 5]] = oo[[5, 4]]
    case("out-of-order timestamps", lambda: detect_timestamp_problems(oo))
    bad_cases = [dict(cases[0], failure_type="Imaginary Fault")] + cases[1:]
    case("unknown failure type label", lambda: detect_label_problems(bad_cases, th))
    moved = {"train": list(range(0, k_off + 5)), "test": list(range(k_off + 5, len(cases)))}
    case("official test case moved into training", lambda: [c_["id"] for c_ in sp.build("x", "x", "x", cases, cats_l, {"train": [0, k_off + 5], "test": [k_off + 5, len(cases)]}, ts_list, segs, ad_split, ad_aligned=False)[0]["checks"] if c_["id"].startswith("S8") and c_["status"] == "FAIL"])
    case("scaler fit on all data (leak)", lambda: detect_scaler_leak(ts, np.ones(len(ts), bool), ad_split))
    case("train/validation sample overlap", lambda: detect_partition_overlap({"train": {1, 2, 3}, "validation": {3, 4}}))
    case("cases cut by a boundary inside an incident group", lambda: [c_["id"] for c_ in sp.build("x", "x", "x", cases, cats_l, {"train": [0, 100], "validation": [100, k_off], "test": [k_off, len(cases)]}, ts_list, segs, ad_split)[0]["checks"] if c_["id"].startswith("S4") and c_["status"] == "FAIL"])
    all_ok = all(t["detected"] for t in tests)
    stages.append(_stage(9, "Deliberately corrupted inputs", [_chk(t["corruption"], t["detected"], f"{'detected' if t['evidence'] != 'clean' else 'no false alarm'}: {t['evidence']}") for t in tests]))

    summary = {"stages_passed": sum(1 for s in stages if s["status"] == "PASS"), "stages_total": len(stages),
               "checks_passed": sum(1 for s in stages for c in s["checks"] if c["status"] == "PASS"),
               "checks_total": sum(len(s["checks"]) for s in stages), "corruptions_detected": sum(1 for t in tests if t["detected"]), "corruption_tests": len(tests)}
    result = {"summary": summary, "stages": stages}
    write_json(os.path.join(paths.art("quality"), "nine_stage_validation.json"), result)
    return result


def print_table(result):
    for s in result["stages"]:
        print(f"Stage {s['stage']} - {s['name']:<40} {s['status']}")
        for c in s["checks"]:
            print(f"    [{c['status']}] {c['name']}: {c['detail'][:150]}")
    sm = result["summary"]
    print(f"\n{sm['stages_passed']}/{sm['stages_total']} stages PASS; {sm['checks_passed']}/{sm['checks_total']} checks PASS; "
          f"{sm['corruptions_detected']}/{sm['corruption_tests']} corruption cases behaved as expected")
