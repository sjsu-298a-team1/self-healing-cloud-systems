import unittest

import _paths  # noqa: F401
import reconcile_labels as r


def case(ts, i=0):
    return {"timestamp": ts, "level": "pod", "cmdb_id": f"svc-{i}", "failure_type": "T"}


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        # 10 cases at 1000..1900; AD list drops case 1800, adds 1720 (AD-only) and 1050 pre-split
        self.cases = [case(1000 + 100 * i, i) for i in range(10)]
        self.ad = [1000 + 100 * i for i in range(10) if 1000 + 100 * i != 1800] + [1720]
        self.rows, self.s = r.reconcile(self.cases, self.ad, split_ts=1450)

    def test_exact_matching_only(self):
        self.assertEqual((self.s["exact_shared"], self.s["ad_only"], self.s["case_only"]), (9, 1, 1))
        cats = {row["timestamp_epoch"]: row["category"] for row in self.rows}
        self.assertEqual(cats[1720], "ad_only")
        self.assertEqual(cats[1800], "case_only")

    def test_nearest_other_source_is_signed_other_minus_this(self):
        by = {row["timestamp_epoch"]: row for row in self.rows}
        self.assertEqual(by[1720]["nearest_other_source_delta_s"], -20)   # nearest case is 1700
        self.assertEqual(by[1800]["nearest_other_source_delta_s"], -80)   # nearest AD event is 1720

    def test_populations_and_split_side(self):
        p = self.s["evaluation_populations_post_split"]
        self.assertEqual(p, {"official_ad_labels": 5, "injection_cases": 5, "intersection": 4, "union": 6})
        by = {row["timestamp_epoch"]: row for row in self.rows}
        self.assertEqual(by[1000]["ft_rcl_side"], "train")   # index 0 < int(0.6*10)
        self.assertEqual(by[1600]["ft_rcl_side"], "test")    # index 6
        self.assertEqual(by[1720]["ft_rcl_side"], "")

    def test_pre_split_identity_flag(self):
        self.assertTrue(self.s["pre_split_ad_events_equal_cases_csv_first_n"])
        bad, s = r.reconcile(self.cases, [x + 1 if x == 1100 else x for x in self.ad], 1450)
        self.assertFalse(s["pre_split_ad_events_equal_cases_csv_first_n"])


if __name__ == "__main__":
    unittest.main()
