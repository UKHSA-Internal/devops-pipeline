"""UKHSA pipeline settings checker.

Validates .github/pipeline-settings.yml against the settings contract. Field
types and structure come from settings.schema.json; cross-field rules (CHK-03
unique names, CHK-04 and CHK-10) are checked here.
"""

import argparse
import json
import sys
from pathlib import Path

SCHEMA_PATH = Path(__file__).resolve().parent / "settings.schema.json"

BLOCKING = "Blocking"
ADVISORY = "Advisory"

RULES = {
    "CHK-01": (ADVISORY, "version is present and a string"),
    "CHK-02": (ADVISORY, "service.name, owner_team and language are present"),
    "CHK-03": (BLOCKING, "each environment has name, category, account_id, role_name and region, and category is valid"),
    "CHK-04": (BLOCKING, "every category (Development, Pre-production, Production) is mapped at least once"),
    # TODO: Also check each approver group exists in the platform approver config, once that config exists.
    "CHK-05": (BLOCKING, "governance.approvers is a non-empty list"),
    "CHK-06": (ADVISORY, "governance.retention_days is an integer greater than zero"),
    "CHK-07": (ADVISORY, "health_endpoint, if set, is a valid path; db_check_required is an explicit boolean"),
    "CHK-08": (BLOCKING, "each custom check has non-empty name and command, and an explicit boolean allow_failure"),
    "CHK-09": (BLOCKING, "deploy.production.approval_mode is all-approvers, single-approver or unattended"),
    "CHK-10": (BLOCKING, "when approval_mode is unattended, exception_id is non-empty"),
    "CHK-11": (BLOCKING, "service.test_command is a non-empty string"),
}

CATEGORIES = ("Development", "Pre-production", "Production")


class UnparseableSettings(ValueError):
    """Raised when the settings file cannot be read or is not a YAML mapping."""


def load_settings(path: Path) -> dict:
    import yaml

    try:
        settings = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError) as error:
        raise UnparseableSettings(f"Unable to parse settings file: {error}") from error
    if not isinstance(settings, dict):
        raise UnparseableSettings("Settings file must contain a YAML mapping.")
    return settings


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def format_path(parts) -> str:
    path = ""
    for part in parts:
        path += f"[{part}]" if isinstance(part, int) else (f".{part}" if path else str(part))
    return path


def violation(rule: str, path: str, message: str) -> dict:
    return {"rule": rule, "severity": RULES[rule][0], "path": path, "message": message}


def _rules_of(schema: dict) -> list:
    rule = schema.get("x-rule")
    if rule is None:
        return []
    return [rule] if isinstance(rule, str) else list(rule)


def _resolve_ref(schema: dict, root: dict) -> dict:
    ref = schema.get("$ref")
    if not ref:
        return schema
    target = root
    for part in ref.lstrip("#/").split("/"):
        target = target[part]
    return target


def _ancestor_rules(root: dict, schema_path) -> list:
    """Return the rules of the deepest annotated schema along the error's schema path."""
    rules, node = [], root
    for part in schema_path:
        if isinstance(node, dict):
            node = _resolve_ref(node, root) if part not in node else node
            if part not in node:
                break
        elif not isinstance(node, list):
            break
        node = node[part]
        if isinstance(node, dict) and _rules_of(node):
            rules = _rules_of(node)
    return rules


def schema_violations(settings: dict, schema: dict) -> list:
    from jsonschema import Draft202012Validator

    violations, seen_missing = [], set()
    for error in Draft202012Validator(schema).iter_errors(settings):
        parent = list(error.absolute_path)
        if error.validator == "required":
            for field in error.validator_value:
                if field in error.instance or (format_path(parent), field) in seen_missing:
                    continue
                seen_missing.add((format_path(parent), field))
                child = _resolve_ref(error.schema.get("properties", {}).get(field, {}), schema)
                rules = _rules_of(child) or _rules_of(error.schema) or _ancestor_rules(
                    schema, error.absolute_schema_path
                )
                path = format_path(parent + [field])
                violations.extend(violation(rule, path, f"{path} is required") for rule in rules)
            continue

        rules = _rules_of(error.schema) or _ancestor_rules(schema, error.absolute_schema_path)
        path = format_path(parent) or "(root)"
        detail = error.schema.get("x-message")
        message = f"{path} {detail}" if detail else f"{path}: {error.message}"
        violations.extend(violation(rule, path, message) for rule in rules)
    return violations


def cross_field_violations(settings: dict) -> list:
    violations = []

    environments = settings.get("environments")
    entries = environments if isinstance(environments, list) else []
    mapped, seen_names = set(), set()
    for index, environment in enumerate(entries):
        if not isinstance(environment, dict):
            continue
        mapped.add(environment.get("category"))
        name = environment.get("name")
        if isinstance(name, str) and name:
            if name in seen_names:
                path = f"environments[{index}].name"
                violations.append(violation("CHK-03", path, f"{path} {name!r} is used by more than one environment"))
            seen_names.add(name)

    for category in CATEGORIES:
        if category not in mapped:
            violations.append(
                violation("CHK-04", "environments", f"No environment is mapped to the {category} category")
            )

    deploy = settings.get("deploy")
    production = deploy.get("production") if isinstance(deploy, dict) else None
    if isinstance(production, dict) and production.get("approval_mode") == "unattended":
        exception_id = production.get("exception_id")
        if not isinstance(exception_id, str) or not exception_id.strip():
            violations.append(
                violation(
                    "CHK-10",
                    "deploy.production.exception_id",
                    "deploy.production.exception_id must be a non-empty string when approval_mode is unattended",
                )
            )

    return violations


def check(settings: dict, schema: dict) -> list:
    violations = schema_violations(settings, schema) + cross_field_violations(settings)
    return sorted(violations, key=lambda item: (item["rule"], item["path"], item["message"]))


def exit_code(violations: list, mode: str, strict: bool) -> int:
    if mode == "audit":
        return 0
    if strict:
        return 1 if violations else 0
    return 1 if any(item["severity"] == BLOCKING for item in violations) else 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="UKHSA Pipeline Standards Check Tool")
    parser.add_argument("--config", default=".github/pipeline-settings.yml", help="Path to settings file")
    parser.add_argument(
        "--mode",
        choices=["pr", "audit"],
        default="pr",
        help="pr: fail on Blocking violations; audit: report everything and always exit 0",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="In pr mode, fail on any violation, including Advisory ones",
    )
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    print(f"[STEP: CHECK] Checking settings file: {config_path}", file=sys.stderr)
    report = {"file_checked": str(config_path), "mode": args.mode, "strict": args.strict}

    try:
        settings = load_settings(config_path)
    except UnparseableSettings as error:
        report.update({"status": "ERROR", "exit_code": 1, "error": str(error)})
        print(json.dumps(report, indent=2))
        return 1

    violations = check(settings, load_schema())
    status = exit_code(violations, args.mode, args.strict)
    report.update(
        {
            "status": "NON_COMPLIANT" if violations else "COMPLIANT",
            "exit_code": status,
            "summary": {
                "blocking": sum(item["severity"] == BLOCKING for item in violations),
                "advisory": sum(item["severity"] == ADVISORY for item in violations),
            },
            "violations": violations,
        }
    )
    print(json.dumps(report, indent=2))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
