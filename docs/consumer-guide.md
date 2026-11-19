# Using the shared pipeline

This guide is for service teams adopting the pipeline. For the settings
contract, rules and checker options, see the
[settings checker reference](../packages/settings-checker/README.md).

## Prerequisites

The platform repository's Actions access must be set to organisation level
(Settings, Actions, General, Access). GitHub can then fetch the release's
pinned composite actions for consumers without a separate checkout token.

Use the floating major tag (`@v1`) for automatic updates, or an exact version
tag (for example `@v1.0.0`) for a fixed release. `@v0` stays on the last 0.x
release and no longer receives updates; callers on `@v0` should move to `@v1`.

## Add a caller

Create `.github/workflows/pipeline.yml` in the service repository. See the
[tested example caller](examples/caller-workflow.yml) for a complete file,
including the `contents: read` and `id-token: write` permissions Deploy needs
for OIDC and the optional `settings_path` input.

The [app-template caller](../packages/app-template/.github/workflows/pipeline.yml)
uses the same `uses:` reference. The workflow reference must be literal.

## Configure the service

Start with the [app-template settings](../packages/app-template/.github/pipeline-settings.yml)
at `.github/pipeline-settings.yml`. Replace placeholder service information,
accounts, roles and approvers with the service's values. Provide at least one
environment in each of Development, Pre-production and Production.

The Check stage flags unreplaced placeholders and malformed account IDs, so
copying the template without editing it does not pass unnoticed: each
`account_id` must be the service's real 12-digit account ID, not all zeros
(CHK-03), and no field may still contain `replace-with-` or `TODO` text
(CHK-13, a warning).

`service.test_command` must be a non-empty, single-line command. The template's
`python3 -m unittest discover -s tests -v` runs a placeholder test: replace the
placeholder with the service's real tests. The
[sample app](../sample-app/README.md) shows a working example.

### Structured tests (contract 1.1)

For more than one command, use a `service.test` block instead of
`test_command` (set exactly one of them). `test_command` stays valid: it is
shorthand for one suite named `test`, with no setup, cache or final step.

```yaml
version: "1.1"

service:
  test:
    setup: "python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    cache:
      paths: [".venv"]
      key_files: ["requirements*.txt", ".python-version"]
    suites:
      - name: unit
        command: ".venv/bin/python -m pytest tests/unit --junitxml=test-results/unit.xml"
      - name: api
        command: ".venv/bin/python -m pytest tests/api --junitxml=test-results/api.xml"
    collect: [".coverage.*"]
    final:
      name: coverage
      command: ".venv/bin/python -m coverage combine && .venv/bin/python -m coverage report"
```

- **Suites** (1 to 10) always run in parallel, each as its own "Test (name)"
  job. To run commands in order, chain them in one suite.
- **Setup and cache.** With `cache`, a "Test setup" job runs `setup` once and
  saves the cache, and every suite restores it. On a miss, they run `setup`
  themselves. Without `cache`, each suite runs `setup` first. Cache `paths`,
  `key_files` and `collect` are relative to the service directory and can't
  contain `..`. The key covers the OS, architecture, language version, the
  `setup` command and the `key_files`.
- **Collect and final.** Each suite uploads the `collect` files. The `final`
  step runs only if every suite passed, with all of them downloaded into the
  service directory, so it can combine coverage without running tests again.
- **Reports.** Write JUnit XML to `test-results/*.xml`. Each suite's job
  summary shows its tests, failures, errors and duration; without XML only the
  result is shown.
- **One result.** The Test stage passes only if every suite and the final step
  pass. The run record's `steps.test` keeps that meaning, and `test_suites`
  lists each suite and the final step. A step that never ran is `SKIPPED`.

Every command is a single line. The checker rules are CHK-20 to CHK-24 in the
[checker reference](../packages/settings-checker/README.md). See the
[tested example](examples/pipeline-settings.yml) and the
[decision record](adr/0008-structured-test-settings.md).

### Test runtime

The Test stage sets up a language runtime before running `test_command` (or each suite, and the setup), based
on `service.language`. The runner has no particular version pre-installed, so
the service must declare the version it needs:

| `service.language` | Version file in the service directory | Runtime |
| --- | --- | --- |
| `python` | `.python-version` | `actions/setup-python` |
| `node` | `.nvmrc`, or `.node-version` | `actions/setup-node` |

`python` and `node` are the only accepted values. Matching ignores case and
surrounding whitespace. If the language is `python` or `node` and its version
file is missing, the Test stage fails and names the file to add. Any other
value, or no value at all, sets up no runtime: the Test stage logs a warning
and runs `test_command` on the runner as it is, so the command must rely only
on what the runner already provides.

The workflow uses `.github/pipeline-settings.yml` by default. For a service in a
subdirectory, set the reusable workflow's `settings_path` input to its settings
file. If no input or root settings file is present, the workflow accepts exactly
one `*/.github/pipeline-settings.yml` file. The test command runs from the
service directory.

Check settings locally before onboarding:

```bash
pip install -r packages/settings-checker/requirements.txt
python3 packages/settings-checker/checker.py ../my-service
```

Run these commands from a checkout of this platform repository. The checker
reports errors and warnings; its default mode fails on errors. Use `--strict`
to fail on warnings too. See the [checker reference](../packages/settings-checker/README.md)
for the complete contract and options.

## What the pipeline does

The Check stage validates settings, then the pipeline sets up the service's
language runtime and runs the configured tests (`test_command`, or the suites
of a `test` block) and the placeholder scan.
Pushes additionally build, deploy and verify the service; pull requests stop
after Scan, so they never build an image or deploy. It records a run report
and passes the full-commit-SHA image tag to each deployment. Deployments
within each category run one at a time in settings order. Pushes deploy to
Development; Pre-production and Production run only on pushes to `main`.

<!-- TODO: Pull requests may deploy to an ephemeral environment in future. -->

`deploy.production.approval_mode` is required: `all-approvers`,
`single-approver` or `unattended`. The last requires
`deploy.production.exception_id`. The approval gate is managed separately
from this workflow.

For local development and limitations of the sample pipeline, see
[local development](local-development.md).
