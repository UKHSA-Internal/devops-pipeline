"""Read the Production approval history of a workflow run for the run record."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

API = "https://api.github.com"
RETRIES = 3
TIME_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# standard-pipeline.yml names its approval jobs with this template, where
# ${{ matrix.approval.environment }} takes the place of {environment}. A test keeps them equal.
APPROVAL_JOB_NAME = "Approve Production ({environment})"


class ApprovalsUnavailable(Exception):
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
    failure = "unknown error"
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(http_request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code in (401, 403, 404):
                raise ApprovalsUnavailable(f"the token cannot read the run's approvals (HTTP {error.code})") from error
            failure = f"HTTP {error.code}"
        except (urllib.error.URLError, TimeoutError) as error:
            failure = str(error)
        if attempt < RETRIES:
            time.sleep(2**attempt)
    raise ApprovalsUnavailable(f"could not read the run's approvals after {RETRIES} attempts ({failure})")


def fetch_reviews(repository: str, run_id: str, token: str, get=request) -> list[dict]:
    """Return the run's review history. The API has no per-attempt form, so this covers every attempt."""
    return get(f"{API}/repos/{quote(repository, safe='/')}/actions/runs/{run_id}/approvals", token)


def fetch_jobs(repository: str, run_id: str, attempt: str, token: str, get=request) -> list[dict]:
    """Return the jobs of one run attempt."""
    jobs = []
    page = 1
    while True:
        body = get(
            f"{API}/repos/{quote(repository, safe='/')}/actions/runs/{run_id}/attempts/{attempt}/jobs"
            f"?per_page=100&page={page}",
            token,
        )
        batch = body.get("jobs", [])
        jobs.extend(batch)
        if len(batch) < 100:
            return jobs
        page += 1


def find_job(jobs: list[dict], environment: str) -> dict | None:
    """Find the approval job for an environment; a reusable workflow prefixes the caller job's name."""
    name = APPROVAL_JOB_NAME.format(environment=environment)
    for job in jobs:
        job_name = job.get("name") or ""
        if job_name == name or job_name.endswith(f" / {name}"):
            return job
    return None


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, TIME_FORMAT).replace(tzinfo=timezone.utc)


def decide(state: str, started_at: str | None, gate_opened_at: str, window_hours: float) -> str | None:
    """Return approved, rejected or expired for one review, or None for an unfinished one.

    Expired means the leg started more than the window after the gate opened, or that there is
    no start time to measure (an approval that cannot be tied to a job is not trusted). An
    approved leg that failed for any other reason is still approved.
    """
    if state == "rejected":
        return "rejected"
    if state != "approved":
        return None
    if not started_at:
        return "expired"
    if gate_opened_at:
        try:
            if parse_time(started_at) - parse_time(gate_opened_at) > timedelta(hours=window_hours):
                return "expired"
        except ValueError:
            pass
    return "approved"


def build_approvers(
    plan: list[dict],
    reviews: list[dict],
    jobs: list[dict],
    gate_opened_at: str,
    window_hours: float,
) -> list[dict]:
    """Return one entry per approval decision, in the plan's environment order.

    The timestamp is the time the approval leg started (it only starts once approved), or for a
    rejection the time its job ended, because the review history has no timestamps.
    """
    approvers = []
    for item in plan:
        environment = item["environment"]
        job = find_job(jobs, environment)
        for review in reviews:
            names = {entry.get("name", "").lower() for entry in review.get("environments") or []}
            if environment.lower() not in names:
                continue
            state = review.get("state")
            started_at = (job or {}).get("started_at")
            decision = decide(state, started_at, gate_opened_at, window_hours)
            if decision is None:
                continue
            timestamp = (job or {}).get("completed_at") if decision == "rejected" else started_at
            approvers.append(
                {
                    "environment": environment,
                    "groups": item["groups"],
                    "approver": (review.get("user") or {}).get("login"),
                    "decision": decision,
                    "timestamp": timestamp,
                }
            )
    return approvers
