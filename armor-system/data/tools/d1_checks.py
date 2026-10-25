"""Pure, stdlib-only verification helpers for the ARMOR D1 release.

Each function mirrors an ARMOR protocol detail (the formula is cited in the
docstring) so that audits of the official split do not depend on running the
official code. Nothing here modifies a split.
"""
import ast
import bisect
import csv
import re
from collections import Counter


def read_cases_csv(path):
    """Read cases.csv -> list of {timestamp:int, level, cmdb_id, failure_type}."""
    with open(path, newline="") as fh:
        rows = list(csv.DictReader(fh))
    required = {"timestamp", "level", "cmdb_id", "failure_type"}
    if not rows or set(rows[0]) != required:
        raise ValueError(f"unexpected cases.csv header: {list(rows[0]) if rows else None}")
    for r in rows:
        r["timestamp"] = int(r["timestamp"])
    return rows


def parse_feat_span(yaml_text):
    """Extract the `feat_span` block of a config as {modality: [[start,end],...]} (inclusive).

    Parsed with a regex plus ast.literal_eval so no YAML dependency or code execution is needed.
    """
    block = re.search(r"^feat_span:\s*\n((?:[ \t]+\S.*\n?)+)", yaml_text, re.M)
    if not block:
        raise ValueError("feat_span block not found")
    spans = {}
    for line in block.group(1).splitlines():
        m = re.match(r"\s+(\w+):\s*(\[.*\])\s*$", line)
        if m:
            val = ast.literal_eval(m.group(2))
            spans[m.group(1)] = val if isinstance(val[0], list) else [val]
    return spans


def span_indices(spans):
    """Inclusive spans -> sorted channel index list (ARMOR uses range(start, end + 1))."""
    out = []
    for s, e in spans:
        out.extend(range(s, e + 1))
    return sorted(out)


def modality_groups(channel_names, feat_span):
    """Map each modality to its channel indices and names; check coverage and disjointness."""
    groups = {m: span_indices(sp) for m, sp in feat_span.items()}
    all_idx = [i for idx in groups.values() for i in idx]
    return {
        "counts": {m: len(idx) for m, idx in groups.items()},
        "total_channels": len(channel_names),
        "covers_all_channels_exactly_once": sorted(all_idx) == list(range(len(channel_names))),
        "names": {m: [channel_names[i] for i in idx] for m, idx in groups.items()},
        "indices": groups,
    }


