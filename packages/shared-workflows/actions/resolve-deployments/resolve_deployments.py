#!/usr/bin/env python3
"""Resolve the named deployments for each environment category from pipeline settings.

The settings checker validates the settings first; this script only reads them.
"""

import json
import os
import re
import secrets
import sys
from pathlib import Path

CATEGORIES = {"Development": "dev", "Pre-production": "preprod", "Production": "prod"}
DEPLOYMENT_FIELDS = ("name", "category", "account_id", "role_name", "region")
DEFAULT_HEALTH_ENDPOINT = "/health"
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_APPROVAL_MODE = "all-approvers"
APPROVAL_ENVIRONMENT = "production-approval"
# GitHub limits environment names to 255 characters.
MAX_GROUP_LENGTH = 255 - len(APPROVAL_ENVIRONMENT) - 1
GROUP_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")


def resolve_approval(settings: dict) -> dict:
    """Plan the Production approval jobs: one gated environment per group, one in total, or none."""
    deploy = settings.get("deploy")
    production = deploy.get("production") if isinstance(deploy, dict) else None
    production = production if isinstance(production, dict) else {}
    mode = production.get("approval_mode", DEFAULT_APPROVAL_MODE)
    exception_id = str(production.get("exception_id") or "").strip()
    if mode == "unattended":
        return {"approval_mode": mode, "approval_environments": [], "approval_exception_id": exception_id}

    governance = settings.get("governance")
    groups = governance.get("approvers") if isinstance(governance, dict) else None
    if not isinstance(groups, list) or not groups:
        raise ValueError("governance.approvers must list at least one approver group")
    groups = [str(group).strip() for group in groups]
    seen = set()
    for group in groups:
        if not GROUP_NAME.fullmatch(group) or len(group) > MAX_GROUP_LENGTH:
            raise ValueError(
                f"approver group {group!r} cannot be used in a GitHub environment name "
                f"(letters, digits, '.', '_' and '-'; at most {MAX_GROUP_LENGTH} characters)"
            )
        # GitHub treats environment names and concurrency groups as case-insensitive.
        if group.lower() in seen:
            raise ValueError(f"approver group {group!r} is listed more than once (names are case-insensitive)")
        seen.add(group.lower())

    if mode == "single-approver":
        environments = [{"environment": APPROVAL_ENVIRONMENT, "groups": groups}]
    else:
        environments = [{"environment": f"{APPROVAL_ENVIRONMENT}-{group}", "groups": [group]} for group in groups]
    return {"approval_mode": mode, "approval_environments": environments, "approval_exception_id": exception_id}


def resolve(settings: dict) -> dict:
    """Build the deployment plan from settings already validated by the settings checker."""
    by_category = {key: [] for key in CATEGORIES.values()}
    for environment in settings["environments"]:
        deployment = {field: str(environment[field]).strip() for field in DEPLOYMENT_FIELDS}
        by_category[CATEGORIES[deployment["category"]]].append(deployment)

    # Check rejects a malformed health_endpoint or timeout_seconds (CHK-07); fall back to
    # the defaults if verification itself is missing or unusable.
    verification = settings.get("verification")
    if not isinstance(verification, dict):
        verification = {}

    # Check only warns that service.language is present (CHK-02), so treat a missing or
    # malformed value as "no runtime", which the Test step reports as unsupported.
    language = settings["service"].get("language")
    language = language.strip().lower() if isinstance(language, str) else ""

    return {
        "test_command": settings["service"]["test_command"].strip(),
        "language": language,
        "dev_deployments": by_category["dev"],
        "preprod_deployments": by_category["preprod"],
        "prod_deployments": by_category["prod"],
        "deployments": [item for key in CATEGORIES.values() for item in by_category[key]],
        "health_endpoint": verification.get("health_endpoint", DEFAULT_HEALTH_ENDPOINT),
        "timeout_seconds": verification.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS),
        **resolve_approval(settings),
    }


def write_outputs(plan: dict, output_path: Path) -> None:
    # Use delimited outputs so a value containing a newline can't add extra outputs.
    delimiter = f"EOF_{secrets.token_hex(16)}"
    with output_path.open("a", encoding="utf-8") as output:
        for key, value in plan.items():
            rendered = value if isinstance(value, (str, int)) else json.dumps(value, separators=(",", ":"))
            output.write(f"{key}<<{delimiter}\n{rendered}\n{delimiter}\n")


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
        plan = resolve(yaml.safe_load(settings_path.read_text(encoding="utf-8")))
    except (OSError, yaml.YAMLError, ValueError) as error:
        print(f"ERROR: Unable to resolve deployments from {settings_path}: {error}", file=sys.stderr)
        return 1

    write_outputs(plan, Path(os.environ["GITHUB_OUTPUT"]))
    append_summary(plan, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    names = ", ".join(item["name"] for item in plan["deployments"])
    print(f"[STEP: CHECK] Resolved {len(plan['deployments'])} deployments: {names}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
