import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CHECKER_PATH = REPOSITORY_ROOT / "packages" / "settings-checker" / "checker.py"
FIXTURES = REPOSITORY_ROOT / "tests" / "fixtures" / "settings"
CHECKER_SPEC = importlib.util.spec_from_file_location("settings_checker", CHECKER_PATH)
if CHECKER_SPEC is None or CHECKER_SPEC.loader is None:
    raise ImportError(f"Unable to load settings checker from {CHECKER_PATH}")
CHECKER = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(CHECKER)
SCHEMA = CHECKER.load_schema()


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
    return {item["rule"] for item in CHECKER.check(values, SCHEMA)}


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
    return status, json.loads(stdout.getvalue())


class SchemaTests(unittest.TestCase):
    def test_schema_is_valid_json_schema(self):
        from jsonschema import Draft202012Validator

        Draft202012Validator.check_schema(SCHEMA)

    def test_every_rule_has_a_severity(self):
        self.assertEqual(sorted(CHECKER.RULES), [f"CHK-{number:02d}" for number in range(1, 12)])
        for rule, (severity, _) in CHECKER.RULES.items():
            self.assertIn(severity, (CHECKER.BLOCKING, CHECKER.ADVISORY), rule)


class RuleTests(unittest.TestCase):
    def test_compliant_settings_have_no_violations(self):
        self.assertEqual(CHECKER.check(copy.deepcopy(COMPLIANT), SCHEMA), [])

    def test_failing_cases_report_only_their_rule(self):
        for rule, cases in FAILING_CASES.items():
            for label, change in cases.items():
                with self.subTest(rule=rule, case=label):
                    self.assertEqual(rules(settings(change)), {rule})

    def test_passing_cases_have_no_violations(self):
        for rule, cases in PASSING_CASES.items():
            for label, change in cases.items():
                with self.subTest(rule=rule, case=label):
                    self.assertEqual(rules(settings(change)), set())

    def test_every_rule_has_passing_and_failing_cases(self):
        self.assertEqual(set(FAILING_CASES), set(CHECKER.RULES))
        self.assertEqual(set(PASSING_CASES), set(CHECKER.RULES))

    def test_missing_service_reports_advisory_and_blocking_rules(self):
        self.assertEqual(rules(settings(delete_path(["service"]))), {"CHK-02", "CHK-11"})

    def test_missing_or_malformed_environments_report_structure_and_categories(self):
        for change in (delete_path(["environments"]), set_path(["environments"], "dev")):
            with self.subTest(change=change):
                self.assertEqual(rules(settings(change)), {"CHK-03", "CHK-04"})

    def test_violation_reports_rule_severity_message_and_path(self):
        violations = CHECKER.check(settings(delete_path(["environments", 1, "role_name"])), SCHEMA)

        self.assertEqual(
            violations,
            [
                {
                    "rule": "CHK-03",
                    "severity": "Blocking",
                    "path": "environments[1].role_name",
                    "message": "environments[1].role_name is required",
                }
            ],
        )

    def test_severities_match_contract(self):
        blocking = {"CHK-03", "CHK-04", "CHK-05", "CHK-08", "CHK-09", "CHK-10", "CHK-11"}
        for rule, (severity, _) in CHECKER.RULES.items():
            with self.subTest(rule):
                self.assertEqual(severity, "Blocking" if rule in blocking else "Advisory")


class ExitCodeTests(unittest.TestCase):
    ADVISORY = [{"severity": "Advisory"}]
    BLOCKING = [{"severity": "Blocking"}, {"severity": "Advisory"}]

    def test_exit_codes(self):
        cases = [
            ([], "pr", False, 0),
            ([], "pr", True, 0),
            (self.ADVISORY, "pr", False, 0),
            (self.ADVISORY, "pr", True, 1),
            (self.BLOCKING, "pr", False, 1),
            (self.BLOCKING, "pr", True, 1),
            (self.BLOCKING, "audit", False, 0),
            (self.BLOCKING, "audit", True, 0),
        ]
        for violations, mode, strict, expected in cases:
            with self.subTest(severities=[item["severity"] for item in violations], mode=mode, strict=strict):
                self.assertEqual(CHECKER.exit_code(violations, mode, strict), expected)


class CliTests(unittest.TestCase):
    MODES = (("--mode", "pr"), ("--mode", "pr", "--strict"), ("--mode", "audit"))

    def expected_exit(self, fixture, mode):
        if fixture == "unparseable.yml":
            return 1
        if "audit" in mode or fixture == "compliant.yml":
            return 0
        if fixture == "advisory-only.yml":
            return 1 if "--strict" in mode else 0
        return 1

    def test_every_fixture_in_every_mode(self):
        fixtures = sorted(path.name for path in FIXTURES.glob("*.yml"))
        blocking_fixtures = [f"blocking-chk-{rule[-2:]}.yml" for rule, (severity, _) in CHECKER.RULES.items()
                             if severity == CHECKER.BLOCKING]
        self.assertEqual(
            set(fixtures), {"compliant.yml", "advisory-only.yml", "unparseable.yml", *blocking_fixtures}
        )
        for fixture in fixtures:
            for mode in self.MODES:
                with self.subTest(fixture=fixture, mode=" ".join(mode)):
                    status, report = run_cli("--config", str(FIXTURES / fixture), *mode)
                    self.assertEqual(status, self.expected_exit(fixture, mode))
                    self.assertEqual(report["exit_code"], status)

    def test_blocking_fixtures_report_only_their_rule(self):
        for path in sorted(FIXTURES.glob("blocking-chk-*.yml")):
            with self.subTest(path.name):
                _, report = run_cli("--config", str(path), "--mode", "audit")
                rule = "CHK-" + path.stem.rsplit("-", 1)[1]
                self.assertEqual({item["rule"] for item in report["violations"]}, {rule})

    def test_advisory_fixture_reports_only_advisory_violations(self):
        _, report = run_cli("--config", str(FIXTURES / "advisory-only.yml"))

        self.assertEqual(report["status"], "NON_COMPLIANT")
        self.assertEqual(report["summary"]["blocking"], 0)
        self.assertGreater(report["summary"]["advisory"], 0)

    def test_unreadable_files_fail_in_every_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            empty = Path(directory) / "empty.yml"
            empty.write_text("", encoding="utf-8")
            not_mapping = Path(directory) / "list.yml"
            not_mapping.write_text("- version\n", encoding="utf-8")
            for path in (empty, not_mapping, Path(directory) / "missing.yml"):
                for mode in self.MODES:
                    with self.subTest(file=path.name, mode=" ".join(mode)):
                        status, report = run_cli("--config", str(path), *mode)
                        self.assertEqual(status, 1)
                        self.assertEqual(report["status"], "ERROR")

    def test_shipped_settings_pass_strict(self):
        for path in (
            REPOSITORY_ROOT / "sample-app" / ".github" / "pipeline-settings.yml",
            REPOSITORY_ROOT / "packages" / "app-template" / ".github" / "pipeline-settings.yml",
            REPOSITORY_ROOT / "tests" / "fixtures" / "failing-test" / ".github" / "pipeline-settings.yml",
        ):
            with self.subTest(str(path.relative_to(REPOSITORY_ROOT))):
                status, report = run_cli("--config", str(path), "--mode", "pr", "--strict")
                self.assertEqual((status, report["violations"]), (0, []))


if __name__ == "__main__":
    unittest.main()
