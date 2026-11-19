import importlib.util
import tempfile
import unittest
from pathlib import Path

SUMMARY_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "shared-workflows"
    / "actions"
    / "test-run"
    / "junit_summary.py"
)
SPEC = importlib.util.spec_from_file_location("junit_summary", SUMMARY_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Unable to load JUnit summary from {SUMMARY_PATH}")
SUMMARY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SUMMARY)


class JUnitTotalsTests(unittest.TestCase):
    def totals(self, **files):
        with tempfile.TemporaryDirectory() as directory:
            for name, content in files.items():
                (Path(directory) / name).write_text(content, encoding="utf-8")
            return SUMMARY.junit_totals(Path(directory))

    def test_sums_testsuite_and_testsuites_files(self):
        totals = self.totals(
            **{
                "a.xml": '<testsuite tests="5" failures="1" errors="0" time="1.25"/>',
                "b.xml": '<testsuites><testsuite tests="3" failures="0" errors="2" time="0.5"/>'
                '<testsuite tests="2" failures="0" errors="0" time="0.25"/></testsuites>',
            }
        )

        self.assertEqual(totals, {"tests": 10, "failures": 1, "errors": 2, "duration_seconds": 2.0})

    def test_no_xml_gives_none(self):
        self.assertIsNone(self.totals())

    def test_unreadable_xml_is_ignored(self):
        self.assertIsNone(self.totals(**{"broken.xml": "<testsuite"}))

    def test_without_xml_only_the_result_is_reported(self):
        result = SUMMARY.build_result("unit", "suite", "failure", None)

        self.assertEqual(result["result"], "FAILED")
        self.assertIsNone(result["tests"])
        self.assertEqual(SUMMARY.summary_text(result), "### Test (unit)\n\n- Result: **FAILED**\n\n")

    def test_summary_table_has_the_counts(self):
        text = SUMMARY.summary_text(
            SUMMARY.build_result(
                "unit", "suite", "success", {"tests": 4, "failures": 1, "errors": 2, "duration_seconds": 0.5}
            )
        )

        self.assertIn("| **PASSED** | 4 | 1 | 2 | 0.5 |", text)


if __name__ == "__main__":
    unittest.main()
