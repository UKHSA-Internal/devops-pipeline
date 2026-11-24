import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from helpers import ACTIONS, load_script

SUMMARY_PATH = ACTIONS / "test-run" / "record_result.py"
SUMMARY = load_script(SUMMARY_PATH, "record_result")


def suite_xml(count, failed=0):
    cases = "".join(
        f'<testcase classname="pkg.Mod" name="test_{index}"><failure message="boom {index}&#10;more">trace</failure></testcase>'
        for index in range(failed)
    )
    return f'<testsuite tests="{count}" failures="{failed}" errors="0" time="1.5">{cases}</testsuite>'


class JUnitTotalsTests(unittest.TestCase):
    def totals(self, **files):
        with tempfile.TemporaryDirectory() as directory:
            for name, content in files.items():
                (Path(directory) / name).write_text(content, encoding="utf-8")
            return SUMMARY.read_junit(sorted(Path(directory).glob("*.xml")))

    def test_sums_testsuite_and_testsuites_files(self):
        totals, _ = self.totals(
            **{
                "a.xml": '<testsuite tests="5" failures="1" errors="0" time="1.25"/>',
                "b.xml": '<testsuites><testsuite tests="3" failures="0" errors="2" time="0.5"/>'
                '<testsuite tests="2" failures="0" errors="0" time="0.25"/></testsuites>',
            }
        )

        self.assertEqual(totals, {"tests": 10, "failures": 1, "errors": 2, "duration_seconds": 2.0})

    def test_no_xml_gives_none(self):
        self.assertIsNone(self.totals()[0])

    def test_unreadable_xml_is_ignored(self):
        self.assertIsNone(self.totals(**{"broken.xml": "<testsuite"})[0])

    def test_suite_with_an_unparsable_value_adds_nothing(self):
        malformed = '<testsuite tests="5" failures="unknown" errors="0" time="1"/>'

        self.assertIsNone(self.totals(**{"a.xml": malformed})[0])
        totals, _ = self.totals(
            **{"a.xml": malformed, "b.xml": '<testsuite tests="2" failures="0" errors="0" time="0.5"/>'}
        )
        self.assertEqual(totals, {"tests": 2, "failures": 0, "errors": 0, "duration_seconds": 0.5})

    def test_suite_without_a_time_has_no_junit_duration(self):
        totals, _ = self.totals(**{"a.xml": '<testsuite tests="2" failures="0" errors="0"/>'})

        self.assertIsNone(totals["duration_seconds"])

    def test_failed_tests_are_named_with_the_first_line_of_the_message(self):
        _, failed = self.totals(**{"a.xml": suite_xml(3, failed=2)})

        self.assertEqual(failed, [("pkg.Mod.test_0", "boom 0"), ("pkg.Mod.test_1", "boom 1")])


class ResultTests(unittest.TestCase):
    def test_timing_fills_the_duration_when_there_is_no_junit(self):
        result = SUMMARY.build_result("unit", "suite", "success", None, timing=3.2)

        self.assertEqual(result["duration_seconds"], 3.2)
        self.assertIsNone(result["tests"])

    def test_junit_duration_wins_over_timing(self):
        totals = {"tests": 1, "failures": 0, "errors": 0, "duration_seconds": 0.5}

        self.assertEqual(SUMMARY.build_result("unit", "suite", "success", totals, timing=9.0)["duration_seconds"], 0.5)

    def test_junit_without_a_time_uses_timing(self):
        totals = {"tests": 1, "failures": 0, "errors": 0, "duration_seconds": None}

        self.assertEqual(SUMMARY.build_result("unit", "suite", "success", totals, timing=9.0)["duration_seconds"], 9.0)

    def test_summary_line_has_runtime_counts_and_coverage(self):
        result = SUMMARY.build_result(
            "unit",
            "suite",
            "success",
            {"tests": 4, "failures": 1, "errors": 2, "duration_seconds": 0.5},
            coverage=(91.25, None),
        )

        self.assertEqual(
            SUMMARY.summary_text(result, "python from .python-version"),
            "## Test (unit)\n\n**PASSED** · 0.5s · python from .python-version · 4 tests, 1 failures, 2 errors"
            " · Coverage: 91.2%\n\n",
        )

    def test_failed_test_list_stops_at_ten_and_counts_the_rest(self):
        result = SUMMARY.build_result("unit", "suite", "failure", None, timing=1.0)

        text = SUMMARY.summary_text(result, failed=[(f"pkg.test_{index}", "boom") for index in range(13)])
        self.assertIn("- `pkg.test_9`: boom\n", text)
        self.assertNotIn("pkg.test_10", text)
        self.assertIn("- and 3 more\n", text)

        text = SUMMARY.summary_text(result, failed=[(f"pkg.test_{index}", "") for index in range(10)])
        self.assertNotIn("more", text)


COBERTURA = '<coverage line-rate="{line}" branch-rate="{branch}" version="1"><packages/></coverage>'


