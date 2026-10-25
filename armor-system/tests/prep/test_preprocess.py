import unittest

import numpy as np

import _paths  # noqa: F401
from prep import preprocess as pp

GROUPS = {"metric": list(range(0, 110)), "trace": list(range(110, 119)), "log": list(range(119, 130))}
SCHEMA = {"tensor_shape_per_sample": [46, 130], "dtype": "float32", "node_order": [f"n{i}" for i in range(46)],
          "channel_order": [{"name": f"c{i}"} for i in range(130)]}


def make(n=40, seed=0):
    rng = np.random.default_rng(seed)
    X = rng.normal(size=(n, 46, 130)).astype(np.float32)
    X[:, 0, 110:119] = 0                    # node 0: trace block zero in every sample (structural)
    X[:, 2, 5] = 0.0                        # a constant channel for node 2
    X[rng.random(X.shape) < 0.5] = 0        # lots of scattered zeros, as in D1
    X[:, 0, 110:119] = 0
    X[:, 1, 110] = rng.normal(size=n)       # keep node 1's trace block clearly non-structural
    X[:, 2, 5] = 0.0
    X[3, 1, 110:119] = 0                    # node 1: trace block zero in a single sample (NOT structural)
    return X


class SchemaTests(unittest.TestCase):
    def test_valid_and_invalid_inputs(self):
        X, ts = make(), np.arange(40) * 60
        self.assertEqual(pp.validate_schema(X, ts, SCHEMA), [])
        bad = X.copy(); bad[0, 0, 0] = np.nan
        self.assertTrue(any("non-finite" in i for i in pp.validate_schema(bad, ts, SCHEMA)))
        self.assertTrue(any("dtype" in i for i in pp.validate_schema(X.astype(np.float64), ts, SCHEMA)))
        self.assertTrue(any("shape" in i for i in pp.validate_schema(X[:, :45], ts, SCHEMA)))
        self.assertTrue(any("increasing" in i for i in pp.validate_schema(X, np.r_[ts[:-1], ts[-2]], SCHEMA)))

    def test_order_validation(self):
        nodes, ch = SCHEMA["node_order"], [c["name"] for c in SCHEMA["channel_order"]]
        self.assertEqual(pp.validate_order(nodes, ch, SCHEMA), [])
        self.assertTrue(pp.validate_order(nodes, ch[::-1], SCHEMA))


class ScalerTests(unittest.TestCase):
    def test_zero_is_not_missing_only_all_zero_blocks_are_absent(self):
        X = make()
        absent = pp.structural_absence(X, GROUPS)
        self.assertTrue(absent[0, 1])               # trace of node 0 is zero in every sample
        self.assertFalse(absent[1, 1])              # one zero row does not make a block absent
        self.assertFalse(absent[:, 0].any())        # metric blocks have scattered zeros but are not absent

    def test_scaler_is_fit_on_the_fit_mask_only(self):
        X = make()
        fit = np.arange(len(X)) < 20
        a = pp.fit_scaler(X, fit, GROUPS)
        Y = X.copy(); Y[~fit] = Y[~fit] * 9 + 3
        b = pp.fit_scaler(Y, fit, GROUPS)
        np.testing.assert_array_equal(a["mean"], b["mean"])
        np.testing.assert_array_equal(a["scale"], b["scale"])
        c = pp.fit_scaler(X, np.ones(len(X), bool), GROUPS)
        self.assertFalse(np.allclose(a["mean"], c["mean"]))
        with self.assertRaises(ValueError):
            pp.fit_scaler(X, np.zeros(len(X), bool), GROUPS)

    def test_transform_properties(self):
        X = make()
        fit = np.arange(len(X)) < 30
        sc = pp.fit_scaler(X, fit, GROUPS)
        Xt, ind = pp.transform(X, sc, GROUPS)
        self.assertTrue(np.isfinite(Xt).all())
        self.assertEqual(Xt.dtype, np.float32)
        self.assertTrue((Xt[:, 0, 110:119] == 0).all())             # absent block forced to 0
        self.assertTrue(sc["constant"][2, 5])                      # constant entry flagged ...
        self.assertTrue((Xt[:, 2, 5] == 0).all())                  # ... and stays finite (scale 1, mean 0)
        live = ~sc["constant"] & ~sc["absent_entry"]
        fit_vals = Xt[fit][:, live]
        self.assertAlmostEqual(float(fit_vals.mean(axis=0).mean()), 0.0, places=4)
        self.assertEqual(ind["structural_absent"].shape, (40, 46, 3))
        self.assertEqual(int(ind["structural_absent"][:, 0, 1].min()), 1)
        self.assertEqual(int(ind["observed_all_zero_not_structural"][3, 1, 1]), 1)     # the lone zero row is flagged separately
        self.assertEqual(int(ind["observed_all_zero_not_structural"][:, 0, 1].max()), 0)  # structural rows are not double counted


class WindowTests(unittest.TestCase):
    def test_windows_never_bridge_gaps(self):
        ts = np.r_[np.arange(10) * 60, 100_000 + np.arange(10) * 60]
        starts = pp.make_windows(ts, np.arange(20), window=6, horizon=1)
        self.assertEqual(len(starts), 2 * (10 - 7 + 1))
        for s in starts:
            seg = ts[s:s + 7]
            self.assertTrue((np.diff(seg) == 60).all())

    def test_short_runs_yield_no_windows(self):
        ts = np.r_[np.arange(5) * 60, 10_000 + np.arange(5) * 60]
        self.assertEqual(len(pp.make_windows(ts, np.arange(10), window=6, horizon=1)), 0)

    def test_boundary_protection_drops_crossing_windows(self):
        ts = np.arange(30) * 60
        starts = pp.make_windows(ts, np.arange(30), window=6, horizon=1)
        kept, dropped = pp.protect_boundaries(ts, starts, 0, 20 * 60, window=6, horizon=1)
        self.assertTrue(all(ts[s + 6] < 20 * 60 for s in kept))
        self.assertEqual(len(kept) + len(dropped), len(starts))
        self.assertGreater(len(dropped), 0)


if __name__ == "__main__":
    unittest.main()
