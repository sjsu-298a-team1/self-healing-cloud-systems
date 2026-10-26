import unittest

import numpy as np

import _paths  # noqa: F401
from prep import quality as q


class DetectorTests(unittest.TestCase):
    def test_timestamp_detectors(self):
        self.assertEqual(q.detect_timestamp_problems(np.array([0, 60, 120])), [])
        self.assertIn("duplicate timestamps", q.detect_timestamp_problems(np.array([0, 60, 60, 120])))
        self.assertIn("timestamps out of order", q.detect_timestamp_problems(np.array([0, 120, 60])))

    def test_label_detector(self):
        cases = [{"failure_type": "A"}, {"failure_type": "B"}]
        self.assertEqual(q.detect_label_problems(cases, {"A": 0, "B": 1}), [])
        self.assertEqual(len(q.detect_label_problems(cases, {"A": 0})), 1)

    def test_partition_overlap_detector(self):
        self.assertEqual(q.detect_partition_overlap({"a": {1, 2}, "b": {3}}), [])
        self.assertEqual(len(q.detect_partition_overlap({"a": {1, 2}, "b": {2, 3}})), 1)

    def test_scaler_leak_detector(self):
        ts = np.arange(10)
        self.assertEqual(q.detect_scaler_leak(ts, ts <= 4, 4), [])
        self.assertEqual(len(q.detect_scaler_leak(ts, np.ones(10, bool), 4)), 1)


    def test_count_mismatch_detector(self):
        exp = {"train": {"A": 2, "B": 1}, "test": {"A": 3}}
        self.assertEqual(q.detect_count_mismatch({"train": {"A": 2, "B": 1}, "test": {"A": 3}}, exp), [])
        self.assertEqual(len(q.detect_count_mismatch({"train": {"A": 2, "B": 2}, "test": {"A": 3}}, exp)), 1)


if __name__ == "__main__":
    unittest.main()
