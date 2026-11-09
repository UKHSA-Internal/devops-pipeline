"""Rules for .github/pipeline-settings.yml, grouped by settings section.

Each rule is a function. Its decorator gives the rule ID and severity; the
messages it reports say what is wrong with a field. To add or change a rule,
edit it here, then update its cases in tests/test_settings_checker.py and the
rules table in README.md.
"""

import re
from typing import Callable, NamedTuple

ERROR = "Error"
WARNING = "Warning"

CATEGORIES = ("Development", "Pre-production", "Production")
APPROVAL_MODES = ("all-approvers", "single-approver", "unattended")
ENVIRONMENT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
URL_PATH = re.compile(r"/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*")


class Rule(NamedTuple):
    id: str
    severity: str
    check: Callable


RULES = []


def rule(rule_id: str, severity: str):
    def register(check):
        RULES.append(Rule(rule_id, severity, check))
        return check

    return register


def is_text(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_single_line(value) -> bool:
    return is_text(value) and "\n" not in value and "\r" not in value


def is_whole_number(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def is_positive(value) -> bool:
    return is_whole_number(value) and value > 0


def is_boolean(value) -> bool:
    return isinstance(value, bool)


def is_account_id(value) -> bool:
    return is_whole_number(value) or is_text(value)


def is_approver_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(is_text(item) for item in value)


def one_of(options):
    return lambda value: isinstance(value, str) and value in options


def matches(pattern):
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


def _key(field: str) -> str:
    return field.rsplit(".", 1)[-1]


class Report:
    """Collects the problems that one rule finds."""

    def __init__(self, rule: Rule):
        self.rule = rule
        self.problems = []

    def problem(self, field: str, message: str) -> None:
        self.problems.append(
            {"field": field, "severity": self.rule.severity, "message": message, "rule": self.rule.id}
        )

    def value(self, parent: dict, field: str, valid, message: str, required: bool = True) -> None:
        """Report field if it is missing (when required) or not valid."""
        key = _key(field)
        if key not in parent:
            if required:
                self.problem(field, "is required")
        elif not valid(parent[key]):
            self.problem(field, message)

    def section(self, parent: dict, field: str, required: bool = True):
        """Return the mapping at field, or None after reporting why it can't be used."""
        key = _key(field)
        if key not in parent:
            if required:
                self.problem(field, "is required")
            return None
        if not isinstance(parent[key], dict):
            self.problem(field, "must be a mapping")
            return None
        return parent[key]

    def entries(self, parent: dict, field: str, required: bool = True) -> list:
        """Return (field, mapping) for each entry of the list at field, reporting entries that aren't mappings."""
        key = _key(field)
        if key not in parent:
            if required:
                self.problem(field, "is required")
            return []
        if not isinstance(parent[key], list):
            self.problem(field, "must be a list")
            return []
        found = []
        for index, entry in enumerate(parent[key]):
            entry_field = f"{field}[{index}]"
            if isinstance(entry, dict):
                found.append((entry_field, entry))
            else:
                self.problem(entry_field, "must be a mapping")
        return found


def check(settings: dict) -> list:
    """Return every problem the rules find, in rule order.

    When several rules report the same problem, such as a missing section that
    each of them needs, it is reported once: with the highest severity and the
    rule IDs listed together, for example "CHK-02, CHK-11".
    """
    problems = {}
    for each in RULES:
        report = Report(each)
        each.check(settings, report)
        for problem in report.problems:
            key = (problem["field"], problem["message"])
            if key not in problems:
                problems[key] = problem
                continue
            existing = problems[key]
            existing["rule"] = ", ".join(sorted({*existing["rule"].split(", "), problem["rule"]}))
            if problem["severity"] == ERROR:
                existing["severity"] = ERROR
    return list(problems.values())


# version


@rule("CHK-01", WARNING)
def version(settings, report):
    report.value(settings, "version", lambda value: isinstance(value, str), 'must be text in quotes, for example "1.0"')


# service


@rule("CHK-02", WARNING)
def service_details(settings, report):
    service = report.section(settings, "service")
    if service is not None:
        for key in ("name", "owner_team", "language"):
            report.value(service, f"service.{key}", is_text, "must not be empty")


@rule("CHK-11", ERROR)
def test_command(settings, report):
    service = report.section(settings, "service")
    if service is not None:
        report.value(service, "service.test_command", is_single_line, "must be a single line, not empty")


# environments


@rule("CHK-03", ERROR)
def environment_fields(settings, report):
    names = set()
    for field, environment in report.entries(settings, "environments"):
        report.value(
            environment,
            f"{field}.name",
            matches(ENVIRONMENT_NAME),
            "must start with a letter or number and use only letters, numbers, '.', '_' and '-'",
        )
        report.value(environment, f"{field}.category", one_of(CATEGORIES), "must be one of " + ", ".join(CATEGORIES))
        report.value(environment, f"{field}.account_id", is_account_id, "must not be empty")
        for key in ("role_name", "region"):
            report.value(environment, f"{field}.{key}", is_text, "must not be empty")

        name = environment.get("name")
        if isinstance(name, str) and name:
            if name in names:
                report.problem(f"{field}.name", f"'{name}' is used by more than one environment")
            names.add(name)


@rule("CHK-04", ERROR)
def every_category_mapped(settings, report):
    environments = settings.get("environments")
    entries = environments if isinstance(environments, list) else []
    mapped = {entry.get("category") for entry in entries if isinstance(entry, dict)}
    for category in CATEGORIES:
        if category not in mapped:
            report.problem("environments", f"no environment is in the {category} category")


# governance


# TODO: Also check each approver group exists in the platform approver config, once that config exists.
@rule("CHK-05", ERROR)
def approvers(settings, report):
    governance = report.section(settings, "governance")
    if governance is not None:
        report.value(
            governance, "governance.approvers", is_approver_list, "must be a list of at least one approver group"
        )


@rule("CHK-06", WARNING)
def retention_days(settings, report):
    governance = report.section(settings, "governance")
    if governance is not None:
        report.value(
            governance, "governance.retention_days", is_positive, "must be a whole number greater than zero"
        )


# verification


# Both fields are optional; when missing, the defaults apply.
@rule("CHK-07", ERROR)
def health_check(settings, report):
    verification = report.section(settings, "verification", required=False)
    if verification is None:
        return
    report.value(
        verification,
        "verification.health_endpoint",
        matches(URL_PATH),
        "must be a URL path starting with '/'",
        required=False,
    )
    report.value(
        verification,
        "verification.timeout_seconds",
        is_positive,
        "must be a whole number greater than zero",
        required=False,
    )


@rule("CHK-12", WARNING)
def db_check_required(settings, report):
    verification = report.section(settings, "verification")
    if verification is not None:
        report.value(verification, "verification.db_check_required", is_boolean, "must be true or false")


@rule("CHK-08", ERROR)
def custom_checks(settings, report):
    verification = settings.get("verification")
    if not isinstance(verification, dict):
        return  # Reported by CHK-07.
    for field, custom_check in report.entries(verification, "verification.custom_checks", required=False):
        for key in ("name", "command"):
            report.value(custom_check, f"{field}.{key}", is_text, "must not be empty")
        report.value(custom_check, f"{field}.timeout_seconds", is_whole_number, "must be a whole number", required=False)
        report.value(custom_check, f"{field}.allow_failure", is_boolean, "must be true or false")


# deploy


@rule("CHK-09", ERROR)
def approval_mode(settings, report):
    deploy = report.section(settings, "deploy")
    production = report.section(deploy, "deploy.production") if deploy is not None else None
    if production is not None:
        report.value(
            production,
            "deploy.production.approval_mode",
            one_of(APPROVAL_MODES),
            "must be one of " + ", ".join(APPROVAL_MODES),
        )


@rule("CHK-10", ERROR)
def unattended_exception(settings, report):
    deploy = settings.get("deploy")
    production = deploy.get("production") if isinstance(deploy, dict) else None
    if (
        isinstance(production, dict)
        and production.get("approval_mode") == "unattended"
        and not is_text(production.get("exception_id"))
    ):
        report.problem("deploy.production.exception_id", "is required when approval_mode is unattended")
