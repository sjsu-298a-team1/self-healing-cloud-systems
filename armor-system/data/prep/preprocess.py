"""STEP 5: reusable CPU preprocessing for D1 feature tensors (N, 46, 130).

Design rules
- ARMOR's features are already scaled and 80% of values are exactly 0. A zero is NOT a missing value:
  after ARMOR's scaling 0 equals the series mean. Only whole node-modality blocks that are zero in every
  fit sample are treated as structurally absent (e.g. the 6 `node-*` machines have no trace features).
- Every learned parameter is fit on an explicit `fit_mask` (training period) and nothing else.
- Official ARMOR preprocessing is untouched; this layer is for our own Model 1 data pipeline.
"""
import hashlib
import json

import numpy as np

N_NODES, N_CHANNELS = 46, 130
MODALITIES = ("metric", "trace", "log")
STD_FLOOR = 1e-8
BOUND = float(np.sqrt(179)) + 1e-3          # ARMOR block z-score bound observed in D1


def validate_schema(X, ts, schema):
    """Return a list of issue strings (empty list = valid). Never raises on bad data."""
    issues = []
    if X.ndim != 3 or tuple(X.shape[1:]) != tuple(schema["tensor_shape_per_sample"]):
        issues.append(f"shape {tuple(X.shape)} != (N, {schema['tensor_shape_per_sample'][0]}, {schema['tensor_shape_per_sample'][1]})")
        return issues
    if str(X.dtype) != schema["dtype"]:
        issues.append(f"dtype {X.dtype} != {schema['dtype']}")
    if not np.issubdtype(X.dtype, np.floating):
        return issues
    bad = int((~np.isfinite(X)).sum())
    if bad:
        issues.append(f"{bad} non-finite values (NaN/Inf)")
    else:
        mx = float(np.abs(X).max()) if X.size else 0.0
        if mx > BOUND:
            issues.append(f"max |value| {mx:.4f} exceeds ARMOR's observed bound {BOUND:.4f}")
    if len(ts) != len(X):
        issues.append(f"{len(ts)} timestamps for {len(X)} samples")
    elif len(ts) > 1:
        d = np.diff(ts)
        if (d <= 0).any():
            issues.append("timestamps are not strictly increasing")
    return issues


def validate_order(nodes, channels, schema):
    issues = []
    if list(nodes) != list(schema["node_order"]):
        issues.append("node order differs from the schema")
    if list(channels) != [c["name"] for c in schema["channel_order"]]:
        issues.append("channel order differs from the schema")
    return issues


def inspect_missing(X, groups):
    """Missing/invalid inspection: NaN/Inf counts and zero statistics per modality (zeros are reported, not imputed)."""
    out = {"nan": int(np.isnan(X).sum()), "inf": int(np.isinf(X).sum()), "per_modality": {}}
    for m in MODALITIES:
        sub = X[:, :, groups[m]]
        out["per_modality"][m] = {"channels": len(groups[m]), "zero_fraction": float((sub == 0).mean()),
                                  "node_blocks_all_zero_in_every_sample": int((~(sub != 0).any(axis=(0, 2))).sum())}
    return out


def structural_absence(X_fit, groups):
    """(46, 3) bool: node-modality blocks that are exactly zero in EVERY fit sample (structurally absent)."""
    absent = np.zeros((X_fit.shape[1], len(MODALITIES)), bool)
    for j, m in enumerate(MODALITIES):
        absent[:, j] = ~(X_fit[:, :, groups[m]] != 0).any(axis=(0, 2))
    return absent


def channel_modality_vector(groups, n_channels=N_CHANNELS):
    v = np.empty(n_channels, np.int8)
    for j, m in enumerate(MODALITIES):
        v[groups[m]] = j
    return v


