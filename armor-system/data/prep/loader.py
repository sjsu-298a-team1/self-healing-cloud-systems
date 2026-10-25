"""Load D1 labels, schema and the numeric feature tensors.

Pickles are read with the non-executing symbolic reader and tensors are parsed as raw numbers
(see data/tools). The 7,200 feature tensors are cached once as a compressed NPZ in the Git-ignored
`data/processed/` directory.
"""
import os

import numpy as np

from . import paths  # noqa: F401  (adds data/tools to sys.path)
import d1_checks as ck  # noqa: E402
import pickle_symbolic as ps  # noqa: E402
import torch_blob as tb  # noqa: E402

N_NODES, N_CHANNELS = 46, 130
MODALITIES = ("metric", "trace", "log")


def read_labels(d1=paths.D1_DIR):
    cases = ck.read_cases_csv(os.path.join(d1, "cases", "cases.csv"))
    ad = [int(x) for x in ps.read_symbolic(os.path.join(d1, "cases", "ad_cases.pkl"))]
    hi = os.path.join(d1, "hash_info")
    objs = {n: ps.read_symbolic(os.path.join(hi, f"{n}.pkl")) for n in ("node_hash", "type_hash", "type_dict", "channel_dict")}
    for name, obj in list(objs.items()) + [("ad_cases", ad)]:
        if ps.global_refs(obj):
            raise ValueError(f"{name}.pkl references globals; refusing to treat as literal data")
    node_hash = objs["node_hash"]
    nodes = [n for n, _ in sorted(node_hash.items(), key=lambda kv: kv[1])]
    if sorted(node_hash.values()) != list(range(len(nodes))):
        raise ValueError("node_hash indices are not 0..N-1")
    channels = list(objs["channel_dict"])
    with open(paths.ARMOR_CFG) as fh:
        feat_span = ck.parse_feat_span(fh.read())
    groups = ck.modality_groups(channels, feat_span)["indices"]
    return {"cases": cases, "ad": ad, "nodes": nodes, "node_hash": node_hash, "type_hash": objs["type_hash"],
            "type_dict": {int(k): v for k, v in objs["type_dict"].items()}, "channels": channels,
            "feat_span": feat_span, "groups": {m: groups[m] for m in MODALITIES}}


def category_of(case, labels):
    return labels["type_dict"][labels["type_hash"][case["failure_type"]]]


def _extract(path):
    raw = ps.read_symbolic(path, keep_bytes=True)
    if not isinstance(raw, list) or any((not isinstance(s, list)) or len(s) != 3 for s in raw):
        raise ValueError(f"{path}: expected list of [timestamp, graph, tensor] triples")
    ts = np.asarray([int(s[0]) for s in raw], dtype=np.int64)
    X = np.stack([tb.tensor_to_array(s[2], np) for s in raw]).astype(np.float32)
    return ts, X


def build_cache(d1=paths.D1_DIR, out=paths.CACHE_FILE):
    """Read train_samples.pkl and test_samples.pkl, sort by timestamp, write one NPZ."""
    ts_tr, X_tr = _extract(os.path.join(d1, "samples", "train_samples.pkl"))
    ts_te, X_te = _extract(os.path.join(d1, "samples", "test_samples.pkl"))
    ts = np.concatenate([ts_tr, ts_te])
    X = np.concatenate([X_tr, X_te])
    is_test = np.concatenate([np.zeros(len(ts_tr), bool), np.ones(len(ts_te), bool)])
    order = np.argsort(ts, kind="stable")
    ts, X, is_test = ts[order], X[order], is_test[order]
    if len(set(ts.tolist())) != len(ts):
        raise ValueError("duplicate timestamps across train and test samples")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez_compressed(out, timestamps=ts, X=X, is_test_file=is_test)
    return out


def load_arrays(path=paths.CACHE_FILE, mmap=False):
    if not os.path.exists(path):
        raise FileNotFoundError(f"feature cache missing: {path} (run data/pipeline.py --stage cache)")
    z = np.load(path, mmap_mode="r" if mmap else None)
    return z["timestamps"], z["X"], z["is_test_file"]
