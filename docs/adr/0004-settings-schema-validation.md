# 4. Settings Validation in the Settings Checker

* **Status:** Proposed
* **Date:** 2026-11-06

## Context
Every consuming service describes itself in `.github/pipeline-settings.yml`.
Before DP-173 the settings checker only confirmed that the file could be read,
and some rules (environment fields, categories, `service.test_command`) were
enforced by the `resolve-deployments` action instead. Rules were split across
actions, had no IDs or severities, and could not be run as a scheduled audit.

## Decision
All settings validation lives in `packages/settings-checker/`, defined once:

- `settings.schema.json` (JSON Schema 2020-12) is the source of truth for
  field types and structure. Each property names the rule (`x-rule`) that
  reports its violations.
- `checker.py` holds the rule table (`CHK-01` to `CHK-11`) and each rule's
  severity, and checks the cross-field rules: unique environment names
  (`CHK-03`), every category mapped (`CHK-04`) and the unattended
  `exception_id` (`CHK-10`).
- Exit codes depend on mode: `--mode pr` fails on Blocking violations,
  `--mode pr --strict` fails on any violation, and `--mode audit` always
  passes. A file that cannot be parsed fails in every mode.
- The Check stage runs the checker in `pr` mode before any other action reads
  the settings. Other actions, such as `resolve-deployments`, read
  already-validated settings and do not validate them again.
- `shared_workflow_ref` is no longer part of the contract, and
  `deploy.production.approval_mode` is required, with the values
  `all-approvers`, `single-approver` and `unattended`.

## Consequences
New rules are added in one place, with a fixture under `tests/fixtures/settings/`
and unit tests. Settings that previously passed now fail Check if
`governance.approvers` is empty or `deploy.production.approval_mode` is
missing; adopting services must add them. Advisory rules (`CHK-01`, `CHK-02`, `CHK-06`, `CHK-07`) do not block a
pipeline run, so actions that read those fields must tolerate malformed values.
The checker and Check stage depend on the pinned `jsonschema` and `pyyaml`
versions in `packages/settings-checker/requirements.txt`.
