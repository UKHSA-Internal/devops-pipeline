# 4. Settings Validation in the Settings Checker

* **Status:** Proposed
* **Date:** 2026-11-09

## Context
Every consuming service describes itself in `.github/pipeline-settings.yml`.
Before DP-173 the settings checker only confirmed that the file could be read,
and some rules (environment fields, categories, `service.test_command`) were
enforced by the `resolve-deployments` action instead. Rules were split across
actions, had no IDs or severities, and could not be run as a readiness report.

A first design used JSON Schema with custom annotations to attach rule IDs and
severities. It needed code to map each schema error back to its rule, and one
rule could be spread across the schema, the checker and several docs. That made
rules hard to change.

## Decision
All settings validation lives in `packages/settings-checker/`:

- `rules.py` holds every rule as a plain Python function, grouped by settings
  section. Each rule carries its ID (`CHK-01` to `CHK-12`, from the low-level
  design) and its severity, Error or Warning, next to its messages. There is no
  JSON Schema.
- `checker.py` takes a repository folder (or `--settings FILE`), applies the
  rules and reports each problem as its field and a plain message, with the
  rule ID in brackets. It writes `text`, `json` or `markdown`.
- Exit codes depend on the mode: by default errors fail, `--strict` also fails
  on warnings, and `--report-only` always exits 0. A missing or unparseable
  settings file is reported as an error.
- The same tool is a standalone onboarding readiness check and the Check stage
  of the pipeline. The Check stage runs it in the default mode, before any
  other action reads the settings, and adds the markdown report to the job
  summary. Other actions, such as `resolve-deployments`, read already-checked
  settings and do not check them again.
- `shared_workflow_ref` is no longer part of the contract, and
  `deploy.production.approval_mode` is required, with the values
  `all-approvers`, `single-approver` and `unattended`.

## Consequences
A rule is changed in one place, `rules.py`, with its test cases, a row in the
checker README's rules table and, for an error rule, a fixture under
`tests/fixtures/settings/errors/`. Settings that previously passed now fail
Check if `governance.approvers` is empty or `deploy.production.approval_mode`
is missing; adopting services must add them. A malformed
`verification.health_endpoint` or `timeout_seconds` is an error (`CHK-07`), so
the verify step only reads checked values. Warnings (`CHK-01`, `CHK-02`,
`CHK-06`, `CHK-12`) do not fail a pipeline run, so actions that read those
fields must tolerate malformed values. The checker depends only on the pinned
`pyyaml` version in `packages/settings-checker/requirements.txt`. Other
repository readiness checks, such as the caller workflow or Dockerfile, are
separate work.
