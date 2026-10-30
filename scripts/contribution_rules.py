#!/usr/bin/env python3
"""Validate commit, branch, pull-request, and ADR contribution rules."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

TYPES = ("feat", "fix", "chore", "docs", "refactor", "test")
SCOPES = (
    "workflows",
    "checker",
    "app-template",
    "sample-app",
    "fixtures",
    "docs",
    "repo",
    "deps",
)
BRANCH_TYPES = ("task", "feature", "fix", "chore", "refactor", "docs")
JIRA_KEY = re.compile(r"\b[A-Z][A-Z0-9]*-[0-9]+\b")
HEADER = re.compile(
    rf"^(?P<type>{'|'.join(TYPES)})"
    rf"\((?P<scope>{'|'.join(map(re.escape, SCOPES))})\)"
    r"(?P<breaking>!)?: (?P<description>\S.*)$"
)
BRANCH = re.compile(
    rf"^(?P<type>{'|'.join(BRANCH_TYPES)})/"
    r"(?:(?P<jira>[A-Z][A-Z0-9]*-[0-9]+)/)?"
    r"(?P<description>[a-z0-9]+(?:-[a-z0-9]+)*)$"
)
ADR_REFERENCE = re.compile(r"^\s*ADR:\s*(docs/adr/[A-Za-z0-9._-]+\.md)\s*$", re.MULTILINE)
BREAKING_HEADER = re.compile(r"^[a-z][a-z0-9-]*(?:\([^)\r\n]+\))?!:")


def first_subject(message: str) -> str:
    for line in message.splitlines():
        if line.strip() and not line.startswith("#"):
            return line
    return ""


def validate_commit_message(message: str) -> list[str]:
    subject = first_subject(message)
    if not HEADER.fullmatch(subject):
        return [
            "Commit header must use "
            "<type>(<scope>): <short description>, with an allowed type and scope."
        ]
    return []


def validate_pr_title(title: str) -> list[str]:
    errors = validate_commit_message(title)
    if not JIRA_KEY.search(title):
        errors.append("PR title must include a Jira key (for example, DP-123).")
    return errors


def validate_branch_name(branch: str) -> tuple[str | None, str | None]:
    match = BRANCH.fullmatch(branch)
    if not match:
        return None, (
            "Branch must use <type>/<JIRA-ID>/<description> or "
            "<type>/<description>, with a lower-case hyphenated description."
        )
    return match.group("jira"), None


def validate_branch_linkage(
    branch: str, pr_title: str, commit_messages: list[str]
) -> list[str]:
    jira_key, error = validate_branch_name(branch)
    if error:
        return [error]
    if jira_key is None and not (
        JIRA_KEY.search(pr_title)
        or any(JIRA_KEY.search(message) for message in commit_messages)
    ):
        return [
            "A branch without a Jira ID requires a Jira key in the PR title "
            "or a commit message."
        ]
    return []


def is_breaking_change(
    pr_title: str, commit_messages: list[str], labels: list[str]
) -> bool:
    if "breaking-change" in labels:
        return True

    messages = [pr_title, *commit_messages]
    for message in messages:
        subject = first_subject(message)
        if BREAKING_HEADER.match(subject):
            return True
        if re.search(r"^BREAKING CHANGE:", message, re.MULTILINE):
            return True
    return False


def adr_references(pr_body: str, commit_messages: list[str]) -> set[str]:
    text = "\n".join([pr_body, *commit_messages])
    return set(ADR_REFERENCE.findall(text))


def validate_adr_gate(
    breaking: bool,
    added_adr: bool,
    pr_body: str,
    commit_messages: list[str],
    existing_main_adrs: set[str],
) -> list[str]:
    if not breaking or added_adr:
        return []
    if adr_references(pr_body, commit_messages) & existing_main_adrs:
        return []
    return [
        "Breaking changes require a new Markdown file under docs/adr/ or an "
        "ADR reference in the PR description or a commit message that exists on main."
    ]


def git_output(*args: str) -> str:
    result = subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True
    )
    return result.stdout


def create_local_pull_request_event() -> dict[str, object]:
    branch = git_output("branch", "--show-current").strip()
    if not branch:
        raise ValueError("A local pull-request event requires a checked-out branch.")

    jira_key, error = validate_branch_name(branch)
    if error or jira_key is None:
        messages = git_output("log", "-5", "--format=%s").splitlines()
        jira_key = next(
            (match.group() for message in messages if (match := JIRA_KEY.search(message))),
            "DP-0",
        )

    return {
        "pull_request": {
            "title": f"chore(repo): run local pre-gate check ({jira_key})",
            "body": "",
            "labels": [],
            "base": {"sha": git_output("rev-parse", "origin/main").strip()},
            "head": {
                "sha": git_output("rev-parse", "HEAD").strip(),
                "ref": branch,
            },
        }
    }


def run_pull_request_validation() -> int:
    event_path = Path(os.environ["GITHUB_EVENT_PATH"])
    event = json.loads(event_path.read_text(encoding="utf-8"))
    if "pull_request" not in event:
        raise ValueError("The contribution validator requires a pull_request event.")

    pull_request = event["pull_request"]
    title = pull_request["title"]
    body = pull_request.get("body") or ""
    branch = pull_request["head"]["ref"]
    base_sha = pull_request["base"]["sha"]
    head_sha = pull_request["head"]["sha"]
    messages = [
        message
        for message in git_output(
            "log", "-z", "--format=%B", f"{base_sha}..{head_sha}"
        ).split("\0")
        if message.strip()
    ]
    labels = [label["name"] for label in pull_request.get("labels", [])]

    errors = validate_pr_title(title)
    for index, message in enumerate(messages, start=1):
        errors.extend(
            f"Commit {index}: {error}" for error in validate_commit_message(message)
        )
    errors.extend(validate_branch_linkage(branch, title, messages))

    breaking = is_breaking_change(title, messages, labels)
    added_adrs = {
        path
        for path in git_output(
            "diff",
            "--diff-filter=A",
            "--name-only",
            f"{base_sha}...{head_sha}",
            "--",
            "docs/adr",
        ).splitlines()
        if path.endswith(".md")
    }

    git_output("rev-parse", "--verify", "origin/main^{commit}")
    referenced_adrs = adr_references(body, messages)
    existing_main_adrs = {
        path
        for path in referenced_adrs
        if subprocess.run(
            ["git", "cat-file", "-e", f"origin/main:{path}"],
            capture_output=True,
        ).returncode
        == 0
    }
    errors.extend(
        validate_adr_gate(
            breaking,
            bool(added_adrs),
            body,
            messages,
            existing_main_adrs,
        )
    )

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Contribution rules validated.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    commit_parser = subparsers.add_parser("commit")
    commit_parser.add_argument("message_file")
    branch_parser = subparsers.add_parser("branch-local")
    branch_parser.add_argument("branch")
    subparsers.add_parser("pull-request")
    subparsers.add_parser("local-event")
    arguments = parser.parse_args()

    if arguments.command == "local-event":
        print(json.dumps(create_local_pull_request_event()))
        return 0
    if arguments.command == "commit":
        message = Path(arguments.message_file).read_text(encoding="utf-8")
        errors = validate_commit_message(message)
    elif arguments.command == "branch-local":
        _, error = validate_branch_name(arguments.branch)
        errors = [error] if error else []
    else:
        return run_pull_request_validation()

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"{arguments.command} rules validated.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, KeyError, ValueError, subprocess.CalledProcessError) as error:
        print(
            f"ERROR: Contribution validation could not complete: {error}",
            file=sys.stderr,
        )
        sys.exit(2)
