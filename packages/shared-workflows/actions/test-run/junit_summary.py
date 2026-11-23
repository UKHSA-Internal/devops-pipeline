#!/usr/bin/env python3
"""Record the result of one test suite or final step.

Reads the JUnit XML files in <service directory>/test-results/ for a suite, writes the
result file the run record is built from, and appends a summary to the job summary.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path


def junit_totals(results_directory: Path) -> dict | None:
    """Return tests, failures, errors and duration summed over the XML files, or None if there are none."""
    totals = {"tests": 0, "failures": 0, "errors": 0, "duration_seconds": 0.0}
    found = False
    for path in sorted(results_directory.glob("*.xml")):
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError) as error:
            print(f"WARNING: Skipping unreadable JUnit file {path}: {error}", file=sys.stderr)
            continue
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        for suite in suites:
            try:
                tests = int(suite.get("tests", 0))
                failures = int(suite.get("failures", 0))
                errors = int(suite.get("errors", 0))
                duration = float(suite.get("time", 0))
            except ValueError:
                print(f"WARNING: Ignoring a malformed testsuite in {path}", file=sys.stderr)
                continue
            found = True
            totals["tests"] += tests
            totals["failures"] += failures
            totals["errors"] += errors
            totals["duration_seconds"] += duration
    if not found:
        return None
    totals["duration_seconds"] = round(totals["duration_seconds"], 3)
    return totals


def build_result(name: str, kind: str, outcome: str, totals: dict | None) -> dict:
    return {
        "name": name,
        "kind": kind,
        "result": "PASSED" if outcome == "success" else "FAILED",
        "tests": totals["tests"] if totals else None,
        "failures": totals["failures"] if totals else None,
        "errors": totals["errors"] if totals else None,
        "duration_seconds": totals["duration_seconds"] if totals else None,
    }


def summary_text(result: dict) -> str:
    title = f"### Test ({result['name']})\n\n"
    if result["tests"] is None:
        return title + f"- Result: **{result['result']}**\n\n"
    return (
        title
        + "| Result | Tests | Failures | Errors | Duration (s) |\n| --- | --- | --- | --- | --- |\n"
        + f"| **{result['result']}** | {result['tests']} | {result['failures']} | {result['errors']} "
        + f"| {result['duration_seconds']} |\n\n"
    )


def main() -> int:
    name, kind, outcome = os.environ["SUITE_NAME"], os.environ["STEP_KIND"], os.environ["RUN_OUTCOME"]
    totals = junit_totals(Path(os.environ["SERVICE_DIRECTORY"]) / "test-results") if kind == "suite" else None
    result = build_result(name, kind, outcome, totals)

    output = Path(os.environ["RESULT_DIRECTORY"]) / f"{name}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(summary_text(result))
    print(f"[STEP: TEST] {name}: {result['result']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
