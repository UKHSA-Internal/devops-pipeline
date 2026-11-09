# 2. Reusable Workflow and Composite Action Scaffold

* **Status:** Approved
* **Date:** 2026-11-06

## Context
Service repositories need a consistent CI/CD pipeline without copying its
implementation into every consumer. Pipeline settings provide service-specific
inputs, while the platform repository needs to evolve shared stages and actions
centrally.

## Decision
Expose the standard pipeline as a reusable GitHub Actions workflow. It accepts
the caller's settings path and orchestrates the shared Check, Test, Scan, Build,
Deploy and run-report stages. Implement reusable stage logic as composite
actions under `packages/shared-workflows/actions/`; keep the workflow entrypoint
under `.github/workflows/` so GitHub can call it directly.

Use job dependencies to enforce the pipeline gates: checks and tests precede
later work, and deployment stages follow the successful build and preceding
environment. Resolve deployments from the caller's settings rather than
hard-coding service-specific targets into the shared workflow.

On the platform repository's own main and pull-request runs, reference composite
actions by relative path. This lets local validation exercise the workflow and
actions from the same checkout.

## Consequences
Consumers share one pipeline implementation while supplying their own settings
and application code. Workflow entrypoints and composite actions must be
maintained and released together; the workflow package release decision is
recorded in [ADR 0003](./0003-canary-release-and-smoke-test.md). Local
validation can use `act` with the repository checkout and sample app.
