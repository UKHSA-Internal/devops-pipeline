#!/usr/bin/env python3
"""Parse detect-secrets scan output, filter out baseline findings, and report.

Report-only: enforcement never fails the step, however many findings there
are. Only the file, line number and secret type are surfaced in the log and
job summary; the secret value and even its hash are never printed.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# TODO: Switch to "blocking" once Cyber confirms the secret-scanning policy.
# Blocking mode is not implemented yet: findings are always report-only.
ENFORCEMENT_MODE = "report-only"


def results_from_data(data: dict) -> dict[str, list[dict]]:
    return data.get("results", {})


def load_results(path: Path) -> dict[str, list[dict]]:
    return results_from_data(json.loads(path.read_text(encoding="utf-8")))


# Aliases kept for readability where the input is already an in-memory dict
# (used directly by unit tests, without touching the filesystem).
load_results_from_dict = results_from_data


def hashes_from_results(results: dict[str, list[dict]]) -> set[tuple[str, str]]:
    return {
        (filename, finding["hashed_secret"])
        for filename, findings in results.items()
        for finding in findings
    }


def baseline_hashes_from_dict(data: dict) -> set[tuple[str, str]]:
    """Return the (filename, hashed_secret) pairs already known to the baseline."""
    return hashes_from_results(results_from_data(data))


def baseline_hashes(path: Path) -> set[tuple[str, str]]:
    """Return the (filename, hashed_secret) pairs already known to the baseline."""
    if not path.is_file():
        return set()
    return baseline_hashes_from_dict(json.loads(path.read_text(encoding="utf-8")))


def new_findings(scan_results: dict[str, list[dict]], known: set[tuple[str, str]]) -> list[dict]:
    """Findings from a live scan that aren't already suppressed by the baseline."""
    findings = [
        {"file": filename, "line": finding["line_number"], "type": finding["type"]}
        for filename, findings_for_file in scan_results.items()
        for finding in findings_for_file
        if (filename, finding["hashed_secret"]) not in known
    ]
    findings.sort(key=lambda finding: (finding["file"], finding["line"]))
    return findings


def log_findings(findings: list[dict]) -> None:
    if not findings:
        print("[STEP: SCAN] No secret findings.")
        return
    print(
        f"[STEP: SCAN] {len(findings)} secret finding(s) "
        "(report-only; secret values are never shown):"
    )
    for finding in findings:
        print(f"[STEP: SCAN]   {finding['file']}:{finding['line']} ({finding['type']})")


def write_summary(findings: list[dict], baseline_used: bool, summary_path: Path) -> None:
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("## Scan\n\n")
        summary.write(f"- Mode: **{ENFORCEMENT_MODE}**\n")
        summary.write(f"- Baseline used: **{'yes' if baseline_used else 'no'}**\n")
        summary.write(f"- Findings: **{len(findings)}**\n\n")
        if findings:
            summary.write("| File | Line | Type |\n| --- | --- | --- |\n")
            for finding in findings:
                summary.write(f"| {finding['file']} | {finding['line']} | {finding['type']} |\n")
            summary.write("\n")


def write_outputs(findings: list[dict], baseline_used: bool, output_path: Path) -> None:
    with output_path.open("a", encoding="utf-8") as outputs:
        outputs.write(f"findings_total={len(findings)}\n")
        outputs.write(f"baseline_used={'true' if baseline_used else 'false'}\n")


def main() -> int:
    scan_results = load_results(Path(os.environ["SCAN_RESULTS_PATH"]))
    baseline_path = Path(os.environ["BASELINE_PATH"])
    baseline_used = baseline_path.is_file()
    known = baseline_hashes(baseline_path)
    findings = new_findings(scan_results, known)

    log_findings(findings)
    write_summary(findings, baseline_used, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    write_outputs(findings, baseline_used, Path(os.environ["GITHUB_OUTPUT"]))

    if findings and ENFORCEMENT_MODE == "blocking":
        print(f"[STEP: SCAN] Exit code 1 ({ENFORCEMENT_MODE})")
        return 1

    print(f"[STEP: SCAN] Exit code 0 ({ENFORCEMENT_MODE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
