#!/usr/bin/env python3
"""Record the result of one test suite or final step.

Every step is treated the same way. Its result comes from the command's outcome, its timing
and the optional files the step wrote to <service directory>/test-results/: JUnit XML
(*.xml) and a Cobertura coverage.xml. Only files written or changed while the step's command
ran are read, so files downloaded from other jobs are never counted for this step.

`junit_summary.py snapshot` records the files that exist before the command runs. With no
argument, the script writes the result file the run record is built from and appends this
step's summary to the job summary.
"""

from __future__ import annotations

import json
import os
import sys
import xml.etree.ElementTree as ElementTree
from pathlib import Path

MAX_FAILED_TESTS = 10
COVERAGE_FILE = "coverage.xml"


def snapshot(results_directory: Path) -> dict:
    """Return the modification time of every XML file in the results directory."""
    return {path.name: path.stat().st_mtime_ns for path in results_directory.glob("*.xml") if path.is_file()}


def changed_files(results_directory: Path, before: dict) -> list:
    """Return the XML files that are new or were modified since the snapshot."""
    return [
        path
        for path in sorted(results_directory.glob("*.xml"))
        if path.is_file() and before.get(path.name) != path.stat().st_mtime_ns
    ]


def first_line(text: str | None) -> str:
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()[:200]
    return ""


def read_junit(paths: list) -> tuple:
    """Return (totals, failed tests) from the JUnit files; totals is None if no testsuite was found.

    A testsuite counts only if tests, failures, errors and time all parse. The duration is
    None when no counted testsuite gave a time.
    """
    totals = {"tests": 0, "failures": 0, "errors": 0, "duration_seconds": None}
    found = False
    failed = []
    for path in paths:
        try:
            root = ElementTree.parse(path).getroot()
        except (ElementTree.ParseError, OSError) as error:
            print(f"WARNING: Skipping unreadable JUnit file {path}: {error}", file=sys.stderr)
            continue
        for case in root.iter("testcase"):
            problem = next((child for child in case if child.tag in ("failure", "error")), None)
            if problem is not None:
                test_id = ".".join(part for part in (case.get("classname"), case.get("name")) if part)
                failed.append((test_id, first_line(problem.get("message")) or first_line(problem.text)))
        suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
        for suite in suites:
            try:
                tests = int(suite.get("tests", 0))
                failures = int(suite.get("failures", 0))
                errors = int(suite.get("errors", 0))
                time_text = suite.get("time")
                duration = float(time_text) if time_text is not None else None
            except ValueError:
                print(f"WARNING: Ignoring a malformed testsuite in {path}", file=sys.stderr)
                continue
            found = True
            totals["tests"] += tests
            totals["failures"] += failures
            totals["errors"] += errors
            if duration is not None:
                totals["duration_seconds"] = (totals["duration_seconds"] or 0.0) + duration
    if not found:
        return None, failed
    if totals["duration_seconds"] is not None:
        totals["duration_seconds"] = round(totals["duration_seconds"], 3)
    return totals, failed


def percent(value: str | None) -> float | None:
    """Turn a Cobertura rate (0 to 1) into a percentage with one decimal place."""
    if value is None:
        return None
    rate = float(value)
    if not 0 <= rate <= 1:
        raise ValueError(f"rate {value} is outside 0 to 1")
    return round(rate * 100, 1)


def read_coverage(path: Path) -> tuple:
    """Return (line percent, branch percent) from a Cobertura file. A bad file gives a warning and Nones."""
    try:
        root = ElementTree.parse(path).getroot()
        line = percent(root.get("line-rate"))
        if line is None:
            raise ValueError("no line-rate on the root element")
        try:
            branch = percent(root.get("branch-rate"))
        except ValueError:
            branch = None
        return line, branch
    except (ElementTree.ParseError, OSError, ValueError) as error:
        print(f"WARNING: Ignoring unreadable coverage file {path}: {error}", file=sys.stderr)
        return None, None


def build_result(
    name: str, kind: str, outcome: str, totals: dict | None, timing: float | None = None, coverage: tuple = (None, None)
) -> dict:
    """Combine the outcome, JUnit totals, timing and coverage. JUnit's duration wins over the timing."""
    junit_duration = totals["duration_seconds"] if totals else None
    return {
        "name": name,
        "kind": kind,
        "result": "PASSED" if outcome == "success" else "FAILED",
        "tests": totals["tests"] if totals else None,
        "failures": totals["failures"] if totals else None,
        "errors": totals["errors"] if totals else None,
        "duration_seconds": junit_duration if junit_duration is not None else timing,
        "coverage_percent": coverage[0],
        "branch_percent": coverage[1],
    }


def summary_text(result: dict, runtime: str = "", failed: list | None = None) -> str:
    parts = [f"**{result['result']}**"]
    if result["duration_seconds"] is not None:
        parts.append(f"{result['duration_seconds']}s")
    if runtime:
        parts.append(runtime)
    if result["tests"] is not None:
        parts.append(f"{result['tests']} tests, {result['failures']} failures, {result['errors']} errors")
    if result["coverage_percent"] is not None:
        text = f"Coverage: {result['coverage_percent']:.1f}%"
        if result.get("branch_percent") is not None:
            text += f" (branches {result['branch_percent']:.1f}%)"
        parts.append(text)
    text = f"## Test ({result['name']})\n\n" + " · ".join(parts) + "\n\n"
    failed = failed or []
    if failed:
        text += "Failed tests:\n\n"
        for test_id, message in failed[:MAX_FAILED_TESTS]:
            text += f"- `{test_id}`" + (f": {message}" if message else "") + "\n"
        if len(failed) > MAX_FAILED_TESTS:
            text += f"- and {len(failed) - MAX_FAILED_TESTS} more\n"
        text += "\n"
    return text


def timing_seconds(milliseconds: str) -> float | None:
    try:
        return round(int(milliseconds) / 1000, 3)
    except ValueError:
        return None


def main() -> int:
    results_directory = Path(os.environ["SERVICE_DIRECTORY"]) / "test-results"
    snapshot_file = Path(os.environ["SNAPSHOT_FILE"]) if os.environ.get("SNAPSHOT_FILE") else None
    if sys.argv[1:] == ["snapshot"]:
        if snapshot_file:
            snapshot_file.write_text(json.dumps(snapshot(results_directory)), encoding="utf-8")
        return 0

    name, kind, outcome = os.environ["SUITE_NAME"], os.environ["STEP_KIND"], os.environ["RUN_OUTCOME"]
    before = json.loads(snapshot_file.read_text(encoding="utf-8")) if snapshot_file and snapshot_file.is_file() else {}
    files = changed_files(results_directory, before)
    totals, failed = read_junit(files)
    coverage = (None, None)
    for path in files:
        if path.name == COVERAGE_FILE:
            coverage = read_coverage(path)
    result = build_result(name, kind, outcome, totals, timing_seconds(os.environ.get("DURATION_MS", "")), coverage)

    output = Path(os.environ["RESULT_DIRECTORY"]) / f"{name}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
        summary.write(summary_text(result, os.environ.get("RUNTIME_DESCRIPTION", ""), failed))
    print(f"[STEP: TEST] {name}: {result['result']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
