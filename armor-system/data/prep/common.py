import csv
import datetime
import hashlib
import json
import os

import numpy as np


def iso(ts):
    return datetime.datetime.fromtimestamp(int(ts), datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
        json.dump(obj, fh, indent=2, sort_keys=False, default=_default)
        fh.write("\n")


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def write_csv(path, rows, fieldnames=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fieldnames = fieldnames or list(rows[0])
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def _default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.bool_):
        return bool(o)
    raise TypeError(f"not serializable: {type(o)}")


def root_nodes(cmdb_id, nodes):
    """Indices of graph nodes named by cmdb_id: exact match, else every replica of a service name."""
    if cmdb_id in nodes:
        return [nodes.index(cmdb_id)], "exact"
    reps = [i for i, n in enumerate(nodes) if n.rsplit("-", 1)[0] == cmdb_id]
    return reps, ("service_replicas" if reps else "unresolved")


def nearest_index(sorted_ts, t, tol):
    i = int(np.searchsorted(sorted_ts, t))
    cand = [j for j in (i - 1, i) if 0 <= j < len(sorted_ts)]
    j = min(cand, key=lambda k: abs(int(sorted_ts[k]) - t))
    return j if abs(int(sorted_ts[j]) - t) <= tol else None
