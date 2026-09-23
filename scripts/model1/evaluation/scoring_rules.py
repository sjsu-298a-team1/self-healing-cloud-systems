"""
Model 1 Phase 6: predeclared scoring-rule ablation formulas.

Exactly three rules, predeclared before any result was seen. No rule may be
added after seeing results (see docs in scoring_ablation.py / the Phase 6
report). All three operate on the SAME (x, reconstruction) pair per window --
only the reduction differs -- so the ablation isolates the scoring rule as
the sole experimental variable, holding the model, checkpoint, and windows
fixed.

x, recon: numpy arrays of shape (N, seq_len=30, n_features=55) for a batch of
windows, or (seq_len, n_features) for a single window. Each function returns
one scalar score per window.
"""
import numpy as np


def score_S1(x, recon):
    """S1 -- existing control: full-window MSE over all 30x55 elements."""
    x = np.asarray(x, dtype=np.float64)
    recon = np.asarray(recon, dtype=np.float64)
    sq_err = (x - recon) ** 2
    if x.ndim == 2:
        return float(sq_err.mean())
    return sq_err.mean(axis=(1, 2))


def score_S2(x, recon):
    """S2 -- current-timestep score: MSE only at the final timestep, over the
    55 features."""
    x = np.asarray(x, dtype=np.float64)
    recon = np.asarray(recon, dtype=np.float64)
    if x.ndim == 2:
        sq_err = (x[-1, :] - recon[-1, :]) ** 2
        return float(sq_err.mean())
    sq_err = (x[:, -1, :] - recon[:, -1, :]) ** 2
    return sq_err.mean(axis=1)


def score_S3(x, recon):
    """S3 -- trailing-5-second score: MSE over only the final 5 timesteps
    (5x55 elements)."""
    x = np.asarray(x, dtype=np.float64)
    recon = np.asarray(recon, dtype=np.float64)
    if x.ndim == 2:
        sq_err = (x[-5:, :] - recon[-5:, :]) ** 2
        return float(sq_err.mean())
    sq_err = (x[:, -5:, :] - recon[:, -5:, :]) ** 2
    return sq_err.mean(axis=(1, 2))


SCORING_RULES = {
    "S1": dict(fn=score_S1, description="full-window MSE over all 30x55 elements"),
    "S2": dict(fn=score_S2, description="MSE at the final timestep only, over 55 features"),
    "S3": dict(fn=score_S3, description="MSE over the final 5 timesteps, over 5x55 elements"),
}
