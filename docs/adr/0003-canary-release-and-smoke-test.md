# 3. Canary-Based Workflow Package Releases

* **Status:** Approved
* **Date:** 2026-11-06

## Context
The reusable workflow entrypoints in `.github/workflows/` and composite actions
in `packages/shared-workflows/` form one runtime unit. Releasing them
independently could make a consumer run a workflow with incompatible action
implementations. Consumers also cannot rely on their default token to check out
the private platform repository at runtime.

## Decision
Release the workflow package from `packages/shared-workflows/VERSION` when that
file changes on `main`. Require a strict stable SemVer version, reject an
existing version tag and a downgrade, and serialize releases. Pull requests run
a dry run that reports the planned release and does not move tags. Before the
deliberate 1.0.0 cut-over, use only `v0` and `v0-canary` as floating aliases.

For a release, pin the standard workflow's relative composite-action references
to the release commit, creating a derived commit that contains the workflow and
its actions at one revision. Force-move the canary alias to that pinned commit
first. Run the sample-app pipeline as the release smoke test, then verify the
canary still points to the pinned commit before creating the version tag and
force-moving the major alias. Version tags are not forced; promotion is
idempotent when the version tag already points to the same pinned commit.

Consumers call literal workflow refs and receive the pinned composite actions
without a runtime checkout token. This requires the platform repository's
Actions access to be available at the organisation level. A separate manual
smoke-test workflow calls the published `v0-canary` alias.

## Consequences
The workflow package has an immutable version reference for each release and a
floating canary that can be tested before promotion. A failed smoke test blocks
promotion, though the canary remains available for diagnosis. Changes to
workflow entrypoints and shared actions must be reviewed as one release unit.
The 1.0.0 alias cut-over and pre-release version support remain deliberate
future work.
