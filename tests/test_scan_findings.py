import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "shared-workflows"
    / "actions"
    / "scan"
    / "parse_findings.py"
)
SPEC = importlib.util.spec_from_file_location("parse_findings", SCRIPT_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Unable to load parse_findings.py from {SCRIPT_PATH}")
PARSE_FINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PARSE_FINDINGS)

# A clearly fake value: not a real credential, used only to exercise detection logic.
FAKE_SECRET_VALUE = "not-a-real-secret-123"
FAKE_SECRET_HASH = "5b22aa990f5b110b5b4fe9e04d1f17c0506545ee"


def scan_results(*, with_finding=True):
    if not with_finding:
        return {"results": {}}
    return {
        "results": {
            "app.py": [
                {
                    "type": "Secret Keyword",
                    "line_number": 2,
                    "hashed_secret": FAKE_SECRET_HASH,
                }
            ]
        }
    }


def baseline(*, suppresses=True):
    if not suppresses:
        return {"results": {}}
    return {
        "results": {
            "app.py": [
                {
                    "type": "Secret Keyword",
                    "line_number": 2,
                    "hashed_secret": FAKE_SECRET_HASH,
                }
            ]
        }
    }


class ScanFindingsUnitTests(unittest.TestCase):
    def test_no_findings_when_scan_is_clean(self):
        results = PARSE_FINDINGS.load_results_from_dict(scan_results(with_finding=False))
        findings = PARSE_FINDINGS.new_findings(results, known=set())
        self.assertEqual(findings, [])

    def test_finding_reported_when_no_baseline(self):
        results = PARSE_FINDINGS.load_results_from_dict(scan_results())
        findings = PARSE_FINDINGS.new_findings(results, known=set())
        self.assertEqual(
            findings, [{"file": "app.py", "line": 2, "type": "Secret Keyword"}]
        )

    def test_finding_suppressed_when_in_baseline(self):
        results = PARSE_FINDINGS.load_results_from_dict(scan_results())
        known = PARSE_FINDINGS.baseline_hashes_from_dict(baseline())
        findings = PARSE_FINDINGS.new_findings(results, known=known)
        self.assertEqual(findings, [])

    def test_baseline_with_different_hash_does_not_suppress(self):
        results = PARSE_FINDINGS.load_results_from_dict(scan_results())
        known = PARSE_FINDINGS.baseline_hashes_from_dict(baseline(suppresses=False))
        findings = PARSE_FINDINGS.new_findings(results, known=known)
        self.assertEqual(
            findings, [{"file": "app.py", "line": 2, "type": "Secret Keyword"}]
        )

    def test_findings_are_sorted_by_file_then_line(self):
        results = {
            "results": {
                "b.py": [{"type": "Secret Keyword", "line_number": 1, "hashed_secret": "h1"}],
                "a.py": [
                    {"type": "Secret Keyword", "line_number": 5, "hashed_secret": "h2"},
                    {"type": "Secret Keyword", "line_number": 1, "hashed_secret": "h3"},
                ],
            }
        }
        findings = PARSE_FINDINGS.new_findings(
            PARSE_FINDINGS.load_results_from_dict(results), known=set()
        )
        self.assertEqual(
            [(finding["file"], finding["line"]) for finding in findings],
            [("a.py", 1), ("a.py", 5), ("b.py", 1)],
        )

    def test_summary_and_log_never_contain_secret_value_or_hash(self):
        findings = [{"file": "app.py", "line": 2, "type": "Secret Keyword"}]
        with tempfile.TemporaryDirectory() as directory:
            summary_path = Path(directory) / "summary.md"
            summary_path.write_text("", encoding="utf-8")
            PARSE_FINDINGS.write_summary(findings, baseline_used=True, summary_path=summary_path)
            summary_text = summary_path.read_text(encoding="utf-8")

        self.assertIn("app.py", summary_text)
        self.assertIn("2", summary_text)
        self.assertIn("Secret Keyword", summary_text)
        self.assertNotIn(FAKE_SECRET_VALUE, summary_text)
        self.assertNotIn(FAKE_SECRET_HASH, summary_text)

    def test_write_outputs_writes_total_and_baseline_used(self):
        findings = [{"file": "app.py", "line": 2, "type": "Secret Keyword"}]
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "output.txt"
            output_path.write_text("", encoding="utf-8")
            PARSE_FINDINGS.write_outputs(findings, baseline_used=True, output_path=output_path)
            output_text = output_path.read_text(encoding="utf-8")

        self.assertIn("findings_total=1", output_text)
        self.assertIn("baseline_used=true", output_text)


class ScanFindingsEndToEndTests(unittest.TestCase):
    """Runs parse_findings.py as a subprocess, the way the composite action does."""

    def run_script(self, *, scan_data, baseline_data=None):
        import subprocess

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            scan_path = root / "scan-results.json"
            scan_path.write_text(json.dumps(scan_data), encoding="utf-8")
            baseline_path = root / ".secrets.baseline"
            if baseline_data is not None:
                baseline_path.write_text(json.dumps(baseline_data), encoding="utf-8")
            summary_path = root / "summary.md"
            summary_path.write_text("", encoding="utf-8")
            output_path = root / "output.txt"
            output_path.write_text("", encoding="utf-8")

            environment = {
                **os.environ,
                "SCAN_RESULTS_PATH": str(scan_path),
                "BASELINE_PATH": str(baseline_path),
                "GITHUB_STEP_SUMMARY": str(summary_path),
                "GITHUB_OUTPUT": str(output_path),
            }
            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH)],
                env=environment,
                capture_output=True,
                text=True,
            )
            return result, summary_path.read_text(encoding="utf-8"), output_path.read_text(
                encoding="utf-8"
            )

    def test_clean_service_exits_zero_with_no_findings(self):
        result, summary_text, output_text = self.run_script(scan_data=scan_results(with_finding=False))

        self.assertEqual(result.returncode, 0)
        self.assertIn("findings_total=0", output_text)
        self.assertIn("baseline_used=false", output_text)
        self.assertNotIn(FAKE_SECRET_VALUE, summary_text + result.stdout + result.stderr)

    def test_finding_without_baseline_still_exits_zero(self):
        result, summary_text, output_text = self.run_script(scan_data=scan_results())

        self.assertEqual(result.returncode, 0)
        self.assertIn("findings_total=1", output_text)
        self.assertIn("baseline_used=false", output_text)
        self.assertNotIn(FAKE_SECRET_VALUE, summary_text + result.stdout + result.stderr)
        self.assertNotIn(FAKE_SECRET_HASH, summary_text + result.stdout + result.stderr)

    def test_finding_suppressed_by_baseline_exits_zero(self):
        result, summary_text, output_text = self.run_script(
            scan_data=scan_results(), baseline_data=baseline()
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("findings_total=0", output_text)
        self.assertIn("baseline_used=true", output_text)
        self.assertNotIn(FAKE_SECRET_VALUE, summary_text + result.stdout + result.stderr)
        self.assertNotIn(FAKE_SECRET_HASH, summary_text + result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
