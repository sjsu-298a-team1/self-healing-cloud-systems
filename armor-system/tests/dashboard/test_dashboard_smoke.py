"""Headless smoke tests: every page renders without an exception (Streamlit AppTest)."""
import os
import unittest

try:
    from streamlit.testing.v1 import AppTest
except Exception:  # pragma: no cover
    AppTest = None

APP = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "app.py"))
PAGES = ["1 - Project Overview", "2 - Dataset Explorer", "3 - Data Splitting", "4 - EDA", "5 - Preprocessing", "6 - Data Quality", "7 - Deliverables and Evidence"]
ART = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data", "artifacts", "d1"))


@unittest.skipIf(AppTest is None, "streamlit not installed")
class DashboardSmoke(unittest.TestCase):
    def run_page(self, page):
        at = AppTest.from_file(APP, default_timeout=90).run()
        at.sidebar.radio[0].set_value(page).run()
        return at

    def test_each_page_renders_without_exception(self):
        for page in PAGES:
            with self.subTest(page=page):
                at = self.run_page(page)
                self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
                self.assertEqual(len(at.error), 0, [e.value for e in at.error])
                self.assertGreater(len(at.markdown) + len(at.metric) + len(at.dataframe), 0)

    @unittest.skipUnless(os.path.exists(os.path.join(ART, "inspection", "inspection_summary.json")), "artifacts not generated")
    def test_overview_shows_real_counts(self):
        at = self.run_page(PAGES[0])
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("7,200", text)
        self.assertIn("210", text)
        self.assertNotIn("Artifact not available", " ".join(w.value for w in at.warning))

    @unittest.skipUnless(os.path.exists(os.path.join(ART, "splits", "official_armor_v1.json")), "artifacts not generated")
    def test_splitting_page_reports_failed_proposal(self):
        at = self.run_page(PAGES[2])
        text = " ".join(m.value for m in at.markdown)
        self.assertIn("FAILS its hard checks", text)

    def test_missing_artifacts_are_reported_not_invented(self):
        script = f"import sys\nsys.path.insert(0, {os.path.dirname(APP)!r})\nimport ui\nui.missing('something.json')\n"
        at = AppTest.from_string(script, default_timeout=30).run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("Artifact not available", at.warning[0].value)
        self.assertIn("something.json", at.warning[0].value)


if __name__ == "__main__":
    unittest.main()
