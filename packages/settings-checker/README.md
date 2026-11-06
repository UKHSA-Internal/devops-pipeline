# Settings Checker

Validates a service's `.github/pipeline-settings.yml` against the pipeline
settings contract. The Check stage of the standard pipeline runs it on every
pipeline run.

- `settings.schema.json` defines field types and structure. Each property names
  the rule (`x-rule`) that reports its violations.
- `checker.py` defines each rule's severity and checks the cross-field rules
  (unique environment names, `CHK-04` and `CHK-10`).

## Usage

```bash
pip install -r packages/settings-checker/requirements.txt
python3 packages/settings-checker/checker.py --config <path> [--mode pr|audit] [--strict]
```

`--config` defaults to `.github/pipeline-settings.yml`.

| Mode | Used by | Exits 1 when |
| --- | --- | --- |
| `--mode pr` (default) | Every pipeline run | Any Blocking violation |
| `--mode pr --strict` | Pre-gate and local runs | Any violation |
| `--mode audit` | Scheduled scans | Never; reports everything |

A file that is missing, cannot be parsed, or is not a YAML mapping exits 1 in
every mode.

The JSON summary is written to stdout; progress messages go to stderr. Each
violation lists its rule ID, severity, field path and message:

```json
{
  "file_checked": ".github/pipeline-settings.yml",
  "mode": "pr",
  "strict": false,
  "status": "NON_COMPLIANT",
  "exit_code": 1,
  "summary": { "blocking": 1, "advisory": 0 },
  "violations": [
    {
      "rule": "CHK-11",
      "severity": "Blocking",
      "path": "service.test_command",
      "message": "service.test_command must be a non-empty, single-line string"
    }
  ]
}
```

`status` is `COMPLIANT`, `NON_COMPLIANT` or `ERROR` (unparseable file, with an
`error` message instead of `violations`).

## Settings contract

```yaml
version: "1.0"                     # string, required
service:
  name: "my-service"               # required
  owner_team: "my-team"            # required
  language: "python"               # required
  test_command: "make test"        # non-empty, single line, required
environments:                      # required; each entry needs every field
  - name: dev-env-1                # letters, numbers, '.', '_', '-'; unique
    category: Development          # Development | Pre-production | Production
    account_id: "123456789012"
    role_name: pipeline-dev-role
    region: eu-west-2
governance:
  retention_days: 30               # integer > 0, required
  approvers:                       # non-empty list of approver group names, required
    - "platform-leads"
verification:
  health_endpoint: "/health"       # optional, default /health
  timeout_seconds: 60              # optional, default 60
  db_check_required: false         # required, explicit boolean
  custom_checks:                   # optional
    - name: "smoke"                # non-empty
      command: "./smoke.sh"        # non-empty
      timeout_seconds: 30          # optional integer
      allow_failure: false         # required, explicit boolean
deploy:
  production:
    approval_mode: all-approvers   # all-approvers | single-approver | unattended
    exception_id: "EXC-0001"       # required only when approval_mode is unattended
```

## Rules

| ID | Rule | Severity |
| --- | --- | --- |
| CHK-01 | `version` is present and a string | Advisory |
| CHK-02 | `service.name`, `owner_team` and `language` are present | Advisory |
| CHK-03 | Each environment has `name`, `category`, `account_id`, `role_name` and `region`, and `category` is valid. Names must be unique and contain only letters, numbers, `.`, `_` and `-` | Blocking |
| CHK-04 | Every category (Development, Pre-production, Production) is mapped at least once | Blocking |
| CHK-05 | `governance.approvers` is a non-empty list | Blocking |
| CHK-06 | `governance.retention_days` is an integer greater than zero | Advisory |
| CHK-07 | `health_endpoint`, if set, is a valid path; `timeout_seconds`, if set, is an integer greater than zero; `db_check_required` is an explicit boolean | Advisory |
| CHK-08 | Each custom check has a non-empty `name` and `command`, and an explicit boolean `allow_failure` | Blocking |
| CHK-09 | `deploy.production.approval_mode` is `all-approvers`, `single-approver` or `unattended` | Blocking |
| CHK-10 | When `approval_mode` is `unattended`, `exception_id` is non-empty | Blocking |
| CHK-11 | `service.test_command` is a non-empty, single-line string | Blocking |

TODO (CHK-05): also check that each approver group exists in the platform
approver config, once that config exists.

## Fixtures and tests

`tests/fixtures/settings/` holds a compliant file, one file per Blocking rule
(`blocking-chk-NN.yml`), an advisory-only file and an unparseable file. The
pre-gate runs the checker against each of them. Unit tests:

```bash
python3 -m unittest discover -s tests
```
