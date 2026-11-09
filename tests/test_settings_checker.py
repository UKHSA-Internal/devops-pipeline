import contextlib
import copy
import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT / "packages" / "settings-checker"))

import checker as CHECKER  # noqa: E402
import rules as RULES  # noqa: E402

FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "settings"
ERROR_FIXTURES = FIXTURES / "errors"

# Error fixture -> the only rule it may report.
EXPECTED_FIXTURE_RULES = {
    "custom-check-missing-allow-failure.yml": "CHK-08",
    "environment-missing-role-name.yml": "CHK-03",
    "missing-test-command.yml": "CHK-11",
    "no-approvers.yml": "CHK-05",
    "no-production-environment.yml": "CHK-04",
    "unattended-without-exception-id.yml": "CHK-10",
    "unsupported-approval-mode.yml": "CHK-09",
}


def environment(name, category):
    return {
        "name": name,
        "category": category,
        "account_id": "123456789012",
        "role_name": "pipeline-role",
        "region": "eu-west-2",
    }


COMPLIANT = {
    "version": "1.0",
    "service": {
        "name": "sample-app",
        "owner_team": "platform-team",
        "language": "python",
        "test_command": "python3 -m unittest discover",
    },
    "environments": [
        environment("dev-env-1", "Development"),
        environment("preprod-env-1", "Pre-production"),
        environment("prod", "Production"),
    ],
    "governance": {"retention_days": 30, "approvers": ["platform-leads"]},
    "verification": {
        "health_endpoint": "/health",
        "timeout_seconds": 60,
        "db_check_required": False,
        "custom_checks": [{"name": "smoke", "command": "true", "timeout_seconds": 30, "allow_failure": False}],
    },
    "deploy": {"production": {"approval_mode": "all-approvers"}},
}


def settings(change):
    """Return a copy of the compliant settings with change(settings) applied."""
    values = copy.deepcopy(COMPLIANT)
    change(values)
    return values


def rules(values):
    return {item["rule"] for item in RULES.check(values)}


def set_path(path, value):
    def change(values):
        *parents, last = path
        target = values
        for part in parents:
            target = target[part]
        target[last] = value

    return change


def delete_path(path):
    def change(values):
        *parents, last = path
        target = values
        for part in parents:
            target = target[part]
        del target[last]

    return change


