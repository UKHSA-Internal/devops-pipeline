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
ACCOUNT_ID = re.compile(r"[0-9]{12}")
PLACEHOLDER = re.compile(r"replace-with-|todo", re.IGNORECASE)
SUPPORTED_SETTINGS_VERSION = (1, 1)
SETTINGS_VERSION = re.compile(r"[0-9]+(\.[0-9]+)*")
SUITE_NAME = re.compile(r"[a-z0-9-]{1,32}")
MAX_SUITES = 10


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


def is_valid_account_id(value) -> bool:
    return is_text(value) and ACCOUNT_ID.fullmatch(value) is not None and value != "0" * 12


def is_approver_list(value) -> bool:
    return isinstance(value, list) and bool(value) and all(is_text(item) for item in value)


def is_relative_path(value) -> bool:
    """A non-empty path that stays inside the repository: not absolute and with no ".." part."""
    return (
        is_single_line(value)
        and not value.startswith(("/", "\\", "~"))
        and re.match(r"[A-Za-z]:", value) is None
        and ".." not in re.split(r"[/\\]", value)
    )


def one_of(options):
    return lambda value: isinstance(value, str) and value in options


def matches(pattern):
    return lambda value: isinstance(value, str) and pattern.fullmatch(value) is not None


def _key(field: str) -> str:
    return field.rsplit(".", 1)[-1]


def _walk_strings(value, field: str, seen=None):
    """Yield (field, value) for every string leaf reachable from value.

    Tracks container ids on the current path (not globally) so a cyclic YAML
    alias cannot recurse forever, while a value legitimately shared by more
    than one non-cyclic alias is still visited at each of its locations.
    """
    if seen is None:
        seen = set()
    if isinstance(value, str):
        yield field, value
    elif isinstance(value, dict):
        container_id = id(value)
        if container_id in seen:
            return
        seen = seen | {container_id}
        for key, item in value.items():
            yield from _walk_strings(item, f"{field}.{key}" if field else str(key), seen)
    elif isinstance(value, list):
        container_id = id(value)
        if container_id in seen:
            return
        seen = seen | {container_id}
        for index, item in enumerate(value):
            yield from _walk_strings(item, f"{field}[{index}]", seen)


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


@rule("CHK-20", ERROR)
def supported_version(settings, report):
    value = settings.get("version")
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return  # Reported by CHK-01.
    text = str(value).strip()
    if SETTINGS_VERSION.fullmatch(text) is None:
        return  # Reported by CHK-01 only when it is not text.
    parts = tuple(int(part) for part in text.split("."))
    width = max(len(parts), len(SUPPORTED_SETTINGS_VERSION))
    pad = lambda numbers: numbers + (0,) * (width - len(numbers))
    if pad(parts) > pad(SUPPORTED_SETTINGS_VERSION):
        supported = ".".join(str(part) for part in SUPPORTED_SETTINGS_VERSION)
        report.problem("version", f"{text} is newer than this pipeline supports (up to {supported})")


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
        # CHK-21 reports when neither test_command nor test is set.
        report.value(
            service, "service.test_command", is_single_line, "must be a single line, not empty", required=False
        )


@rule("CHK-21", ERROR)
def one_way_to_test(settings, report):
    service = settings.get("service")
    if not isinstance(service, dict):
        return  # Reported by CHK-02 and CHK-11.
    has_test, has_test_command = "test" in service, "test_command" in service
    if has_test and has_test_command:
        report.problem("service", "set only one of test and test_command, not both")
    elif not has_test and not has_test_command:
        report.problem("service", "set one of test and test_command")


def _test_block(settings):
    """Return the service.test mapping, or None when it is absent or not a mapping."""
    service = settings.get("service")
    test = service.get("test") if isinstance(service, dict) else None
    return test if isinstance(test, dict) else None


def _suite_names(test) -> set:
    suites = test.get("suites")
    entries = suites if isinstance(suites, list) else []
    return {entry["name"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("name"), str)}


NAME_MESSAGE = "must be 1 to 32 lowercase letters, digits and hyphens"


@rule("CHK-22", ERROR)
def test_suites(settings, report):
    service = settings.get("service")
    if not isinstance(service, dict) or "test" not in service:
        return
    test = report.section(service, "service.test")
    if test is None:
        return
    suites = report.entries(test, "service.test.suites")
    if isinstance(test.get("suites"), list) and not 1 <= len(test["suites"]) <= MAX_SUITES:
        report.problem("service.test.suites", f"must have 1 to {MAX_SUITES} suites")
    names = set()
    for field, suite in suites:
        report.value(suite, f"{field}.name", matches(SUITE_NAME), NAME_MESSAGE)
        name = suite.get("name")
        if isinstance(name, str) and SUITE_NAME.fullmatch(name):
            if name in names:
                report.problem(f"{field}.name", f"'{name}' is used by more than one suite")
            names.add(name)
    final = report.section(test, "service.test.final", required=False)
    if final is not None:
        report.value(final, "service.test.final.name", matches(SUITE_NAME), NAME_MESSAGE)
        if final.get("name") in names:
            report.problem("service.test.final.name", "must differ from every suite name")


@rule("CHK-23", ERROR)
def test_commands(settings, report):
    test = _test_block(settings)
    if test is None:
        return  # Reported by CHK-22.
    message = "must be a single line, not empty"
    report.value(test, "service.test.setup", is_single_line, message, required=False)
    suites = test.get("suites")
    for index, suite in enumerate(suites if isinstance(suites, list) else []):
        if isinstance(suite, dict):  # Other entries are reported by CHK-22.
            report.value(suite, f"service.test.suites[{index}].command", is_single_line, message)
    final = test.get("final")
    if isinstance(final, dict):
        report.value(final, "service.test.final.command", is_single_line, message)


def _path_list(report, parent, field, valid, message, required):
    """Report field if it is not a list of valid items; a required list must also be non-empty."""
    report.value(
        parent,
        field,
        lambda value: isinstance(value, list) and (not required or bool(value)) and all(valid(item) for item in value),
        message,
        required=required,
    )


@rule("CHK-24", ERROR)
def test_paths(settings, report):
    test = _test_block(settings)
    if test is None:
        return  # Reported by CHK-22.
    paths_message = "must be a list of relative paths inside the repository, without '..'"
    cache = report.section(test, "service.test.cache", required=False)
    if cache is not None:
        _path_list(report, cache, "service.test.cache.paths", is_relative_path, paths_message, required=True)
        _path_list(
            report, cache, "service.test.cache.key_files", is_single_line, "must be a list of file patterns", required=True
        )
    _path_list(report, test, "service.test.collect", is_relative_path, paths_message, required=False)


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
        report.value(
            environment,
            f"{field}.account_id",
            is_valid_account_id,
            "must be a 12-digit string, for example \"123456789012\", and not all zeros",
        )
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


# whole file


@rule("CHK-13", WARNING)
def no_placeholder_text(settings, report):
    for field, value in _walk_strings(settings, ""):
        if PLACEHOLDER.search(value):
            report.problem(field, "contains template placeholder text")