def sampling_profile(timestamps, gap_threshold=60):
    """Describe timestamp ordering, spacing and contiguous segments.

    A new segment starts whenever the step exceeds `gap_threshold` seconds.
    """
    ts = list(timestamps)
    diffs = [b - a for a, b in zip(ts, ts[1:])]
    segments, start = [], 0
    for i, d in enumerate(diffs):
        if d > gap_threshold:
            segments.append((start, i))
            start = i + 1
    if ts:
        segments.append((start, len(ts) - 1))
    seg_lens = [e - s + 1 for s, e in segments]
    return {
        "count": len(ts),
        "min": min(ts) if ts else None,
        "max": max(ts) if ts else None,
        "sorted_ascending": ts == sorted(ts),
        "duplicate_timestamps": len(ts) - len(set(ts)),
        "step_seconds_top": Counter(diffs).most_common(8),
        "segments": len(segments),
        "segment_len_min": min(seg_lens) if seg_lens else None,
        "segment_len_median": sorted(seg_lens)[len(seg_lens) // 2] if seg_lens else None,
        "segment_len_max": max(seg_lens) if seg_lens else None,
    }


def ad_split_timestamp(train_ts, test_ts, ratio=0.6):
    """ARMOR AD split point (anomaly_detector.AD): ts_list[int(len * ratio)] over train+test sorted."""
    ts_list = sorted(list(train_ts) + list(test_ts))
    return ts_list[int(len(ts_list) * ratio)]


def case_split_index(n_cases, ratio=0.6):
    """ARMOR FT/RCL split: cases[:idx] train, cases[idx:] test with idx = int(n * ratio)."""
    return int(n_cases * ratio)


def window_counts(case_timestamps, sample_ts_sorted, before=59, after=300):
    """Samples falling in [case-before, case+after) for each case (ARMOR aggregate_* windows)."""
    out = []
    for c in case_timestamps:
        lo = bisect.bisect_left(sample_ts_sorted, c - before)
        hi = bisect.bisect_left(sample_ts_sorted, c + after)
        out.append(hi - lo)
    return out


def samples_within(sample_ts, event_ts_sorted, tolerance=300):
    """Flag each sample timestamp that lies within +/- tolerance of any event timestamp."""
    flags = []
    for t in sample_ts:
        i = bisect.bisect_left(event_ts_sorted, t)
        near = False
        for j in (i - 1, i):
            if 0 <= j < len(event_ts_sorted) and abs(event_ts_sorted[j] - t) <= tolerance:
                near = True
        flags.append(near)
    return flags


def class_counts(cases, type_hash, type_dict, start=0, stop=None):
    """Per-fine-type and per-category counts for cases[start:stop]."""
    subset = cases[start:stop]
    fine = Counter(c["failure_type"] for c in subset)
    cat = Counter(type_dict[type_hash[c["failure_type"]]] for c in subset)
    return {"n": len(subset), "fine": dict(fine), "category": dict(cat)}


def unmapped_failure_types(cases, type_hash):
    return sorted({c["failure_type"] for c in cases if c["failure_type"] not in type_hash})


def exact_root_cause_in_nodes(cases, node_hash):
    """Cases whose cmdb_id is exactly a graph node, vs not (substring matching needed)."""
    exact = [c for c in cases if c["cmdb_id"] in node_hash]
    return {"exact_node_match": len(exact), "not_exact": len(cases) - len(exact),
            "not_exact_ids": sorted({c["cmdb_id"] for c in cases if c["cmdb_id"] not in node_hash})}


def segment_bounds(ts_sorted, gap_threshold=60):
    """Contiguous runs of timestamps (step <= gap_threshold) as (start_ts, end_ts) pairs."""
    if not ts_sorted:
        return []
    bounds, start = [], ts_sorted[0]
    for a, b in zip(ts_sorted, ts_sorted[1:]):
        if b - a > gap_threshold:
            bounds.append((start, a))
            start = b
    bounds.append((start, ts_sorted[-1]))
    return bounds


def case_segment_offsets(case_timestamps, bounds):
    """For each case, seconds from its containing segment start to the case, and case to segment end.

    Returns (offsets, uncovered_cases) where offsets is a list of (before, after) seconds.
    """
    starts = [b[0] for b in bounds]
    offsets, uncovered = [], 0
    for c in case_timestamps:
        i = bisect.bisect_right(starts, c) - 1
        if i >= 0 and bounds[i][0] <= c <= bounds[i][1]:
            offsets.append((c - bounds[i][0], bounds[i][1] - c))
        else:
            uncovered += 1
    return offsets, uncovered


def block_zscore_evidence(blocks, tol=1e-3):
    """Count series-blocks that are constant, mean0/std1 within tol, or other.

    `blocks` is an iterable of 2-D sequences shaped (samples, series) given as nested lists of floats
    or any object exposing .mean(axis=0)/.std(axis=0) (e.g. numpy arrays).
    """
    import numpy as np
    out = {"series_blocks": 0, "constant": 0, "mean0_std1": 0, "other": 0}
    for B in blocks:
        B = np.asarray(B, dtype="float64").reshape(len(B), -1)
        mu, sd = B.mean(axis=0), B.std(axis=0)
        const = sd < 1e-9
        ok = (~const) & (np.abs(mu) < tol) & (np.abs(sd - 1) < tol)
        out["series_blocks"] += int(sd.size)
        out["constant"] += int(const.sum())
        out["mean0_std1"] += int(ok.sum())
        out["other"] += int((~const & ~ok).sum())
    return out


def window_capacity(ts_sorted, window=6, step=60):
    """Count overlapping `window`-step windows that lie entirely inside contiguous runs.

    A run is contiguous when consecutive timestamps differ by exactly `step` seconds.
    Returns {"runs", "runs_shorter_than_window", "windows"}.
    """
    runs, length = [], 1 if ts_sorted else 0
    for a, b in zip(ts_sorted, ts_sorted[1:]):
        if b - a == step:
            length += 1
        else:
            runs.append(length)
            length = 1
    if length:
        runs.append(length)
    return {"runs": len(runs),
            "runs_shorter_than_window": sum(1 for r in runs if r < window),
            "windows": sum(max(0, r - window + 1) for r in runs)}
