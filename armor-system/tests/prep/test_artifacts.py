"""Integration checks on the committed, generated artifacts (skipped if they have not been generated)."""
import json
import os
import unittest

import numpy as np

import _paths  # noqa: F401
from prep import paths, splits as sp

ART = paths.ART


def load(*p):
    with open(os.path.join(ART, *p)) as fh:
        return json.load(fh)


@unittest.skipUnless(os.path.exists(os.path.join(ART, "splits", "official_armor_v1.json")), "artifacts not generated")
class ArtifactTests(unittest.TestCase):
    def test_official_split_is_the_armor_reproduction_split(self):
        m = load("splits", "official_armor_v1.json")
        self.assertEqual((m["case_ranges"]["train"]["n_cases"], m["case_ranges"]["test"]["n_cases"]), (126, 84))
        self.assertTrue(m["usable"])
        self.assertEqual(m["status"], "approved_reproduction")

    def test_rejected_split_is_honestly_marked_failing(self):
        m = load("splits", "model1_candidate_100_26_84_v1.json")
        self.assertFalse(m["usable"])
        self.assertEqual(m["verdict"], "FAIL")
        self.assertEqual(m["status"], "rejected_fails_hard_checks")
        failed = {c["id"].split("_")[0] for c in m["checks"] if c["status"] == "FAIL"}
        self.assertTrue({"S4", "S5", "S6"} <= failed)

    def test_approved_101_25_84_split(self):
        m = load("splits", "model1_split_101_25_84_v1.json")
        self.assertEqual(m["status"], "approved")
        self.assertTrue(m["usable"])
        self.assertEqual([m["case_ranges"][k]["n_cases"] for k in ("train", "validation", "test")], [101, 25, 84])
        approved = {"train": [37, 32, 10, 18, 4], "validation": [10, 6, 3, 5, 1], "test": [36, 22, 8, 14, 4]}
        for s_, counts in approved.items():
            self.assertEqual(list(m["case_ranges"][s_]["class_counts"].values()), counts)
        self.assertTrue(all(c["status"] == "PASS" for c in m["checks"] if c["severity"] == "hard"))
        self.assertTrue(any("single Node Memory case" in x for x in m["statistical_limitations"]))
        off = load("splits", "official_armor_v1.json")
        self.assertEqual(m["case_ranges"]["test"]["first_case_ts"], off["case_ranges"]["test"]["first_case_ts"])
        self.assertEqual(m["case_ranges"]["test"]["n_cases"], off["case_ranges"]["test"]["n_cases"])

    def test_manifest_hashes_are_self_consistent(self):
        for n in ("official_armor_v1", "model1_candidate_100_26_84_v1", "model1_split_101_25_84_v1"):
            m = load("splits", f"{n}.json")
            self.assertEqual(m["content_sha256"], sp.content_hash(m))

    def test_no_case_is_in_two_splits_and_all_are_assigned(self):
        import csv
        with open(os.path.join(ART, "splits", "case_split_assignments.csv")) as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 210)
        for key in ("official_split", "rejected_100_26_84_split", "model1_split"):
            self.assertTrue(all(r[key] in ("train", "validation", "test") for r in rows))
        off_test = [r["case_index"] for r in rows if r["official_split"] == "test"]
        for key in ("rejected_100_26_84_split", "model1_split"):
            self.assertEqual(off_test, [r["case_index"] for r in rows if r[key] == "test"])

    def test_schema_and_scalers(self):
        sch = load("inspection", "schema.json")
        self.assertEqual(len(sch["node_order"]), 46)
        self.assertEqual(len(sch["channel_order"]), 130)
        z = np.load(os.path.join(ART, "preprocessing", "scaler_model1_train_period_v1.npz"))
        self.assertEqual(z["mean"].shape, (46, 130))
        self.assertTrue(np.isfinite(z["mean"]).all() and np.isfinite(z["scale"]).all() and (z["scale"] > 0).all())

    def test_nine_stage_validation_recorded_all_pass(self):
        q = load("quality", "nine_stage_validation.json")
        self.assertEqual(q["summary"]["stages_total"], 9)
        self.assertEqual(q["summary"]["stages_passed"], 9)
        self.assertEqual(q["summary"]["corruptions_detected"], q["summary"]["corruption_tests"])

    def test_augmentation_not_adopted(self):
        a = load("augmentation", "augmentation_assessment.json")
        self.assertEqual(a["decision"], "not_adopted")
        self.assertFalse(a["utility_implemented"])


if __name__ == "__main__":
    unittest.main()
