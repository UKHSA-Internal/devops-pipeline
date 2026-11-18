#!/usr/bin/env python3
"""Generate the standard pipeline run report and job summary."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import approvals as approvals_api  # noqa: E402

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


def blocked_reason(environment: dict[str, str], approvers: list[dict] | None) -> str | None:
    """Return why Production did not deploy because of the approval gate, or None if it was not blocked."""
    if environment.get("deploy_prod_result", "skipped") != "skipped":
        return None
    if environment.get("approval_guard_result") == "failure":
        return "approval guard failed"
    approve_result = environment.get("approve_result", "")
    if approve_result not in ("failure", "cancelled"):
        return None
    first_by_decision = {}
    for entry in approvers or []:
        first_by_decision.setdefault(entry["decision"], entry)
    if "rejected" in first_by_decision:
        entry = first_by_decision["rejected"]
        return f"approval rejected by {entry['approver']} ({entry['environment']})"
    if "expired" in first_by_decision:
        return f"approval expired ({first_by_decision['expired']['environment']})"
    return f"approval job {approve_result}"


def simulated_stages(deployment_results: list[dict]) -> list[str]:
    ran = [result for result in deployment_results if result["deploy_outcome"] != "skipped"]
    return [
        stage
        for stage in ("deploy", "verify")
        if any(result.get(f"{stage}_simulated") for result in ran)
    ]


def deploy_step_status(environment: dict[str, str], deployment_results: list[dict], blocked: str | None) -> str:
    """Aggregate the deploy step: SKIPPED if nothing ran and nothing was blocked, FAILED on any failure."""
    ran = [
        environment[key]
        for key in ("deploy_dev_result", "deploy_preprod_result", "deploy_prod_result")
        if environment[key] != "skipped"
    ]
    if not ran and blocked is None:
        return "SKIPPED"
    failed = (
        blocked is not None
        or any(result in ("failure", "cancelled") for result in ran)
        or any(result.get("result_error") for result in deployment_results)
    )
    return "FAILED" if failed else "PASSED"


def environment_entries(deployment_results: list[dict], planned: list[dict], blocked: str | None) -> list[dict]:
    """One entry per deployment that ran, plus SKIPPED Production entries when approval blocked it."""
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
        for result in deployment_results
        if result["deploy_outcome"] != "skipped"
    ]
    if blocked is not None:
        image_tags = [result.get("image_tag") for result in deployment_results if result.get("image_tag")]
        environments.extend(
            {
                "name": deployment["name"],
                "category": deployment["category"],
                "deploy_status": "SKIPPED",
                "verify_status": "SKIPPED",
                "image_tag": image_tags[0] if image_tags else None,
                "verified_at": None,
                "skipped_reason": blocked,
            }
            for deployment in planned
            if deployment["category"] == "Production"
        )
    return environments


def governance_block(environment: dict[str, str], approvals: dict) -> dict[str, object]:
    mode = environment.get("approval_mode")
    return {
        # TODO: Populate compliance_verdict after parsing the settings contract.
        "compliance_verdict": None,
        "approval_mode": mode or None,
        "exception_id": (environment.get("approval_exception_id") or None) if mode == "unattended" else None,
        "approvers": approvals["approvers"],
        **({"approvals_unavailable": True} if approvals["unavailable"] else {}),
    }


def create_report(
    environment: dict[str, str],
    end_time: str,
    deployment_results: list[dict] | None = None,
    approvals: dict | None = None,
    planned: list[dict] | None = None,
) -> dict[str, object]:
    approvals = approvals or {"approvers": [], "unavailable": False}
    deployment_results = deployment_results or []
    blocked = blocked_reason(environment, approvals["approvers"])

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
            "deploy": deploy_step_status(environment, deployment_results, blocked),
        },
        "environments": environment_entries(deployment_results, planned or [], blocked),
        "simulated_stages": simulated_stages(deployment_results),
        "governance": governance_block(environment, approvals),
    }


def collect_approvals(environment: dict[str, str], get_reviews=None, get_jobs=None) -> dict:
    """Read the approval decisions, or report that they are unavailable. Never raises."""
    plan = json.loads(environment.get("approval_environments") or "[]")
    if (
        environment.get("approval_mode") == "unattended"
        or not plan
        or environment.get("approve_result", "") in ("", "skipped")
    ):
        return {"approvers": [], "unavailable": False}
    try:
        if os.environ.get("ACT") == "true":
            raise approvals_api.ApprovalsUnavailable("the review history is not available under act")
        repository, run_id = environment["repository"], environment["run_id"]
        token, attempt = os.environ["GH_TOKEN"], os.environ.get("RUN_ATTEMPT") or "1"
        reviews = (get_reviews or approvals_api.fetch_reviews)(repository, run_id, token)
        jobs = (get_jobs or approvals_api.fetch_jobs)(repository, run_id, attempt, token)
        approvers = approvals_api.build_approvers(
            plan,
            reviews,
            jobs,
            environment.get("gate_opened_at", ""),
            float(os.environ.get("MAX_AGE_HOURS") or 24),
        )
    except (approvals_api.ApprovalsUnavailable, KeyError, TypeError, ValueError, AttributeError) as error:
        print(
            "::warning title=Run record::Approval details are unavailable "
            f"({error}). Grant 'actions: read' to the caller workflow."
        )
        return {"approvers": None, "unavailable": True}
    return {"approvers": approvers, "unavailable": False}


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
            if "skipped_reason" in deployment:
                summary.write(f"\n**{deployment['name']} skipped:** {deployment['skipped_reason']}\n")
        summary.write("\n")
        simulated = ", ".join(report["simulated_stages"]) or "none"
        summary.write(f"**Simulated stages:** {simulated}\n\n")
        governance = report["governance"]
        if governance["approvers"]:
            summary.write("| Approval environment | Approver | Decision | Time (UTC) |\n| --- | --- | --- | --- |\n")
            for entry in governance["approvers"]:
                summary.write(
                    f"| {entry['environment']} | {entry['approver']} | **{entry['decision']}** | "
                    f"{entry['timestamp']} |\n"
                )
            summary.write("\n")
        elif governance.get("approvals_unavailable"):
            summary.write("**Approvals unavailable:** the review history could not be read.\n\n")


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
    for name in (
        "APPROVAL_MODE",
        "APPROVAL_EXCEPTION_ID",
        "APPROVAL_ENVIRONMENTS",
        "APPROVAL_GUARD_RESULT",
        "APPROVE_RESULT",
        "GATE_OPENED_AT",
    ):
        normalized_environment[name.lower()] = os.environ.get(name, "")
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
    report = create_report(
        normalized_environment,
        end_time,
        deployment_results,
        collect_approvals(normalized_environment),
        planned_deployments,
    )
    output_path = Path(os.environ["REPORT_PATH"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    append_summary(report, Path(os.environ["GITHUB_STEP_SUMMARY"]))
    print(f"[STEP: PUBLISH-REPORT] Wrote run report: {output_path}")
    print("TODO: Set artifact retention from governance.retention_days.")


if __name__ == "__main__":
    main()
