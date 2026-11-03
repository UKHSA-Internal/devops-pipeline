#!/usr/bin/env python3
"""Resolve the named deployments for each environment category from pipeline settings."""

import json
import os
import re
import sys
from pathlib import Path

CATEGORIES = {"Dev": "dev", "Pre-production": "preprod", "Production": "prod"}
REQUIRED_FIELDS = ("name", "category", "account_id", "role_name", "region")
NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
DEFAULT_HEALTH_ENDPOINT = "/health"
DEFAULT_TIMEOUT_SECONDS = 60


class SettingsError(ValueError):
    """Raised when the settings cannot be used to build the deployment plan."""


def resolve(settings: dict) -> dict:
    environments = settings.get("environments")
    if not isinstance(environments, list) or not environments:
        raise SettingsError("'environments' must list at least one deployment.")

    by_category = {key: [] for key in CATEGORIES.values()}
    seen_names = set()
    for position, environment in enumerate(environments, start=1):
        if not isinstance(environment, dict):
            raise SettingsError(f"environments[{position}] must be a mapping.")
        deployment = {}
        for field in REQUIRED_FIELDS:
            value = environment.get(field)
            if value is None or not str(value).strip():
                raise SettingsError(f"environments[{position}] is missing '{field}'.")
            deployment[field] = str(value).strip()
        if deployment["category"] not in CATEGORIES:
            raise SettingsError(
                f"environments[{position}] has unknown category {deployment['category']!r}; "
                f"expected one of {', '.join(CATEGORIES)}."
            )
        if not NAME_PATTERN.match(deployment["name"]):
            raise SettingsError(
                f"environments[{position}] name {deployment['name']!r} may only contain "
                "letters, numbers, '.', '_' and '-'."
            )
        if deployment["name"] in seen_names:
            raise SettingsError(f"Deployment name {deployment['name']!r} is used more than once.")
        seen_names.add(deployment["name"])
        by_category[CATEGORIES[deployment["category"]]].append(deployment)

    missing = [category for category, key in CATEGORIES.items() if not by_category[key]]
    if missing:
        raise SettingsError(f"No deployments defined for category: {', '.join(missing)}.")

    verification = settings.get("verification") or {}
    health_endpoint = str(verification.get("health_endpoint", DEFAULT_HEALTH_ENDPOINT))
    if not health_endpoint.startswith("/"):
        raise SettingsError("verification.health_endpoint must start with '/'.")
    timeout_seconds = verification.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)
    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or timeout_seconds < 1:
        raise SettingsError("verification.timeout_seconds must be a positive integer.")

    service = settings.get("service")
    test_command = service.get("test_command") if isinstance(service, dict) else None
    if not isinstance(test_command, str) or not test_command.strip():
        raise SettingsError("'service.test_command' must be a non-empty string.")
    if "\n" in test_command or "\r" in test_command:
        raise SettingsError("'service.test_command' must be a single line.")

    return {
        "test_command": test_command.strip(),
        "dev_deployments": by_category["dev"],
        "preprod_deployments": by_category["preprod"],
        "prod_deployments": by_category["prod"],
        "deployments": [item for key in CATEGORIES.values() for item in by_category[key]],
        "health_endpoint": health_endpoint,
        "timeout_seconds": timeout_seconds,
    }


def write_outputs(plan: dict, output_path: Path) -> None:
    with output_path.open("a", encoding="utf-8") as output:
        for key, value in plan.items():
            rendered = value if isinstance(value, (str, int)) else json.dumps(value, separators=(",", ":"))
            output.write(f"{key}={rendered}\n")


def append_summary(plan: dict, summary_path: Path) -> None:
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("### Deployment plan\n\n| Category | Deployment | Region |\n| --- | --- | --- |\n")
        for deployment in plan["deployments"]:
            summary.write(
                f"| {deployment['category']} | `{deployment['name']}` | {deployment['region']} |\n"
            )
        summary.write("\n")


def main() -> int:
    import yaml

    settings_path = Path(sys.argv[1])
    try:
        settings = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
        if not isinstance(settings, dict):
            raise SettingsError("Settings file must contain a YAML mapping.")
        plan = resolve(settings)
    except (OSError, yaml.YAMLError, SettingsError) as error:
        print(f"ERROR: Unable to resolve deployments from {settings_path}: {error}", file=sys.stderr)
        return 1

    write_outputs(plan, Path(os.environ["GITHUB_OUTPUT"]))
    append_summary(plan, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    names = ", ".join(item["name"] for item in plan["deployments"])
    print(f"[STEP: CHECK] Resolved {len(plan['deployments'])} deployments: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
