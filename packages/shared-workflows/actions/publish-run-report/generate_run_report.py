#!/usr/bin/env python3
"""Generate the standard pipeline run report and job summary."""

from __future__ import annotations

import json
import os
import re
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


def load_deployment_results(
    planned: list[dict],
    results_dir: Path,
    active_categories: set[str],
    started_dir: Path,
) -> list[dict]:
    results = []
    for deployment in planned:
        if deployment["category"] not in active_categories:
            continue
        result_path = results_dir / f"{deployment['name']}.json"
        if result_path.is_file():
            results.append(json.loads(result_path.read_text(encoding="utf-8")))
        elif not (started_dir / deployment["name"]).is_file():
            # Cancelled by fail-fast before it began: unattempted, not a failure.
            continue
        else:
            results.append(
                {
                    "name": deployment["name"],
                    "category": deployment["category"],
                    "deploy_outcome": "failure",
                    "verify_outcome": "skipped",
                    "verified_at": None,
                    "result_error": f"Missing deployment result file: {result_path}",
                }
            )
    return results


def create_report(
    environment: dict[str, str], end_time: str, deployment_results: list[dict] | None = None
) -> dict[str, object]:
    deploy_results = [
        environment[key]
        for key in ("deploy_dev_result", "deploy_preprod_result", "deploy_prod_result")
    ]
    ran_deploy_results = [result for result in deploy_results if result != "skipped"]
    has_failed_deployment = any(
        result in ("failure", "cancelled") for result in ran_deploy_results
    ) or any(result.get("result_error") for result in deployment_results or [])
    deploy_status = (
        "SKIPPED"
        if not ran_deploy_results
        else "FAILED"
        if has_failed_deployment
        else "PASSED"
    )
    environments = [
        {
            "name": result["name"],
            "category": result["category"],
            "deploy_status": map_result(result["deploy_outcome"]),
            "verify_status": map_result(result["verify_outcome"]),
            "image_tag": result.get("image_tag"),
            "verified_at": result.get("verified_at"),
            **({"error": result["result_error"]} if result.get("result_error") else {}),
        }
        for result in deployment_results or []
        if result["deploy_outcome"] != "skipped"
    ]

    return {
        "context": {
            "pipeline_run_id": environment["run_id"],
            "repository": environment["repository"],
            "change_id": environment["commit_sha"],
            "ref": environment["ref"],
            "workflow_ref": environment["workflow_ref"],
            "workflow_sha": environment["workflow_sha"],
            "workflow_package_version": environment["workflow_package_version"],
            "trigger_type": environment["trigger_type"],
        },
        "timestamps": {
            "start_time": environment["start_time"] or None,
            "end_time": end_time,
        },
        "steps": {
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
    steps = report["steps"]
    with summary_path.open("a", encoding="utf-8") as summary:
        summary.write("## Pipeline Run Report\n\n")
        summary.write("| Step | Result |\n| --- | --- |\n")
        for step, result in steps.items():
            summary.write(f"| {step.replace('-', ' ').title()} | **{result}** |\n")
        summary.write("\n")
        summary.write("| Deployment | Category | Deploy | Verify |\n| --- | --- | --- | --- |\n")
        for deployment in report["environments"]:
            summary.write(
                f"| {deployment['name']} | {deployment['category']} | "
                f"**{deployment['deploy_status']}** | **{deployment['verify_status']}** |\n"
            )
            if "error" in deployment:
                summary.write(f"\n**ERROR:** {deployment['error']}\n")
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
            "TRIGGER_TYPE",
            "START_TIME",
            "CHECK_RESULT",
            "TEST_RESULT",
            "SCAN_RESULT",
            "BUILD_RESULT",
            "DEPLOY_DEV_RESULT",
            "DEPLOY_PREPROD_RESULT",
            "DEPLOY_PROD_RESULT",
        )
    }
    normalized_environment = {
        key.lower(): value for key, value in environment.items()
    }
    version_path = Path(os.environ["VERSION_FILE"])
    version = version_path.read_text(encoding="utf-8").rstrip("\n")
    if not re.fullmatch(r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", version):
        raise ValueError(f"Invalid workflow package version in {version_path}: {version!r}")
    normalized_environment["workflow_package_version"] = version
    planned_deployments = json.loads(os.environ.get("DEPLOYMENTS") or "[]")
    deployment_results_by_category = {
        "Development": normalized_environment["deploy_dev_result"],
        "Pre-production": normalized_environment["deploy_preprod_result"],
        "Production": normalized_environment["deploy_prod_result"],
    }
    deployment_results = load_deployment_results(
        planned_deployments,
        Path(os.environ["RESULTS_DIR"]),
        {
            category
            for category, result in deployment_results_by_category.items()
            if result != "skipped"
        },
        Path(os.environ["STARTED_DIR"]),
    )
    for result in deployment_results:
        if result.get("result_error"):
            print(f"ERROR: {result['result_error']}")
    end_time = utc_now()
    report = create_report(normalized_environment, end_time, deployment_results)
    output_path = Path(os.environ["REPORT_PATH"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    append_summary(report, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    print(f"[STEP: PUBLISH-REPORT] Wrote run report: {output_path}")
    print("TODO: Set artifact retention from governance.retention_days.")


if __name__ == "__main__":
    main()
