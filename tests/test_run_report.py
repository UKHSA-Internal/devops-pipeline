import importlib.util
import json
import tempfile
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

END_TIME = "2026-10-30T12:10:00Z"


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
    }
    return {**values, **overrides}


def deployment_result(name, category, deploy="success", verify="success"):
    return {
        "name": name,
        "category": category,
        "deploy_outcome": deploy,
        "verify_outcome": verify,
        "verified_at": "2026-10-30T12:05:00Z" if verify == "success" else None,
    }


class RunReportTests(unittest.TestCase):
    def test_maps_pr_flow_with_multiple_deployments_per_category(self):
        report = REPORT.create_report(
            report_inputs(),
            END_TIME,
            [
                deployment_result("dev-env-1", "Dev"),
                deployment_result("dev-env-2", "Dev"),
                deployment_result("preprod-env-1", "Pre-production"),
            ],
        )

        self.assertEqual(report["stages"]["deploy"], "PASSED")
        self.assertEqual(
            [(entry["name"], entry["category"]) for entry in report["environments"]],
            [
                ("dev-env-1", "Dev"),
                ("dev-env-2", "Dev"),
                ("preprod-env-1", "Pre-production"),
            ],
        )
        self.assertTrue(
            all(entry["verify_status"] == "PASSED" for entry in report["environments"])
        )
        self.assertEqual(report["environments"][0]["verified_at"], "2026-10-30T12:05:00Z")
        self.assertEqual(report["context"]["trigger_type"], "release")
        self.assertIsNone(report["governance"]["compliance_verdict"])

    def test_maps_main_flow_to_include_production(self):
        report = REPORT.create_report(
            report_inputs(deploy_prod_result="success"),
            END_TIME,
            [
                deployment_result("dev-env-1", "Dev"),
                deployment_result("preprod-env-1", "Pre-production"),
                deployment_result("prod", "Production"),
            ],
        )

        self.assertEqual(report["stages"]["deploy"], "PASSED")
        self.assertEqual(len(report["environments"]), 3)
        self.assertEqual(report["environments"][-1]["name"], "prod")

    def test_failure_and_cancellation_are_failed(self):
        report = REPORT.create_report(
            report_inputs(
                test_result="failure",
                scan_result="skipped",
                build_result="skipped",
                deploy_dev_result="skipped",
                deploy_preprod_result="skipped",
                deploy_prod_result="skipped",
            ),
            END_TIME,
        )

        self.assertEqual(report["stages"]["test"], "FAILED")
        self.assertEqual(report["stages"]["scan"], "SKIPPED")
        self.assertEqual(report["stages"]["deploy"], "SKIPPED")
        self.assertEqual(report["environments"], [])
        self.assertEqual(REPORT.map_result("cancelled"), "FAILED")

    def test_deploy_failure_marks_aggregate_failed_and_verify_skipped(self):
        report = REPORT.create_report(
            report_inputs(
                deploy_dev_result="failure",
                deploy_preprod_result="skipped",
                deploy_prod_result="skipped",
            ),
            END_TIME,
            [deployment_result("dev-env-1", "Dev", deploy="failure", verify="skipped")],
        )

        self.assertEqual(report["stages"]["deploy"], "FAILED")
        self.assertEqual(report["environments"][0]["deploy_status"], "FAILED")
        self.assertEqual(report["environments"][0]["verify_status"], "SKIPPED")
        self.assertIsNone(report["environments"][0]["verified_at"])

    def test_verify_failure_is_reported_for_that_deployment_only(self):
        report = REPORT.create_report(
            report_inputs(deploy_preprod_result="skipped"),
            END_TIME,
            [
                deployment_result("dev-env-1", "Dev"),
                deployment_result("dev-env-2", "Dev", verify="failure"),
            ],
        )

        self.assertEqual(
            [entry["verify_status"] for entry in report["environments"]],
            ["PASSED", "FAILED"],
        )

    def test_loads_results_in_planned_order_and_ignores_missing(self):
        planned = [
            {"name": "dev-env-1"},
            {"name": "dev-env-2"},
            {"name": "preprod-env-1"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            for name in ("preprod-env-1", "dev-env-1"):
                (results_dir / f"{name}.json").write_text(
                    json.dumps(deployment_result(name, "Dev")), encoding="utf-8"
                )

            results = REPORT.load_deployment_results(planned, results_dir)

        self.assertEqual([result["name"] for result in results], ["dev-env-1", "preprod-env-1"])


if __name__ == "__main__":
    unittest.main()