# rule -> (label -> change). Every change must violate that rule and no other.
FAILING_CASES = {
    "CHK-01": {
        "missing version": delete_path(["version"]),
        "numeric version": set_path(["version"], 1.0),
    },
    "CHK-02": {
        "missing name": delete_path(["service", "name"]),
        "blank owner_team": set_path(["service", "owner_team"], "  "),
        "missing language": delete_path(["service", "language"]),
    },
    "CHK-03": {
        "environment not a mapping": lambda v: v["environments"].append("dev"),
        "missing role_name": delete_path(["environments", 0, "role_name"]),
        "blank region": set_path(["environments", 0, "region"], ""),
        "unknown category": lambda v: v["environments"].append(environment("staging", "Staging")),
        "short category name": lambda v: v["environments"].append(environment("dev-2", "Dev")),
        "unsafe name": set_path(["environments", 0, "name"], "../dev"),
        "duplicate name": lambda v: v["environments"].append(environment("prod", "Production")),
    },
    "CHK-04": {
        "no Production": lambda v: v["environments"].pop(),
        "no environments": set_path(["environments"], []),
    },
    "CHK-05": {
        "missing governance.approvers": delete_path(["governance", "approvers"]),
        "empty approvers": set_path(["governance", "approvers"], []),
        "approvers not a list": set_path(["governance", "approvers"], "platform-leads"),
        "blank approver": set_path(["governance", "approvers"], [""]),
    },
    "CHK-06": {
        "missing retention_days": delete_path(["governance", "retention_days"]),
        "zero retention_days": set_path(["governance", "retention_days"], 0),
        "text retention_days": set_path(["governance", "retention_days"], "30"),
        "boolean retention_days": set_path(["governance", "retention_days"], True),
    },
    "CHK-07": {
        "relative health_endpoint": set_path(["verification", "health_endpoint"], "health"),
        "health_endpoint with space": set_path(["verification", "health_endpoint"], "/he alth"),
        "missing db_check_required": delete_path(["verification", "db_check_required"]),
        "text db_check_required": set_path(["verification", "db_check_required"], "false"),
        "zero timeout_seconds": set_path(["verification", "timeout_seconds"], 0),
        "verification not a mapping": set_path(["verification"], "none"),
    },
    "CHK-08": {
        "custom_checks not a list": set_path(["verification", "custom_checks"], "smoke"),
        "blank name": set_path(["verification", "custom_checks", 0, "name"], ""),
        "missing command": delete_path(["verification", "custom_checks", 0, "command"]),
        "missing allow_failure": delete_path(["verification", "custom_checks", 0, "allow_failure"]),
        "text allow_failure": set_path(["verification", "custom_checks", 0, "allow_failure"], "no"),
        "text timeout_seconds": set_path(["verification", "custom_checks", 0, "timeout_seconds"], "30"),
    },
    "CHK-09": {
        "missing deploy": delete_path(["deploy"]),
        "missing production": set_path(["deploy"], {}),
        "missing approval_mode": set_path(["deploy", "production"], {}),
        "old standard value": set_path(["deploy", "production", "approval_mode"], "standard"),
        "old fast-track value": set_path(["deploy", "production", "approval_mode"], "fast-track"),
    },
    "CHK-10": {
        "unattended without exception_id": set_path(["deploy", "production"], {"approval_mode": "unattended"}),
        "unattended with blank exception_id": set_path(
            ["deploy", "production"], {"approval_mode": "unattended", "exception_id": " "}
        ),
    },
    "CHK-11": {
        "missing test_command": delete_path(["service", "test_command"]),
        "blank test_command": set_path(["service", "test_command"], "  "),
        "multiline test_command": set_path(["service", "test_command"], "a\nb"),
        "numeric test_command": set_path(["service", "test_command"], 1),
    },
}

PASSING_CASES = {
    "CHK-01": {"string version": set_path(["version"], "2")},
    "CHK-02": {"other language": set_path(["service", "language"], "java")},
    "CHK-03": {
        "unquoted account_id": set_path(["environments", 0, "account_id"], 123456789012),
        "several deployments per category": lambda v: v["environments"].append(environment("dev-2", "Development")),
    },
    "CHK-04": {"categories in any order": lambda v: v["environments"].reverse()},
    "CHK-05": {"several approvers": set_path(["governance", "approvers"], ["leads", "security"])},
    "CHK-06": {"one day": set_path(["governance", "retention_days"], 1)},
    "CHK-07": {
        "nested health_endpoint": set_path(["verification", "health_endpoint"], "/api/v1/health"),
        "defaults omitted": lambda v: [v["verification"].pop(key) for key in ("health_endpoint", "timeout_seconds")],
        "db check required": set_path(["verification", "db_check_required"], True),
    },
    "CHK-08": {
        "custom_checks omitted": delete_path(["verification", "custom_checks"]),
        "timeout omitted": delete_path(["verification", "custom_checks", 0, "timeout_seconds"]),
        "allow_failure true": set_path(["verification", "custom_checks", 0, "allow_failure"], True),
    },
    "CHK-09": {
        "single-approver": set_path(["deploy", "production", "approval_mode"], "single-approver"),
        "unattended": set_path(["deploy", "production"], {"approval_mode": "unattended", "exception_id": "EXC-1"}),
    },
    "CHK-10": {
        "exception_id not needed": set_path(["deploy", "production"], {"approval_mode": "all-approvers"}),
    },
    "CHK-11": {"command with arguments": set_path(["service", "test_command"], "make test ARGS='-v'")},
}


def run_cli(*args):
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(io.StringIO()):
        status = CHECKER.main(list(args))
    return status, stdout.getvalue()


def run_json(*args):
    status, output = run_cli(*args, "--format", "json")
    return status, json.loads(output)


