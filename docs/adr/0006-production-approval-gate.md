# 6. Production Approval Gate

* **Status:** Approved
* **Date:** 2026-11-16

## Context
Production deployments need a manual sign-off from the service's approver
groups. A plain GitHub Environment proceeds on one reviewer's approval, so it
cannot enforce `all-approvers` alone. Consumers pass no secrets and have one
caller workflow, and GitHub-hosted jobs cannot wait longer than six hours.

## Decision
- `all-approvers` (the default) uses one gated environment per approver group,
  `production-approval-<group>`, with the approval jobs running in parallel.
  Production runs only when every one succeeds.
- `single-approver` uses one environment, `production-approval`.
- `unattended` skips the pause and records the exception ID in the run record.
- The approval guard fails closed. If an approval environment is missing, has no
  required reviewers or cannot be read, the run fails before Production.
- Approvals expire after 24 hours. A newer run supersedes an older run that is
  still waiting, and an approval given more than 24 hours after the gate opened
  fails the leg.
- CHK-05 requires `governance.approvers` to include `service.owner_team`. The
  owner team stands in for the platform approver configuration until that
  exists.

## Consequences
Each consuming repository must create the approval environments with required
reviewers and grant `actions: read` to the caller. The run record shows each
approval, and a rejected or expired approval records Production as skipped. CHK-05
is stricter, but it implements the documented rule and no live consumer depends
on the old behaviour, so this is not a breaking change.
