import importlib.util
import unittest
from pathlib import Path

REPORT_PATH = (
    Path(__file__).resolve().parents[1]
    / "packages"
    / "shared-workflows"
    / "actions"
    / "publish-run-report"
    / "generate_run_report.py"
)
REPORT_SPEC = importlib.util.spec_from_file_location("generate_run_report", REPORT_PATH)
if REPORT_SPEC is None or REPORT_SPEC.loader is None:
    raise ImportError(f"Unable to load run report generator from {REPORT_PATH}")
REPORT = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(REPORT)


def report_inputs(**overrides):
    values = {
        "run_id": "123",
        "repository": "UKHSA/sample-app",
        "commit_sha": "abcdef123456",
        "ref": "refs/heads/feature/example",
        "workflow_ref": "UKHSA/devops-pipeline/.github/workflows/sample-app-pipeline.yml@refs/heads/main",
        "workflow_sha": "fedcba654321",
        "start_time": "2026-10-30T12:00:00Z",
        "check_result": "success",
        "test_result": "success",
        "scan_result": "success",
        "build_result": "success",
        "deploy_dev_result": "success",
        "deploy_preprod_result": "success",
        "deploy_prod_result": "skipped",
        "verify_result": "success",
    }
    return {**values, **overrides}


class RunReportTests(unittest.TestCase):
    def test_maps_pr_flow_and_omits_skipped_production(self):
        report = REPORT.create_report(report_inputs(), "2026-10-30T12:10:00Z")

        self.assertEqual(report["stages"]["deploy"], "PASSED")
        self.assertEqual(
            [entry["category"] for entry in report["environments"]],
            ["Dev", "Pre-production"],
        )
        self.assertTrue(
            all(entry["verify_status"] == "PASSED" for entry in report["environments"])
        )
        self.assertEqual(report["context"]["trigger_type"], "release")
        self.assertIsNone(report["governance"]["compliance_verdict"])

    def test_maps_main_flow_to_include_production(self):
        report = REPORT.create_report(
            report_inputs(deploy_prod_result="success"),
            "2026-10-30T12:10:00Z",
        )

        self.assertEqual(report["stages"]["deploy"], "PASSED")
        self.assertEqual(len(report["environments"]), 3)
        self.assertEqual(report["environments"][-1]["category"], "Production")

    def test_failure_and_cancellation_are_failed(self):
        report = REPORT.create_report(
            report_inputs(
                test_result="failure",
                scan_result="skipped",
                build_result="skipped",
                deploy_dev_result="skipped",
                deploy_preprod_result="skipped",
                deploy_prod_result="skipped",
                verify_result="skipped",
            ),
            "2026-10-30T12:10:00Z",
        )

        self.assertEqual(report["stages"]["test"], "FAILED")
        self.assertEqual(report["stages"]["scan"], "SKIPPED")
        self.assertEqual(report["stages"]["deploy"], "SKIPPED")
        self.assertEqual(REPORT.map_result("cancelled"), "FAILED")

    def test_deploy_failure_marks_aggregate_failed(self):
        report = REPORT.create_report(
            report_inputs(
                deploy_dev_result="failure",
                deploy_preprod_result="skipped",
                deploy_prod_result="skipped",
                verify_result="skipped",
            ),
            "2026-10-30T12:10:00Z",
        )

        self.assertEqual(report["stages"]["deploy"], "FAILED")
        self.assertEqual(report["environments"][0]["deploy_status"], "FAILED")


if __name__ == "__main__":
    unittest.main()
