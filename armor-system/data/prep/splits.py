"""Chronological, incident-group-aware split manifests for D1.

Nothing here is random. Cases are ordered as in cases.csv (strictly ascending in time) and split by
index. A candidate is evaluated against explicit checks and only a candidate whose hard checks pass
is marked usable. Hard failures are recorded, never hidden.
"""
import bisect
import hashlib
import json
from collections import Counter

from . import paths  # noqa: F401
import d1_checks as ck  # noqa: E402

MANIFEST_VERSION = "1.0"
BEFORE, AFTER = 59, 300            # ARMOR case aggregation window [ts-59, ts+300)
HISTORY = 360                      # ARMOR input history: 6 one-minute steps before the target
REQUIRED_SPAN = BEFORE + AFTER + HISTORY   # 719 s a later case reaches back plus an earlier case reaches forward
MIN_CLASS_SUPPORT = 3              # advisory threshold for a stable per-class estimate
CLASSES = ("Container Hardware", "Container Network", "Node CPU", "Node Disk", "Node Memory")


def case_extent(ts):
    """Seconds [start, end) of everything a case's features may touch (history + aggregation window)."""
    return ts - BEFORE - HISTORY, ts + AFTER


def incident_groups(case_ts, test_segment_bounds):
    """Group cases whose evidence cannot be separated: same contiguous test slice, or overlapping extents."""
    n = len(case_ts)
    parent = list(range(n))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        parent[find(a)] = find(b)

    starts = [b[0] for b in test_segment_bounds]
    seg_of = []
    for t in case_ts:
        i = bisect.bisect_right(starts, t) - 1
        seg_of.append(i if i >= 0 and test_segment_bounds[i][0] <= t <= test_segment_bounds[i][1] else None)
    first_in_seg = {}
    for k, s in enumerate(seg_of):
        if s is None:
            continue
        if s in first_in_seg:
            union(first_in_seg[s], k)
        else:
            first_in_seg[s] = k
    for k in range(n - 1):
        if case_extent(case_ts[k + 1])[0] < case_extent(case_ts[k])[1]:
            union(k, k + 1)
    roots = {}
    gid = []
    for k in range(n):
        r = find(k)
        roots.setdefault(r, len(roots))
        gid.append(roots[r])
    return gid


def _boundaries(cases, ranges, ad_split_ts, ad_aligned):
    """Sample-time boundaries between consecutive splits (seconds, split B starts at boundary)."""
    names = list(ranges)
    out = []
    for a, b in zip(names, names[1:]):
        last_a = cases[ranges[a][1] - 1]["timestamp"]
        first_b = cases[ranges[b][0]]["timestamp"]
        lo, hi = case_extent(last_a)[1], case_extent(first_b)[0]
        mid = (lo + hi) // 2
        use_ad = ad_aligned and b == names[-1] and lo <= ad_split_ts <= hi
        out.append({"between": [a, b], "boundary_ts": ad_split_ts if use_ad else mid,
                    "rule": "AD split time (lies inside the safe gap)" if use_ad else "midpoint of the safe gap",
                    "last_case_extent_end": lo, "first_case_extent_start": hi,
                    "safe_gap_seconds": hi - lo,
                    "case_to_case_seconds": first_b - last_a})
    return out


def _period_of(ts, boundary_list, names):
    k = bisect.bisect_right(boundary_list, ts)
    return names[k]


