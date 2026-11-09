# 5. Release Version 1.0.0 of the Workflow Package

* **Status:** Proposed
* **Date:** 2026-11-09

## Context
ADR 0003 releases the workflow package with canary and major floating aliases,
and left the 1.0.0 cut-over as deliberate future work. Until now, a guard in
the release workflow allowed only `v0` aliases, so every release was a 0.x
version. The settings contract and the standard pipeline are now ready for
service teams to adopt, and consumers need a stable major version to call.

## Decision
Release the workflow package as `1.0.0`:

- Set `packages/shared-workflows/VERSION` to `1.0.0`.
- Remove the release workflow's guard that allowed only `v0` aliases. The other
  release checks are unchanged: strict SemVer, no existing version tag and no
  downgrade.
- Releases from `1.0.0` use `v1` and `v1-canary`. The manual smoke-test
  workflow calls `v1-canary`.
- `v0` and `v0-canary` stay on the last 0.x release and are no longer moved.
  The floating-tags ruleset keeps protecting them.

## Consequences
Merging this change releases `1.0.0`: it creates `v1-canary`, then `v1.0.0`
and `v1` once the smoke test passes. Consumers on `@v0` stop receiving updates
and must change their caller to `@v1` (or an exact `@v1.x.y`). The app-template
caller already uses `@v1`. Future breaking changes to the workflow interface or
the settings contract need a new major version and their own ADR. Pre-release
version support remains future work.