def rule_ids():
    return {rule.id for rule in RULES.RULES}


class RuleTests(unittest.TestCase):
    def test_rule_ids_are_unique_and_complete(self):
        ids = [rule.id for rule in RULES.RULES]
        self.assertEqual(sorted(ids), [f"CHK-{number:02d}" for number in range(1, 12)])

    def test_severities_match_contract(self):
        errors = {"CHK-03", "CHK-04", "CHK-05", "CHK-08", "CHK-09", "CHK-10", "CHK-11"}
        for rule in RULES.RULES:
            with self.subTest(rule.id):
                self.assertEqual(rule.severity, RULES.ERROR if rule.id in errors else RULES.WARNING)

    def test_compliant_settings_have_no_problems(self):
        self.assertEqual(RULES.check(copy.deepcopy(COMPLIANT)), [])

    def test_failing_cases_report_only_their_rule(self):
        for rule, cases in FAILING_CASES.items():
            for label, change in cases.items():
                with self.subTest(rule=rule, case=label):
                    self.assertEqual(rules(settings(change)), {rule})

    def test_passing_cases_have_no_problems(self):
        for rule, cases in PASSING_CASES.items():
            for label, change in cases.items():
                with self.subTest(rule=rule, case=label):
                    self.assertEqual(rules(settings(change)), set())

    def test_every_rule_has_passing_and_failing_cases(self):
        self.assertEqual(set(FAILING_CASES), rule_ids())
        self.assertEqual(set(PASSING_CASES), rule_ids())

    def test_missing_service_reports_both_service_rules(self):
        self.assertEqual(rules(settings(delete_path(["service"]))), {"CHK-02", "CHK-11"})

    def test_missing_or_malformed_environments_report_fields_and_categories(self):
        for change in (delete_path(["environments"]), set_path(["environments"], "dev")):
            with self.subTest(change=change):
                self.assertEqual(rules(settings(change)), {"CHK-03", "CHK-04"})

    def test_problem_reports_field_severity_message_and_rule(self):
        problems = RULES.check(settings(delete_path(["environments", 1, "role_name"])))

        self.assertEqual(
            problems,
            [
                {
                    "field": "environments[1].role_name",
                    "severity": "Error",
                    "message": "is required",
                    "rule": "CHK-03",
                }
            ],
        )


class ExitCodeTests(unittest.TestCase):
    WARNING = [{"severity": "Warning"}]
    ERROR = [{"severity": "Error"}, {"severity": "Warning"}]

    def test_exit_codes(self):
        # problems, strict, report_only, expected
        cases = [
            ([], False, False, 0),
            ([], True, False, 0),
            (self.WARNING, False, False, 0),
            (self.WARNING, True, False, 1),
            (self.ERROR, False, False, 1),
            (self.ERROR, True, False, 1),
            (self.ERROR, False, True, 0),
        ]
        for problems, strict, report_only, expected in cases:
            with self.subTest(severities=[item["severity"] for item in problems], strict=strict, report_only=report_only):
                self.assertEqual(CHECKER.exit_code(problems, strict, report_only), expected)