def build(name, status, description, cases, categories, ranges, sample_ts, test_segs, ad_split_ts, ad_aligned=True, extra=None):
    """Return (manifest, per-case assignment rows). `ranges`: {split: [start_idx, end_idx_exclusive]}."""
    case_ts = [c["timestamp"] for c in cases]
    gid = incident_groups(case_ts, test_segs)
    names = list(ranges)
    split_of = {}
    for s, (a, b) in ranges.items():
        for i in range(a, b):
            split_of[i] = s
    assert sorted(split_of) == list(range(len(cases))), "ranges must cover every case exactly once"
    bounds = _boundaries(cases, ranges, ad_split_ts, ad_aligned)
    blist = [b["boundary_ts"] for b in bounds]

    def counts(s):
        a, b = ranges[s]
        c = Counter(categories[a:b])
        return {k: c.get(k, 0) for k in CLASSES}

    sample_split = [_period_of(t, blist, names) for t in sample_ts]
    sample_counts = Counter(sample_split)
    checks = []

    def chk(cid, severity, ok, detail, warn=False):
        status_ = "PASS" if ok else ("WARN" if warn else "FAIL")
        checks.append({"id": cid, "severity": severity, "status": status_, "detail": detail})

    # S1 chronology
    inc = all(b > a for a, b in zip(case_ts, case_ts[1:]))
    chk("S1_chronological_order", "hard", inc,
        "case timestamps strictly increase in file order; splits are contiguous index ranges in that order"
        if inc else "case timestamps are not strictly increasing")
    # S2 coverage
    miss = {s: [k for k, v in counts(s).items() if v == 0] for s in names}
    chk("S2_class_coverage", "hard", not any(miss.values()),
        "every class appears in every split" if not any(miss.values()) else f"classes absent from splits: { {s: m for s, m in miss.items() if m} }")
    # S3 support
    low = {s: {k: v for k, v in counts(s).items() if v < MIN_CLASS_SUPPORT} for s in names}
    chk("S3_minimum_class_support", "advisory", not any(low.values()),
        f"every split-class has >= {MIN_CLASS_SUPPORT} cases" if not any(low.values())
        else f"split-classes below {MIN_CLASS_SUPPORT} cases (per-class metrics unstable): { {s: m for s, m in low.items() if m} }", warn=True)
    # S4 isolation
    spans = {}
    for i, g in enumerate(gid):
        spans.setdefault(g, set()).add(split_of[i])
    cut = {g: sorted(v) for g, v in spans.items() if len(v) > 1}
    chk("S4_incident_group_isolation", "hard", not cut,
        f"{len(spans)} incident groups, none spans two splits" if not cut else f"incident groups spanning splits: {cut}")
    # S5 boundary gap
    bad = [b for b in bounds if b["safe_gap_seconds"] <= 0]
    chk("S5_boundary_window_gap", "hard", not bad,
        f"every boundary has a positive safe gap (>= {min([b['safe_gap_seconds'] for b in bounds] or [0])} s after allowing {REQUIRED_SPAN} s of window reach)"
        if not bad else "boundary extents overlap: " + "; ".join(
            f"{b['between'][0]}|{b['between'][1]} cases {b['case_to_case_seconds']} s apart, needs > {REQUIRED_SPAN} s" for b in bad))
    # S6 extent inside period
    outside = []
    for i, t in enumerate(case_ts):
        lo, hi = case_extent(t)
        k = names.index(split_of[i])
        p_lo = blist[k - 1] if k > 0 else -10 ** 18
        p_hi = blist[k] if k < len(blist) else 10 ** 18
        if lo < p_lo or hi > p_hi:
            outside.append(i)
    chk("S6_case_extent_inside_period", "hard", not outside,
        "every case's history + window lies inside its split's time period" if not outside
        else f"{len(outside)} cases reach across a split boundary (case indices {outside})")
    # S7 partition
    chk("S7_sample_partition_complete_disjoint", "hard", sum(sample_counts.values()) == len(sample_ts),
        f"{len(sample_ts)} samples assigned once each: {dict(sample_counts)}")
    # S8 official test unchanged
    off_test = list(range(ck.case_split_index(len(cases), 0.6), len(cases)))
    test_idx = list(range(*ranges[names[-1]]))
    chk("S8_official_test_cases_unchanged", "hard", test_idx == off_test,
        "held-out set equals ARMOR's last 84 cases; no official test case moved" if test_idx == off_test
        else "held-out set differs from ARMOR's official test cases")
    # S9 info on AD vs FT boundary
    first_test = case_ts[ranges[names[-1]][0]]
    chk("S9_ad_vs_ft_boundary_difference", "info", True,
        f"AD split {ad_split_ts} (sample-based, 60% of samples) vs first held-out case {first_test} (case-based, 60% of cases): "
        f"AD boundary is {first_test - ad_split_ts} s earlier; FT/RCL use cases only, AD uses samples")

    hard_fail = [c for c in checks if c["severity"] == "hard" and c["status"] == "FAIL"]
    warn = [c for c in checks if c["status"] == "WARN"]
    verdict = "FAIL" if hard_fail else ("PASS_WITH_WARNINGS" if warn else "PASS")
    manifest = {
        "manifest_version": MANIFEST_VERSION, "name": name, "status": status, "description": description,
        "verdict": verdict, "usable": not hard_fail,
        "ordering": "cases.csv file order (strictly ascending timestamp); chronological, no random assignment",
        "window_parameters": {"before_s": BEFORE, "after_s": AFTER, "history_s": HISTORY, "required_span_s": REQUIRED_SPAN},
        "case_ranges": {s: {"start_index": a, "end_index_exclusive": b, "n_cases": b - a,
                            "first_case_ts": case_ts[a], "last_case_ts": case_ts[b - 1], "class_counts": counts(s)}
                        for s, (a, b) in ranges.items()},
        "ad_split": {"timestamp": ad_split_ts, "utc": _utc(ad_split_ts), "first_heldout_case_ts": first_test, "seconds_before_first_heldout_case": first_test - ad_split_ts},
        "sample_time_boundaries": bounds,
        "sample_partition": {s: sample_counts.get(s, 0) for s in names},
        "incident_groups": {"n_groups": len(set(gid)), "groups_with_multiple_cases": sum(1 for g in set(gid) if gid.count(g) > 1)},
        "checks": checks,
    }
    if extra:
        manifest.update(extra)
    manifest["content_sha256"] = content_hash(manifest)
    rows = [{"case_index": i, "split": split_of[i], "group_id": gid[i]} for i in range(len(cases))]
    return manifest, rows