class CoverageTests(unittest.TestCase):
    def read(self, content):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "coverage.xml"
            path.write_text(content, encoding="utf-8")
            return SUMMARY.read_coverage(path)

    def test_line_and_branch_rates_become_percentages_and_branch_is_optional(self):
        self.assertEqual(self.read(COBERTURA.format(line="0.9123", branch="0.5")), (91.2, 50.0))
        self.assertEqual(self.read('<coverage line-rate="0.8"/>'), (80.0, None))

    def test_malformed_files_give_a_warning_and_none(self):
        for content in ("<coverage", '<coverage line-rate="high"/>', '<coverage line-rate="1.5"/>', "<coverage/>"):
            with self.subTest(content=content):
                self.assertEqual(self.read(content), (None, None))


class StepRunTests(unittest.TestCase):
    """Runs the script as the action does, for a suite or a final step, with the same rules for both."""

    def run_step(self, kind, files, name="unit", before=None, duration_ms="2500", outcome="success"):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            results = root / "service" / "test-results"
            results.mkdir(parents=True)
            environment = {
                **os.environ,
                "SERVICE_DIRECTORY": str(root / "service"),
                "SNAPSHOT_FILE": str(root / "before.json"),
                "SUITE_NAME": name,
                "STEP_KIND": kind,
                "RUN_OUTCOME": outcome,
                "DURATION_MS": duration_ms,
                "RESULT_DIRECTORY": str(root / "results"),
                "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
            }
            for file_name, content in (before or {}).items():
                (results / file_name).write_text(content, encoding="utf-8")
            command = [sys.executable, str(SUMMARY_PATH)]
            subprocess.run([*command, "snapshot"], env=environment, check=True)
            for file_name, content in files.items():
                (results / file_name).write_text(content, encoding="utf-8")
            completed = subprocess.run(command, env=environment, check=True, capture_output=True, text=True)
            result = json.loads((root / "results" / f"{name}.json").read_text(encoding="utf-8"))
            return result, (root / "summary.md").read_text(encoding="utf-8"), completed.stderr

    def test_final_step_named_report_shows_its_coverage(self):
        result, summary, _ = self.run_step("final", {"coverage.xml": COBERTURA.format(line="0.875", branch="0.5")}, name="report")

        self.assertEqual(result["coverage_percent"], 87.5)
        self.assertEqual(result["duration_seconds"], 2.5)
        self.assertIn("## Test (report)", summary)
        self.assertIn("Coverage: 87.5% (branches 50.0%)", summary)

    def test_suite_that_writes_coverage_shows_it_too(self):
        result, summary, _ = self.run_step("suite", {"coverage.xml": COBERTURA.format(line="0.5", branch="0.4"), "unit.xml": suite_xml(3)})

        self.assertEqual(result["coverage_percent"], 50.0)
        self.assertEqual(result["tests"], 3)
        self.assertEqual(result["duration_seconds"], 1.5)
        self.assertIn("Coverage: 50.0%", summary)

    def test_final_step_that_writes_no_files_shows_only_result_and_duration(self):
        result, summary, _ = self.run_step("final", {}, name="gate")

        self.assertIsNone(result["tests"])
        self.assertIsNone(result["coverage_percent"])
        self.assertEqual(summary, "## Test (gate)\n\n**PASSED** · 2.5s\n\n")

    def test_files_that_were_there_before_the_step_are_ignored(self):
        before = {"unit.xml": suite_xml(7, failed=2), "coverage.xml": COBERTURA.format(line="0.9", branch="0.9")}

        result, summary, _ = self.run_step("final", {}, before=before)

        self.assertIsNone(result["tests"])
        self.assertIsNone(result["coverage_percent"])
        self.assertNotIn("Failed tests", summary)

    def test_malformed_coverage_gives_a_warning_and_null_not_a_failure(self):
        result, summary, stderr = self.run_step("suite", {"coverage.xml": "<coverage"})

        self.assertIsNone(result["coverage_percent"])
        self.assertIn("WARNING: Ignoring unreadable coverage file", stderr)
        self.assertNotIn("Coverage", summary)

    def test_failed_tests_are_listed_in_the_summary(self):
        _, summary, _ = self.run_step("suite", {"unit.xml": suite_xml(5, failed=2)}, outcome="failure")

        self.assertIn("Failed tests:", summary)
        self.assertIn("- `pkg.Mod.test_1`: boom 1", summary)

    def test_missing_timing_leaves_the_duration_empty(self):
        result, _, _ = self.run_step("suite", {}, duration_ms="")

        self.assertIsNone(result["duration_seconds"])


class NoStepNamesInPipelineCodeTests(unittest.TestCase):
    def test_pipeline_code_never_refers_to_a_step_by_name(self):
        root = Path(__file__).resolve().parents[1]
        files = [root / ".github" / "workflows" / "standard-pipeline.yml"]
        files += [
            path
            for path in (root / "packages" / "shared-workflows" / "actions").rglob("*")
            if path.is_file() and path.suffix in (".py", ".yml")
        ]
        # A step name would appear as a quoted value or a YAML value; the coverage file and the
        # coverage_percent field are conventions, not step names.
        step_name = re.compile(r"""["'`]coverage["'`]|\bname:\s*coverage\b|:\s*coverage\s*$""")
        for path in files:
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                with self.subTest(file=path.name, line=number):
                    self.assertIsNone(step_name.search(line))


if __name__ == "__main__":
    unittest.main()