class CliTests(unittest.TestCase):
    MODES = ((), ("--strict",), ("--report-only",))

    def expected_exit(self, fixture, mode):
        if "--report-only" in mode or fixture.name == "compliant.yml":
            return 0
        if fixture.name == "warnings-only.yml":
            return 1 if "--strict" in mode else 0
        return 1

    def test_fixtures_are_the_expected_set(self):
        self.assertEqual(
            {path.name for path in FIXTURES.glob("*.yml")}, {"compliant.yml", "warnings-only.yml", "unparseable.yml"}
        )
        self.assertEqual({path.name for path in ERROR_FIXTURES.glob("*.yml")}, set(EXPECTED_FIXTURE_RULES))

    def test_every_fixture_in_every_mode(self):
        for fixture in sorted([*FIXTURES.glob("*.yml"), *ERROR_FIXTURES.glob("*.yml")]):
            for mode in self.MODES:
                with self.subTest(fixture=fixture.name, mode=" ".join(mode) or "default"):
                    status, report = run_json("--settings", str(fixture), *mode)
                    self.assertEqual(status, self.expected_exit(fixture, mode))
                    self.assertEqual(report["exit_code"], status)

    def test_error_fixtures_report_only_their_rule(self):
        for fixture in sorted(ERROR_FIXTURES.glob("*.yml")):
            with self.subTest(fixture.name):
                _, report = run_json("--settings", str(fixture), "--report-only")
                expected = EXPECTED_FIXTURE_RULES[fixture.name]
                self.assertEqual({item["rule"] for item in report["problems"]}, {expected})
                self.assertEqual({item["severity"] for item in report["problems"]}, {"Error"})
                self.assertFalse(report["ready"])

    def test_warnings_only_fixture_is_ready_with_warnings(self):
        _, report = run_json("--settings", str(FIXTURES / "warnings-only.yml"))

        self.assertTrue(report["ready"])
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertGreater(report["summary"]["warnings"], 0)

    def test_unusable_files_are_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.yml"
            empty.write_text("", encoding="utf-8")
            not_mapping = Path(directory) / "list.yml"
            not_mapping.write_text("- version\n", encoding="utf-8")
            unparseable = FIXTURES / "unparseable.yml"
            for path in (empty, not_mapping, unparseable, Path(directory) / "missing.yml"):
                for mode in self.MODES:
                    with self.subTest(file=path.name, mode=" ".join(mode) or "default"):
                        status, report = run_json("--settings", str(path), *mode)
                        self.assertEqual(status, 0 if "--report-only" in mode else 1)
                        self.assertFalse(report["ready"])
                        self.assertEqual(
                            [(item["field"], item["severity"], item["rule"]) for item in report["problems"]],
                            [(str(path), "Error", None)],
                        )

    def test_repository_path_finds_the_settings_file(self):
        with tempfile.TemporaryDirectory() as directory:
            repository = Path(directory)
            status, report = run_json(str(repository))
            self.assertEqual(status, 1)
            self.assertEqual(report["problems"][0]["message"], "file not found")

            (repository / ".github").mkdir()
            shutil.copy(FIXTURES / "compliant.yml", repository / ".github" / "pipeline-settings.yml")
            status, report = run_json(str(repository), "--strict")
            self.assertEqual(status, 0)
            self.assertEqual(report["settings_file"], str(repository / ".github" / "pipeline-settings.yml"))

    def test_settings_option_overrides_repository_path(self):
        fixture = ERROR_FIXTURES / "missing-test-command.yml"
        status, report = run_json(str(REPOSITORY_ROOT / "sample-app"), "--settings", str(fixture))

        self.assertEqual((status, report["settings_file"]), (1, str(fixture)))

    def test_text_output_leads_with_field_and_message(self):
        status, output = run_cli("--settings", str(ERROR_FIXTURES / "missing-test-command.yml"))

        self.assertEqual(status, 1)
        self.assertIn("Not ready: 1 error", output)
        self.assertIn("✗ service.test_command – must be a single line, not empty (CHK-11)", output)

    def test_markdown_output_has_a_problem_table(self):
        _, output = run_cli("--settings", str(ERROR_FIXTURES / "missing-test-command.yml"), "--format", "markdown")

        self.assertIn("**Not ready: 1 error**", output)
        self.assertIn("| ✗ Error | `service.test_command` | must be a single line, not empty | CHK-11 |", output)

    def test_strict_and_report_only_cannot_be_combined(self):
        with self.assertRaises(SystemExit):
            run_cli("--strict", "--report-only")

    def test_shipped_settings_pass_strict(self):
        for repository in (
            REPOSITORY_ROOT / "sample-app",
            REPOSITORY_ROOT / "packages" / "app-template",
            REPOSITORY_ROOT / "tests" / "fixtures" / "failing-test",
        ):
            with self.subTest(str(repository.relative_to(REPOSITORY_ROOT))):
                status, report = run_json(str(repository), "--strict")
                self.assertEqual((status, report["problems"]), (0, []))


if __name__ == "__main__":
    unittest.main()
