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

    def test_proposed_split_is_honestly_marked_failing(self):
        m = load("splits", "model1_candidate_100_26_84_v1.json")
        self.assertFalse(m["usable"])
        self.assertEqual(m["verdict"], "FAIL")
        failed = {c["id"].split("_")[0] for c in m["checks"] if c["status"] == "FAIL"}
        self.assertTrue({"S4", "S5", "S6"} <= failed)

    def test_alternative_is_usable_but_pending_approval_and_keeps_official_test(self):
        m = load("splits", "model1_alternative_v1.json")
        self.assertTrue(m["usable"])
        self.assertEqual(m["status"], "proposed_pending_approval")
        self.assertEqual(m["case_ranges"]["test"]["n_cases"], 84)
        off = load("splits", "official_armor_v1.json")
        self.assertEqual(m["case_ranges"]["test"]["first_case_ts"], off["case_ranges"]["test"]["first_case_ts"])

    def test_manifest_hashes_are_self_consistent(self):
        for n in ("official_armor_v1", "model1_candidate_100_26_84_v1", "model1_alternative_v1"):
            m = load("splits", f"{n}.json")
            self.assertEqual(m["content_sha256"], sp.content_hash(m))

    def test_no_case_is_in_two_splits_and_all_are_assigned(self):
        import csv
        with open(os.path.join(ART, "splits", "case_split_assignments.csv")) as fh:
            rows = list(csv.DictReader(fh))
        self.assertEqual(len(rows), 210)
        for key in ("official_split", "candidate_split", "alternative_split"):
            self.assertTrue(all(r[key] in ("train", "validation", "test") for r in rows))
        off_test = [r["case_index"] for r in rows if r["official_split"] == "test"]
        for key in ("candidate_split", "alternative_split"):
            self.assertEqual(off_test, [r["case_index"] for r in rows if r[key] == "test"])

    def test_schema_and_scalers(self):
        sch = load("inspection", "schema.json")
        self.assertEqual(len(sch["node_order"]), 46)
        self.assertEqual(len(sch["channel_order"]), 130)
        z = np.load(os.path.join(ART, "preprocessing", "scaler_official_train_period_v1.npz"))
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
