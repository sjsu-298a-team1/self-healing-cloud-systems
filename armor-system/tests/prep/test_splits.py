import unittest

import _paths  # noqa: F401
from prep import splits as sp

CLASSES = list(sp.CLASSES)


def make_cases(gaps):
    ts, t = [], 1_000_000
    for g in gaps:
        t += g
        ts.append(t)
    return [{"timestamp": x} for x in ts]


def sample_grid(cases):
    lo, hi = cases[0]["timestamp"] - 3600, cases[-1]["timestamp"] + 3600
    return list(range(lo, hi, 60))


class SplitTests(unittest.TestCase):
    def test_groups_by_shared_segment_and_overlap(self):
        cases = make_cases([0, 100, 5000, 5000])           # cases 0 and 1 are 100 s apart
        gid = sp.incident_groups([c["timestamp"] for c in cases], [(cases[0]["timestamp"] - 50, cases[1]["timestamp"] + 50)])
        self.assertEqual(gid[0], gid[1])
        self.assertNotEqual(gid[1], gid[2])
        self.assertNotEqual(gid[2], gid[3])
        gid2 = sp.incident_groups([c["timestamp"] for c in cases], [])      # no shared slice, extents overlap
        self.assertEqual(gid2[0], gid2[1])

    def build(self, gaps, ranges, test_start=None):
        cases = make_cases(gaps)
        cats = [CLASSES[i % 5] for i in range(len(cases))]
        segs = [(c["timestamp"] - 100, c["timestamp"] + 300) for c in cases]
        return sp.build("t", "t", "t", cases, cats, ranges, sample_grid(cases), segs, cases[0]["timestamp"] - 1, ad_aligned=False), cases

    def test_clean_split_passes_every_hard_check(self):
        (m, rows), _ = self.build([0] + [5000] * 14, {"train": [0, 9], "test": [9, 15]})
        self.assertTrue(m["usable"])
        self.assertEqual([c["status"] for c in m["checks"] if c["severity"] == "hard"], ["PASS"] * 7)
        self.assertEqual(len(rows), 15)

    def test_boundary_inside_window_reach_fails_and_is_not_usable(self):
        gaps = [0] + [5000] * 8 + [400] + [5000] * 5          # cases 8 and 9 only 400 s apart (< 719 s)
        (m, _), _ = self.build(gaps, {"train": [0, 9], "test": [9, 15]})
        ids = {c["id"].split("_")[0]: c["status"] for c in m["checks"]}
        self.assertEqual(ids["S5"], "FAIL")
        self.assertEqual(ids["S6"], "FAIL")
        self.assertFalse(m["usable"])
        self.assertEqual(m["verdict"], "FAIL")

    def test_group_cut_by_boundary_is_detected(self):
        gaps = [0] + [5000] * 8 + [200] + [5000] * 5
        (m, _), _ = self.build(gaps, {"train": [0, 9], "test": [9, 15]})
        self.assertEqual({c["id"].split("_")[0]: c["status"] for c in m["checks"]}["S4"], "FAIL")

    def test_moving_an_official_test_case_is_detected(self):
        (m, _), _ = self.build([0] + [5000] * 14, {"train": [0, 10], "test": [10, 15]})
        self.assertEqual({c["id"].split("_")[0]: c["status"] for c in m["checks"]}["S8"], "FAIL")

    def test_missing_class_in_a_split_fails_coverage(self):
        (m, _), _ = self.build([0] + [5000] * 14, {"train": [0, 13], "test": [13, 15]})
        self.assertEqual({c["id"].split("_")[0]: c["status"] for c in m["checks"]}["S2"], "FAIL")

    def test_manifest_is_deterministic_and_hash_matches(self):
        (a, _), _ = self.build([0] + [5000] * 14, {"train": [0, 9], "test": [9, 15]})
        (b, _), _ = self.build([0] + [5000] * 14, {"train": [0, 9], "test": [9, 15]})
        self.assertEqual(a["content_sha256"], b["content_sha256"])
        self.assertEqual(a["content_sha256"], sp.content_hash(a))

    def test_boundary_scan_and_rolling_origin(self):
        cases = make_cases([0] + [5000] * 59 + [300] + [5000] * 20)      # a close pair at index 60
        cats = [CLASSES[i % 5] for i in range(len(cases))]
        scan = sp.boundary_scan(cases, cats, [], lo=58, hi=62, end=70)
        self.assertFalse(next(r for r in scan if r["k"] == 60)["boundary_ok"])
        self.assertTrue(next(r for r in scan if r["k"] == 59)["boundary_ok"])
        folds = sp.rolling_origin(cases, cats, [], n_pre=70, first_val_start=30, n_folds=2)
        self.assertEqual(len(folds), 2)
        self.assertEqual(folds[0]["train"][1], folds[0]["validation"][0])
        self.assertEqual(folds[1]["validation"][1], 70)


if __name__ == "__main__":
    unittest.main()
