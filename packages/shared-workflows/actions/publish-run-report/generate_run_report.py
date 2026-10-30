#!/usr/bin/env python3
"""Generate the standard pipeline run report and job summary."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


RESULTS = {
    "success": "PASSED",
    "failure": "FAILED",
    "cancelled": "FAILED",
    "skipped": "SKIPPED",
}


def map_result(result: str) -> str:
    try:
        return RESULTS[result]
    except KeyError as error:
        raise ValueError(f"Unexpected GitHub job result: {result!r}") from error


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_report(environment: dict[str, str], end_time: str) -> dict[str, object]:
    deploy_results = [
        environment[key]
        for key in ("deploy_dev_result", "deploy_preprod_result", "deploy_prod_result")
    ]
    ran_deploy_results = [result for result in deploy_results if result != "skipped"]
    deploy_status = (
        "SKIPPED"
        if not ran_deploy_results
        else "FAILED"
        if any(result in ("failure", "cancelled") for result in ran_deploy_results)
        else "PASSED"
    )
    verify_status = map_result(environment["verify_result"])
    environments = []
    for key, name, category in (
        ("deploy_dev_result", "Dev", "Dev"),
        ("deploy_preprod_result", "Pre-production", "Pre-production"),
        ("deploy_prod_result", "Production", "Production"),
    ):
        deploy_result = environment[key]
        if deploy_result == "skipped":
            continue
        environments.append(
            {
                "name": name,
                "category": category,
                "deploy_status": map_result(deploy_result),
                "verify_status": verify_status,
                "verified_at": end_time if verify_status == "PASSED" else None,
            }
        )

    return {
        "context": {
            "pipeline_run_id": environment["run_id"],
            "repository": environment["repository"],
            "change_id": environment["commit_sha"],
            "ref": environment["ref"],
            "workflow_ref": environment["workflow_ref"],
            "workflow_sha": environment["workflow_sha"],
            "trigger_type": "release",
        },
        "timestamps": {
            "start_time": environment["start_time"] or None,
            "end_time": end_time,
        },
        "stages": {
            "check": map_result(environment["check_result"]),
            "test": map_result(environment["test_result"]),
            "scan": map_result(environment["scan_result"]),
            "build": map_result(environment["build_result"]),
            "deploy": deploy_status,
        },
        "environments": environments,
        "governance": {
            # TODO: Populate governance values after parsing the settings contract.
            "compliance_verdict": None,
            "approval_mode": None,
            "exception_id": None,
            "approvers": None,
        },
    }


def append_summary(report: dict[str, object], summary_path: Path) -> None:
    stages = report["stages"]
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("## Pipeline Run Report\n\n")
        summary.write("| Stage | Result |\n| --- | --- |\n")
        for stage, result in stages.items():
            summary.write(f"| {stage.replace('-', ' ').title()} | **{result}** |\n")
        summary.write("\n")


def main() -> None:
    environment = {
        name: os.environ[name]
        for name in (
            "RUN_ID",
            "REPOSITORY",
            "COMMIT_SHA",
            "REF",
            "WORKFLOW_REF",
            "WORKFLOW_SHA",
            "START_TIME",
            "CHECK_RESULT",
            "TEST_RESULT",
            "SCAN_RESULT",
            "BUILD_RESULT",
            "DEPLOY_DEV_RESULT",
            "DEPLOY_PREPROD_RESULT",
            "DEPLOY_PROD_RESULT",
            "VERIFY_RESULT",
        )
    }
    normalized_environment = {
        key.lower(): value for key, value in environment.items()
    }
    end_time = utc_now()
    report = create_report(normalized_environment, end_time)
    output_path = Path(os.environ["REPORT_PATH"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    append_summary(report, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    print(f"[STAGE: PUBLISH-REPORT] Wrote run report: {output_path}")
    print("TODO: Set artifact retention from governance.retention_days.")


if __name__ == "__main__":
    main()