def fit_scaler(X, fit_mask, groups):
    """Fit per node-channel mean/scale on rows where fit_mask is True. Returns a plain dict of arrays.

    Entries of structurally absent node-modality blocks are excluded and later forced to 0. Entries with
    zero spread (constant in the fit set) get scale 1.0 so they stay finite and are flagged.
    """
    fit_mask = np.asarray(fit_mask, bool)
    if fit_mask.shape != (X.shape[0],):
        raise ValueError("fit_mask must have one flag per sample")
    if not fit_mask.any():
        raise ValueError("empty fit set")
    Xf = X[fit_mask].astype(np.float64)
    absent = structural_absence(Xf, groups)
    mean, std = Xf.mean(axis=0), Xf.std(axis=0)
    constant = std < STD_FLOOR
    scale = np.where(constant, 1.0, std)
    cm = channel_modality_vector(groups)
    abs_entry = absent[:, cm]                      # (46, 130)
    mean = np.where(abs_entry, 0.0, mean)
    scale = np.where(abs_entry, 1.0, scale)
    return {"mean": mean.astype(np.float32), "scale": scale.astype(np.float32), "constant": constant & ~abs_entry,
            "absent_block": absent, "absent_entry": abs_entry, "n_fit_samples": int(fit_mask.sum())}


def transform(X, scaler, groups):
    """(X - mean) / scale; structurally absent entries are set to 0. Also returns missing-modality indicators."""
    Xt = (X.astype(np.float32) - scaler["mean"]) / scaler["scale"]
    Xt = np.where(scaler["absent_entry"][None], np.float32(0), Xt).astype(np.float32)
    cm = channel_modality_vector(groups)
    zero_rows = np.stack([(X[:, :, groups[m]] == 0).all(axis=2) for m in MODALITIES], axis=2)   # (N,46,3)
    static = np.broadcast_to(scaler["absent_block"][None], zero_rows.shape)
    return Xt, {"structural_absent": static.astype(np.uint8),
                "observed_all_zero_not_structural": (zero_rows & ~static).astype(np.uint8)}


def make_windows(ts, positions, window=6, horizon=1, step=60):
    """Start positions (into `positions`) of sequences of window+horizon consecutive samples spaced exactly `step` s.

    `positions` are indices into the full arrays, in time order. A window never bridges a gap.
    """
    pos = np.asarray(positions)
    t = np.asarray(ts)[pos]
    need = window + horizon
    out, run_start = [], 0
    for i in range(1, len(pos) + 1):
        if i == len(pos) or t[i] - t[i - 1] != step:
            n = i - run_start
            out.extend(range(run_start, run_start + max(0, n - need + 1)))
            run_start = i
    return pos[np.asarray(out, dtype=int)] if out else pos[:0]   # global index of the first sample of each window


def protect_boundaries(ts, starts, period_lo, period_hi, window=6, horizon=1, step=60):
    """Keep only windows lying wholly inside [period_lo, period_hi) in time. Returns (kept, dropped)."""
    ends = np.asarray(ts)[np.asarray(starts) + (window + horizon - 1)] if len(starts) else np.array([], dtype=np.int64)
    begin = np.asarray(ts)[np.asarray(starts)] if len(starts) else np.array([], dtype=np.int64)
    ok = (begin >= period_lo) & (ends < period_hi)
    return np.asarray(starts)[ok], np.asarray(starts)[~ok]


def config_hash(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def prepare_window(X, ts, scaler, groups, start, window=6):
    """Model-ready example: `window` input steps and the next step as target, transformed with a fitted scaler.

    `start` is the global index of the first sample. Raises if the 7 samples are not consecutive minutes,
    so a window can never bridge a gap. Returns float32 arrays plus the missing-modality indicators.
    """
    sl = slice(start, start + window + 1)
    t = np.asarray(ts)[sl]
    if len(t) != window + 1 or not (np.diff(t) == 60).all():
        raise ValueError("window is not made of consecutive one-minute samples")
    Xt, ind = transform(X[sl], scaler, groups)
    return {"inputs": Xt[:window], "target": Xt[window], "timestamps": t.astype(np.int64),
            "structural_absent": ind["structural_absent"][0],                       # (46, 3), constant over the window
            "observed_all_zero_not_structural": ind["observed_all_zero_not_structural"][:window]}   # (window, 46, 3)
