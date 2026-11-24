#!/usr/bin/env python3
"""Check that each Production approval environment exists and is gated by required reviewers.

A job that references a missing environment makes GitHub create it with no protection,
so a missing gate would let Production deploy unapproved. This guard fails the run first.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import quote

API = "https://api.github.com"
RETRIES = 3

PREREQUISITES = (
    "Grant 'actions: read' to the caller workflow, and create each approval environment "
    "in the repository settings with required reviewers (and 'Prevent self-review' enabled)."
)


class GuardError(Exception):
    pass


def request(url: str, token: str) -> list | dict:
    http_request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(http_request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404):
                raise GuardError(
                    f"the token cannot read the repository's environment settings (HTTP {error.code}). "
                    + PREREQUISITES
                ) from error
            failure = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError) as error:
            failure = str(error)
        if attempt < RETRIES:
            time.sleep(2**attempt)
    raise GuardError(f"could not read environment settings after {RETRIES} attempts ({failure})")


def fetch_environments(repository: str, token: str, get=request) -> dict[str, dict]:
    """Return every environment in the repository, keyed by lower-case name."""
    environments = {}
    page = 1
    while True:
        body = get(f"{API}/repos/{quote(repository, safe='/')}/environments?per_page=100&page={page}", token)
        batch = body.get("environments", [])
        for environment in batch:
            environments[environment["name"].lower()] = environment
        if len(batch) < 100:
            return environments
        page += 1


def reviewer_rules(environment: dict) -> list[dict]:
    return [
        rule
        for rule in environment.get("protection_rules") or []
        if rule.get("type") == "required_reviewers" and rule.get("reviewers")
    ]


def evaluate(expected: list[str], environments: dict[str, dict]) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for the expected approval environment names."""
    errors, warnings = [], []
    for name in expected:
        environment = environments.get(name.lower())
        if environment is None:
            errors.append(f"environment '{name}' does not exist. Create it with required reviewers.")
            continue
        rules = reviewer_rules(environment)
        if not rules:
            errors.append(f"environment '{name}' has no required reviewers.")
            continue
        if not any(rule.get("prevent_self_review") for rule in rules):
            errors.append(f"environment '{name}' does not prevent self-review. Enable 'Prevent self-review'.")
        if environment.get("can_admins_bypass") is not False:
            warnings.append(f"environment '{name}' lets administrators bypass its protection rules.")
    return errors, warnings


def main() -> int:
    plan = json.loads(os.environ["APPROVAL_ENVIRONMENTS"] or "[]")
    expected = [item["environment"] for item in plan]
    if not expected:
        print("[STEP: APPROVAL] Guard: no approval environments are expected (unattended).")
        return 0
    if os.environ.get("ACT") == "true":
        print(f"[STEP: APPROVAL] Guard: skipped under act; would check {', '.join(expected)}.")
        return 0

    try:
        environments = fetch_environments(os.environ["REPOSITORY"], os.environ["GH_TOKEN"])
    except GuardError as error:
        print(f"::error title=Approval guard::Cannot verify the approval environments: {error}")
        print("[STEP: APPROVAL] Guard FAILED")
        return 1

    errors, warnings = evaluate(expected, environments)
    for warning in warnings:
        print(f"::warning title=Approval guard::{warning}")
    for error in errors:
        print(f"::error title=Approval guard::{error}")
    if errors:
        print("[STEP: APPROVAL] Guard FAILED")
        return 1
    print(f"[STEP: APPROVAL] Guard passed for {', '.join(expected)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
