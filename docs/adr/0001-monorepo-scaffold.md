# 1. Monorepo Workspace Scaffold

* **Status:** Approved
* **Date:** 2026-10-30

## Context
A central monorepo is required to house shared pipeline workflows, governance validation tools, reference starter templates, and test fixtures.

## Decision
Structure the workspace as a single monorepo. Independently consumable components
are organized under `./packages/`: `./packages/setting-checker` for standards
validation and `./packages/app-template` for adopting service repositories.
Their publishable package names are `settings-checker` and `app-template`.
`./packages/shared-workflows` contains reusable workflow sources and composite
actions, but is released only as part of the broader workflow package together
with GitHub-discovered entrypoints under the root `./.github/workflows/`; it is
not an independently published package. Keep repository-maintenance scripts in
`./scripts`, the reference implementation in `./sample-app`, tests and fixtures
in `./tests`, and architecture records in `./docs/adr`.

## Consequences
Enables isolated component development and component-prefixed tagging (e.g.,
`settings-checker/v1.0.0`) without third-party monorepo tools. Directory names
describe each component's role while commit scopes remain those defined in
`CONTRIBUTING.md`. Workflow entrypoints remain in the root `.github/workflows/`
so GitHub discovers them, while their shared sources are shipped in the same
workflow release.