def _utc(ts):
    import datetime
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def content_hash(manifest):
    body = {k: v for k, v in manifest.items() if k != "content_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def boundary_scan(cases, categories, test_segs, lo=90, hi=112, end=126):
    """Evaluate candidate train|val boundary indices k (train=[0,k), val=[k,end)) without choosing one."""
    case_ts = [c["timestamp"] for c in cases]
    gid = incident_groups(case_ts, test_segs)
    out = []
    for k in range(lo, hi + 1):
        gap = case_ts[k] - case_ts[k - 1] - REQUIRED_SPAN
        iso = gid[k] != gid[k - 1]
        val = Counter(categories[k:end])
        out.append({"k": k, "train_cases": k, "val_cases": end - k, "case_to_case_seconds": case_ts[k] - case_ts[k - 1],
                    "safe_gap_seconds": gap, "boundary_ok": gap > 0 and iso,
                    "val_class_counts": {c: val.get(c, 0) for c in CLASSES}})
    return out


def rolling_origin(cases, categories, test_segs, n_pre=126, first_val_start=42, n_folds=2):
    """Forward-chaining folds over the pre-test cases: train on everything earlier, validate on the next block."""
    case_ts = [c["timestamp"] for c in cases]
    gid = incident_groups(case_ts, test_segs)
    size = (n_pre - first_val_start) // n_folds
    folds, start = [], first_val_start
    for f in range(n_folds):
        end = n_pre if f == n_folds - 1 else start + size
        k = start
        while k < end and not (case_ts[k] - case_ts[k - 1] - REQUIRED_SPAN > 0 and gid[k] != gid[k - 1]):
            k += 1                                   # move boundary forward to the first safe index
        val = Counter(categories[k:end])
        trn = Counter(categories[:k])
        folds.append({"fold": f + 1, "train": [0, k], "validation": [k, end], "boundary_moved_from": start if k != start else None,
                      "train_class_counts": {c: trn.get(c, 0) for c in CLASSES},
                      "validation_class_counts": {c: val.get(c, 0) for c in CLASSES}})
        start = end
    return folds
