import importlib.util
import json
import os
import re
import subprocess
import sys
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
        "workflow_package_version": "0.7.3",
        "trigger_type": "pull_request",
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
        "image_tag": "sample-app:abcdef123456",
        "verified_at": "2026-10-30T12:05:00Z" if verify == "success" else None,
    }


class RunReportTests(unittest.TestCase):
    def test_maps_pr_flow_with_multiple_deployments_per_category(self):
        report = REPORT.create_report(
            report_inputs(),
            END_TIME,
            [
                deployment_result("dev-env-1", "Development"),
                deployment_result("dev-env-2", "Development"),
                deployment_result("preprod-env-1", "Pre-production"),
            ],
        )

        self.assertEqual(report["steps"]["deploy"], "PASSED")
        self.assertEqual(
            [(entry["name"], entry["category"]) for entry in report["environments"]],
            [
                ("dev-env-1", "Development"),
                ("dev-env-2", "Development"),
                ("preprod-env-1", "Pre-production"),
            ],
        )
        self.assertTrue(
            all(entry["verify_status"] == "PASSED" for entry in report["environments"])
        )
        self.assertEqual(report["environments"][0]["verified_at"], "2026-10-30T12:05:00Z")
        self.assertEqual(report["context"]["trigger_type"], "pull_request")
        self.assertIsNone(report["governance"]["compliance_verdict"])

    def test_maps_main_flow_to_include_production(self):
        report = REPORT.create_report(
            report_inputs(deploy_prod_result="success", trigger_type="push"),
            END_TIME,
            [
                deployment_result("dev-env-1", "Development"),
                deployment_result("preprod-env-1", "Pre-production"),
                deployment_result("prod", "Production"),
            ],
        )

        self.assertEqual(report["steps"]["deploy"], "PASSED")
        self.assertEqual(len(report["environments"]), 3)
        self.assertEqual(report["environments"][-1]["name"], "prod")
        self.assertEqual(report["context"]["trigger_type"], "push")

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

        self.assertEqual(report["steps"]["test"], "FAILED")
        self.assertEqual(report["steps"]["scan"], "SKIPPED")
        self.assertEqual(report["steps"]["deploy"], "SKIPPED")
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
            [deployment_result("dev-env-1", "Development", deploy="failure", verify="skipped")],
        )

        self.assertEqual(report["steps"]["deploy"], "FAILED")
        self.assertEqual(report["environments"][0]["deploy_status"], "FAILED")
        self.assertEqual(report["environments"][0]["verify_status"], "SKIPPED")
        self.assertIsNone(report["environments"][0]["verified_at"])

    def test_verify_failure_is_reported_for_that_deployment_only(self):
        report = REPORT.create_report(
            report_inputs(deploy_preprod_result="skipped"),
            END_TIME,
            [
                deployment_result("dev-env-1", "Development"),
                deployment_result("dev-env-2", "Development", verify="failure"),
            ],
        )

        self.assertEqual(
            [entry["verify_status"] for entry in report["environments"]],
            ["PASSED", "FAILED"],
        )

    def test_loads_results_in_planned_order_and_ignores_missing(self):
        planned = [
            {"name": "dev-env-1", "category": "Development"},
            {"name": "dev-env-2", "category": "Development"},
            {"name": "preprod-env-1", "category": "Pre-production"},
            {"name": "prod", "category": "Production"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            for name, category in (
                ("preprod-env-1", "Pre-production"),
                ("dev-env-1", "Development"),
                ("dev-env-2", "Development"),
            ):
                (results_dir / f"{name}.json").write_text(
                    json.dumps(deployment_result(name, category)), encoding="utf-8"
                )

            results = REPORT.load_deployment_results(
                planned, results_dir, {"Development", "Pre-production"}, results_dir / "started"
            )

        self.assertEqual(
            [result["name"] for result in results],
            ["dev-env-1", "dev-env-2", "preprod-env-1"],
        )
        self.assertNotIn("prod", [result["name"] for result in results])

    def test_missing_result_for_ran_deployment_is_recorded_as_failure(self):
        planned = [{"name": "dev-env-1", "category": "Development"}]
        with tempfile.TemporaryDirectory() as directory:
            started_dir = Path(directory) / "started"
            started_dir.mkdir()
            (started_dir / "dev-env-1").touch()
            results = REPORT.load_deployment_results(
                planned, Path(directory), {"Development"}, started_dir
            )

        report = REPORT.create_report(report_inputs(), END_TIME, results)

        self.assertEqual(report["steps"]["deploy"], "FAILED")
        self.assertEqual(report["environments"][0]["deploy_status"], "FAILED")
        self.assertEqual(report["environments"][0]["verify_status"], "SKIPPED")
        self.assertIn("Missing deployment result file", report["environments"][0]["error"])

    def test_unattempted_deployment_cancelled_by_fail_fast_is_not_a_failure(self):
        planned = [
            {"name": "dev-env-1", "category": "Development"},
            {"name": "dev-env-2", "category": "Development"},
        ]
        with tempfile.TemporaryDirectory() as directory:
            results_dir = Path(directory)
            started_dir = results_dir / "started"
            started_dir.mkdir()
            (started_dir / "dev-env-1").touch()
            failed = deployment_result("dev-env-1", "Development")
            failed["deploy_outcome"] = "failure"
            failed["verify_outcome"] = "skipped"
            (results_dir / "dev-env-1.json").write_text(json.dumps(failed), encoding="utf-8")

            results = REPORT.load_deployment_results(
                planned, results_dir, {"Development"}, started_dir
            )

        self.assertEqual([result["name"] for result in results], ["dev-env-1"])
        report = REPORT.create_report(
            report_inputs(deploy_dev_result="failure"), END_TIME, results
        )
        self.assertEqual(report["steps"]["deploy"], "FAILED")
        self.assertEqual([env["name"] for env in report["environments"]], ["dev-env-1"])
        self.assertNotIn("error", report["environments"][0])

    def test_same_image_tag_is_reported_for_every_environment(self):
        report = REPORT.create_report(
            report_inputs(deploy_prod_result="success", trigger_type="push"),
            END_TIME,
            [
                deployment_result("dev-env-1", "Development"),
                deployment_result("preprod-env-1", "Pre-production"),
                deployment_result("prod", "Production"),
            ],
        )

        self.assertEqual(
            {entry["image_tag"] for entry in report["environments"]},
            {"sample-app:abcdef123456"},
        )


class TestSuitesTests(unittest.TestCase):
    def recorded(self, name, result="PASSED", tests=10, failures=0, duration=1.5):
        return {
            "name": name,
            "kind": "suite",
            "result": result,
            "tests": tests,
            "failures": failures,
            "errors": 0,
            "duration_seconds": duration,
        }

    def test_lists_suites_then_the_final_step_in_plan_order(self):
        with tempfile.TemporaryDirectory() as directory:
            results = Path(directory)
            for recorded in (
                self.recorded("unit", tests=7, duration=2.5),
                self.recorded("api", result="FAILED", failures=2),
                {**self.recorded("coverage"), "kind": "final", "tests": None, "failures": None, "duration_seconds": None},
            ):
                (results / f"{recorded['name']}.json").write_text(json.dumps(recorded), encoding="utf-8")

            suites = REPORT.load_test_suites(["unit", "api", "coverage"], results, "failure")

        self.assertEqual([suite["name"] for suite in suites], ["unit", "api", "coverage"])
        self.assertEqual(
            suites[0], {"name": "unit", "result": "PASSED", "tests": 7, "failures": 0, "duration_seconds": 2.5}
        )
        self.assertEqual((suites[1]["result"], suites[1]["failures"]), ("FAILED", 2))
        self.assertEqual(
            suites[2], {"name": "coverage", "result": "PASSED", "tests": None, "failures": None, "duration_seconds": None}
        )
        self.assertNotIn("errors", suites[1])

    def test_planned_step_without_a_result_file_is_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            suites = REPORT.load_test_suites(["unit", "coverage"], Path(directory), "failure")

        self.assertEqual([suite["result"] for suite in suites], ["SKIPPED", "SKIPPED"])
        self.assertIsNone(suites[0]["tests"])

    def test_nothing_is_listed_when_the_test_stage_was_skipped(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(REPORT.load_test_suites(["unit"], Path(directory), "skipped"), [])

    def test_report_without_test_suites_has_an_empty_list(self):
        self.assertEqual(REPORT.create_report(report_inputs(), END_TIME)["test_suites"], [])


class RunRecordFileTests(unittest.TestCase):
    TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

    def generate(self, test_results=None, test_suites=(), test_final_name="", **overrides):
        values = report_inputs(**overrides)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            version_file = root / "VERSION"
            version_file.write_text(values["workflow_package_version"] + "\n", encoding="utf-8")
            results = root / "results"
            results.mkdir()
            (results / "dev-env-1.json").write_text(
                json.dumps(deployment_result("dev-env-1", "Development")), encoding="utf-8"
            )
            suite_results = root / "test-suites"
            suite_results.mkdir()
            for name, result in (test_results or {}).items():
                (suite_results / f"{name}.json").write_text(json.dumps(result), encoding="utf-8")
            environment = {
                **os.environ,
                **{key.upper(): value for key, value in values.items()},
                "DEPLOYMENTS": json.dumps([{"name": "dev-env-1", "category": "Development"}]),
                "RESULTS_DIR": str(results),
                "STARTED_DIR": str(root / "started"),
                "TEST_RESULTS_DIR": str(suite_results),
                "TEST_SUITES": json.dumps([{"name": name, "command": "true"} for name in test_suites]),
                "TEST_FINAL_NAME": test_final_name,
                "REPORT_PATH": str(root / "run-record.json"),
                "GITHUB_STEP_SUMMARY": str(root / "summary.md"),
                "VERSION_FILE": str(version_file),
            }
            subprocess.run(
                [sys.executable, str(REPORT_PATH)],
                env=environment,
                check=True,
                capture_output=True,
            )
            return json.loads((root / "run-record.json").read_text(encoding="utf-8"))

    def test_run_record_has_expected_structure(self):
        record = self.generate(deploy_preprod_result="skipped")

        self.assertEqual(
            set(record), {"context", "timestamps", "steps", "test_suites", "environments", "governance"}
        )
        self.assertEqual(
            set(record["context"]),
            {
                "pipeline_run_id",
                "repository",
                "change_id",
                "ref",
                "workflow_ref",
                "workflow_sha",
                "workflow_package_version",
                "trigger_type",
            },
        )
        self.assertEqual(set(record["steps"]), {"check", "test", "scan", "build", "deploy"})
        self.assertTrue(set(record["steps"].values()) <= {"PASSED", "FAILED", "SKIPPED"})
        for value in record["timestamps"].values():
            self.assertRegex(value, self.TIMESTAMP)
        self.assertEqual(record["environments"][0]["image_tag"], "sample-app:abcdef123456")
        self.assertEqual(record["context"]["workflow_package_version"], "0.7.3")

    def test_run_record_file_includes_test_suites_and_keeps_the_stage_result(self):
        recorded = {"name": "unit", "kind": "suite", "result": "PASSED", "tests": 3, "failures": 0, "errors": 0, "duration_seconds": 0.5}
        record = self.generate(test_results={"unit": recorded}, test_suites=["unit"], test_final_name="coverage")

        self.assertEqual(record["steps"]["test"], "PASSED")
        self.assertEqual(
            record["test_suites"],
            [
                {"name": "unit", "result": "PASSED", "tests": 3, "failures": 0, "duration_seconds": 0.5},
                {"name": "coverage", "result": "SKIPPED", "tests": None, "failures": None, "duration_seconds": None},
            ],
        )

    def test_invalid_or_missing_version_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            version_file = Path(directory) / "VERSION"
            environment = {
                **os.environ,
                **{key.upper(): value for key, value in report_inputs().items()},
                "VERSION_FILE": str(version_file),
            }
            missing = subprocess.run(
                [sys.executable, str(REPORT_PATH)], env=environment, capture_output=True, text=True
            )
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("FileNotFoundError", missing.stderr)

            version_file.write_text("0.7.3-canary\n", encoding="utf-8")
            invalid = subprocess.run(
                [sys.executable, str(REPORT_PATH)], env=environment, capture_output=True, text=True
            )
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("Invalid workflow package version", invalid.stderr)

    def test_failed_check_records_check_failed_and_downstream_skipped(self):
        record = self.generate(
            check_result="failure",
            test_result="skipped",
            scan_result="skipped",
            build_result="skipped",
            deploy_dev_result="skipped",
            deploy_preprod_result="skipped",
        )

        self.assertEqual(
            record["steps"],
            {
                "check": "FAILED",
                "test": "SKIPPED",
                "scan": "SKIPPED",
                "build": "SKIPPED",
                "deploy": "SKIPPED",
            },
        )
        self.assertEqual(record["environments"], [])


if __name__ == "__main__":
    unittest.main()
