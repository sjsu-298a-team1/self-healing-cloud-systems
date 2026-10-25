import copy
import csv
import hashlib
import os
import tempfile
import unittest

import _paths  # noqa: F401
import validate_d1 as v


def summary():
    return {
        "cases": {"n_cases": 210, "distinct_categories": 5, "distinct_fine_failure_types": 15,
                  "unmapped_failure_types": [], "ad_cases_not_in_cases_csv": 21, "cases_csv_not_in_ad_cases": 7},
        "features": {"n_nodes": 46, "n_channels": 130, "nan_total": 0, "inf_total": 0,
                     "modality_groups": {"counts": {"metric": 110, "log": 11, "trace": 9},
                                         "covers_all_channels_exactly_once": True},
                     "scaling_evidence_per_node_channel": {"train_only": {"fraction_of_nonconstant": 0.0025}}},
        "split_and_leakage": {
            "samples": {"train_samples": {"count": 3714}, "samples_pkl": {"step_seconds_top": [[60, 7195]]},
                        "train_test_timestamp_overlap": 0,
                        "samples_pkl_is_exact_union_of_train_and_test_by_timestamp_and_values": True},
            "pretraining_exposure": {"train_samples_after_ad_split_ts": 1445}},
    }


class ValidateTests(unittest.TestCase):
    def test_all_hypotheses_verified_on_expected_summary(self):
        res = {r["id"]: r["status"] for r in v.run_hypotheses(summary())}
        self.assertTrue(all(res[k] == "VERIFIED" for k in ("failure_cases", "nodes", "metric_channels", "normal_samples")))
        self.assertNotIn("MISMATCH", res.values())
        self.assertEqual(res["ad_events_equal_cases"], "DISCREPANCY_CONFIRMED")
        self.assertEqual(res["pretraining_set_precedes_ad_split"], "DISCREPANCY_CONFIRMED")

    def test_detects_mismatch_and_missing_keys(self):
        s = copy.deepcopy(summary())
        s["cases"]["n_cases"] = 209
        del s["features"]["n_nodes"]
        res = {r["id"]: r for r in v.run_hypotheses(s)}
        self.assertEqual(res["failure_cases"]["status"], "MISMATCH")
        self.assertEqual(res["nodes"]["status"], "MISMATCH")
        self.assertIn("error", res["nodes"])

    def test_inventory_rehash_flags_changed_and_missing(self):
        with tempfile.TemporaryDirectory() as d:
            for name, data in (("a.txt", b"one"), ("b.txt", b"two")):
                with open(os.path.join(d, name), "wb") as fh:
                    fh.write(data)
            inv = os.path.join(d, "inv.csv")
            with open(inv, "w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["path", "bytes", "format", "sha256"])
                w.writerow(["a.txt", 3, "other", hashlib.sha256(b"one").hexdigest()])
                w.writerow(["b.txt", 3, "other", hashlib.sha256(b"two").hexdigest()])
                w.writerow(["c.txt", 3, "other", hashlib.sha256(b"three").hexdigest()])
            with open(os.path.join(d, "b.txt"), "wb") as fh:
                fh.write(b"TWO")
            out = v.verify_inventory(d, inv)
            self.assertEqual(out["files_checked"], 3)
            self.assertEqual(sorted(out["problems"]), ["changed: b.txt", "missing: c.txt"])


if __name__ == "__main__":
    unittest.main()
