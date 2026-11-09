# Settings Checker

Checks a repository's `.github/pipeline-settings.yml` and reports whether it is
ready to onboard to the shared pipeline. Point it at a repository on your
machine to see what needs fixing before onboarding. The Check stage of the
standard pipeline runs the same tool on every pipeline run.

- `rules.py` holds every rule, grouped by settings section. Each rule has an
  ID, a severity (Error or Warning) and plain messages.
- `checker.py` reads the settings file, applies the rules, sets the exit code
  and writes the report.

## Usage

```bash
pip install -r packages/settings-checker/requirements.txt
python3 packages/settings-checker/checker.py [REPOSITORY] [--settings FILE] [--strict | --report-only] [--format text|json|markdown]
```

- `REPOSITORY` is the repository folder to check. It defaults to the current
  folder, and the checker reads `REPOSITORY/.github/pipeline-settings.yml`.
- `--settings FILE` checks that file instead.

For example:

```bash
python3 packages/settings-checker/checker.py ../my-service
python3 packages/settings-checker/checker.py --settings tests/fixtures/settings/warnings-only.yml --strict
```

### Modes

| Mode | Used by | Exits 1 when |
| --- | --- | --- |
| Default | Every pipeline run | Any error |
| `--strict` | Pre-gate and local runs | Any error or warning |
| `--report-only` | Readiness reports | Never; reports everything |

A settings file that is missing, cannot be parsed, or is not a YAML mapping is
reported as an error. It fails in the default and `--strict` modes.

### Output

`--format` chooses the output. `text` (the default) is for people:

```text
Settings file: .github/pipeline-settings.yml
Not ready: 1 error, 1 warning

✗ service.test_command – must be a single line, not empty (CHK-11)
! governance.retention_days – must be a whole number greater than zero (CHK-06)
```

`✗` marks an error and `!` a warning. The settings are **Ready** when there are
no errors; warnings don't stop onboarding.

`markdown` writes the same report as a table; the Check stage adds it to the
job summary. `json` is for scripts:

```json
{
  "settings_file": ".github/pipeline-settings.yml",
  "ready": false,
  "exit_code": 1,
  "summary": { "errors": 1, "warnings": 0 },
  "problems": [
    {
      "field": "service.test_command",
      "severity": "Error",
      "message": "must be a single line, not empty",
      "rule": "CHK-11"
    }
  ]
}
```

A problem with the file itself has the file path as its `field`, and `rule` is
`null`.

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
| CHK-01 | `version` is present and a string | Warning |
| CHK-02 | `service.name`, `owner_team` and `language` are present | Warning |
| CHK-03 | Each environment has `name`, `category`, `account_id`, `role_name` and `region`, and `category` is valid. Names must be unique and contain only letters, numbers, `.`, `_` and `-` | Error |
| CHK-04 | Every category (Development, Pre-production, Production) has at least one environment | Error |
| CHK-05 | `governance.approvers` is a non-empty list | Error |
| CHK-06 | `governance.retention_days` is an integer greater than zero | Warning |
| CHK-07 | `health_endpoint`, if set, is a valid path; `timeout_seconds`, if set, is an integer greater than zero; `db_check_required` is an explicit boolean | Warning |
| CHK-08 | Each custom check has a non-empty `name` and `command`, and an explicit boolean `allow_failure` | Error |
| CHK-09 | `deploy.production.approval_mode` is `all-approvers`, `single-approver` or `unattended` | Error |
| CHK-10 | When `approval_mode` is `unattended`, `exception_id` is non-empty | Error |
| CHK-11 | `service.test_command` is a non-empty, single-line string | Error |

TODO (CHK-05): also check that each approver group exists in the platform
approver config, once that config exists.

## Changing a rule

1. Edit the rule in `rules.py`, or add a new function with an `@rule` ID and
   severity.
2. Add failing and passing cases for it in `tests/test_settings_checker.py`.
3. Update the rules table above.
4. For a new error rule, add a fixture in `tests/fixtures/settings/errors/`,
   named after the problem, and add its expected rule ID to
   `EXPECTED_FIXTURE_RULES` in the test.

## Fixtures and tests

`tests/fixtures/settings/` holds:

- `compliant.yml`: no errors or warnings;
- `warnings-only.yml`: warnings only;
- `unparseable.yml`: invalid YAML;
- `errors/`: one file per error rule, named after its problem (for example
  `missing-test-command.yml`). A unit test checks that each one reports only
  its expected rule.

The pre-gate runs the checker against each of them. Unit tests:

```bash
python3 -m unittest discover -s tests
```
