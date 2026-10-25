import os
import tempfile
import unittest

import _paths  # noqa: F401
import d1_checks as ck

YAML = """\
path:
  case_path: data/D1/cases/cases.csv

feat_span:
  metric: [[0, 3], [6, 8]]
  trace: [4, 4]
  log: [5, 5]

missing_modality_config:
  run_all: false
"""


class ChecksTests(unittest.TestCase):
    def test_parse_feat_span_and_groups(self):
        spans = ck.parse_feat_span(YAML)
        self.assertEqual(spans, {"metric": [[0, 3], [6, 8]], "trace": [[4, 4]], "log": [[5, 5]]})
        names = [f"c{i}" for i in range(9)]
        g = ck.modality_groups(names, spans)
        self.assertEqual(g["counts"], {"metric": 7, "trace": 1, "log": 1})
        self.assertTrue(g["covers_all_channels_exactly_once"])
        bad = ck.modality_groups(names + ["extra"], spans)
        self.assertFalse(bad["covers_all_channels_exactly_once"])

    def test_sampling_profile_segments(self):
        p = ck.sampling_profile([0, 60, 120, 600, 660, 5000])
        self.assertEqual((p["count"], p["segments"], p["segment_len_max"], p["sorted_ascending"]), (6, 3, 3, True))
        self.assertEqual(p["step_seconds_top"][0], (60, 3))
        self.assertEqual(ck.sampling_profile([5, 5, 3])["duplicate_timestamps"], 1)

    def test_armor_split_formulas(self):
        self.assertEqual(ck.case_split_index(210, 0.6), 126)
        self.assertEqual(ck.case_split_index(133, 0.6), 79)
        # 10 sorted timestamps -> index int(10 * 0.6) = 6 -> 30
        self.assertEqual(ck.ad_split_timestamp([0, 10, 20], [5, 15, 25, 30, 35, 40, 45], 0.6), 30)

    def test_window_counts_half_open(self):
        ts = [100, 130, 159, 160, 400, 459, 460]
        # case at 200: window [141, 500) holds 159, 160, 400, 459, 460
        self.assertEqual(ck.window_counts([200], ts, before=59, after=300), [5])
        self.assertEqual(ck.window_counts([1000], ts), [0])

    def test_samples_within_tolerance(self):
        flags = ck.samples_within([0, 299, 301, 1000], [600], tolerance=300)
        self.assertEqual(flags, [False, False, True, False])

    def test_class_counts_and_unmapped(self):
        cases = [{"failure_type": "a", "cmdb_id": "x-0"}, {"failure_type": "b", "cmdb_id": "x"},
                 {"failure_type": "a", "cmdb_id": "y-1"}]
        th, td = {"a": 0, "b": 1}, {0: "Alpha", 1: "Beta"}
        c = ck.class_counts(cases, th, td, 0, 2)
        self.assertEqual((c["n"], c["fine"], c["category"]), (2, {"a": 1, "b": 1}, {"Alpha": 1, "Beta": 1}))
        self.assertEqual(ck.unmapped_failure_types(cases + [{"failure_type": "zzz", "cmdb_id": "q"}], th), ["zzz"])
        r = ck.exact_root_cause_in_nodes(cases, {"x-0": 0, "y-1": 1})
        self.assertEqual((r["exact_node_match"], r["not_exact"], r["not_exact_ids"]), (2, 1, ["x"]))

    def test_segments_and_case_offsets(self):
        ts = [0, 60, 120, 1000, 1060]
        bounds = ck.segment_bounds(ts)
        self.assertEqual(bounds, [(0, 120), (1000, 1060)])
        offs, uncovered = ck.case_segment_offsets([60, 1060, 500], bounds)
        self.assertEqual((offs, uncovered), ([(60, 60), (60, 0)], 1))

    def test_window_capacity(self):
        ts = [0, 60, 120, 180, 240, 300, 360, 1000, 1060, 5000]  # runs of 7, 2, 1
        self.assertEqual(ck.window_capacity(ts, window=6), {"runs": 3, "runs_shorter_than_window": 2, "windows": 2})
        self.assertEqual(ck.window_capacity([], window=6), {"runs": 0, "runs_shorter_than_window": 0, "windows": 0})

    def test_block_zscore_evidence(self):
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        rng = np.random.default_rng(0)
        x = rng.normal(size=(180, 4))
        x = (x - x.mean(0)) / x.std(0)
        x[:, 3] = 0.0
        ev = ck.block_zscore_evidence([x])
        self.assertEqual((ev["series_blocks"], ev["constant"], ev["mean0_std1"], ev["other"]), (4, 1, 3, 0))

    def test_read_cases_csv_validates_header(self):
        with tempfile.TemporaryDirectory() as d:
            good = os.path.join(d, "g.csv")
            with open(good, "w") as fh:
                fh.write("timestamp,level,cmdb_id,failure_type\n10,node,n1,T\n")
            self.assertEqual(ck.read_cases_csv(good)[0]["timestamp"], 10)
            bad = os.path.join(d, "b.csv")
            with open(bad, "w") as fh:
                fh.write("ts,level\n1,x\n")
            with self.assertRaises(ValueError):
                ck.read_cases_csv(bad)


if __name__ == "__main__":
    unittest.main()
