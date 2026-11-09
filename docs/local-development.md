# Local development

Run commands in this guide from the repository root. See
[CONTRIBUTING.md](../CONTRIBUTING.md) for branch, commit and review rules.
Run `make help` to list local targets.

## Check settings

Install the checker's pinned dependencies and validate the sample settings
strictly, failing on any error or warning:

```bash
pip install -r packages/settings-checker/requirements.txt
make check-settings
```

Check a different file or repository:

```bash
make check-settings SETTINGS=tests/fixtures/settings/compliant.yml
make check-settings SETTINGS=tests/fixtures/settings/warnings-only.yml  # fails: --strict
python3 packages/settings-checker/checker.py ../my-service
```

Set `PYTHON=/path/to/python` to use a virtual environment. Paths are relative
to the repository root. See the
[settings checker reference](../packages/settings-checker/README.md) for
the contract, rules, modes and output formats.

## Run unit tests

With the checker's requirements installed, run:

```bash
python3 -m unittest discover -s tests
```

This covers the settings checker, deployment resolver and run-record structure.

## Run workflows with act

The workflow targets require [act](https://nektosact.com/) and a running Docker
daemon. They use `catthehacker/ubuntu:act-latest` by default. Run the standard
pipeline against the sample app and run the platform pre-gate with:

```bash
make test-standard-pipeline-local
make test-pregate-local
```

The first runs `standard-pipeline.yml` with an `act` `workflow_call` event and
the sample app's settings. Local runs use actions from this checkout; hosted
runs use the action references in the called workflow. Generated build files
and `run-record.json` are saved under the ignored `.act-artifacts/` directory.
The [consumer guide](consumer-guide.md) describes the pipeline's stages.

The run record's `context.workflow_package_version` is read from the executing
report action's workflow-package `VERSION` file, including for consumers using
a floating major alias. On local or unreleased runs it identifies the source
version and does not prove that version has been published.

Choose another compatible runner or provide a specific pull-request event for
the pre-gate:

```bash
make test-standard-pipeline-local ACT_RUNNER_IMAGE=catthehacker/ubuntu:act-latest
make test-pregate-local ACT_EVENT_FILE=/path/to/pull-request-event.json
```

The pre-gate otherwise generates pull-request metadata automatically. Use
`act -l` to list detected workflows and jobs.

### Failure and warning scenarios

Each failure target asserts a non-zero run and that the run record marks
downstream steps `SKIPPED`:

```bash
make test-pipeline-failing-test     # injected unit-test failure: test FAILED
make test-pipeline-failing-check    # missing settings file: check FAILED before the checker runs
make test-pipeline-settings-errors  # settings with an error: the checker fails check
```

The warning scenario asserts that Check, Test and Deploy pass for
`tests/fixtures/warnings-only-service/`:

```bash
make test-pipeline-settings-warnings
```

This shows that warnings don't stop a run. No later stage reads a field that
only has warning rules, so it doesn't test how stages handle malformed values.

### Pre-gate checks

The pre-gate validates the repository; the sample-app pipeline exercises the
workflow end to end. In addition to contribution rules for commits, branches,
PR titles and the ADR gate, the pre-gate:

- runs the unit tests;
- checks the sample app and app-template settings with `checker.py --strict`;
- checks every fixture in `tests/fixtures/settings/`: the compliant file passes
  with `--strict`, each file in `errors/` fails by default,
  `warnings-only.yml` passes by default and fails with `--strict`,
  `unparseable.yml` fails unless `--report-only` is used, and every file
  passes with `--report-only`.

Only hosted GitHub Actions runs can confirm pull-request and `main` behaviour,
including whether Production is skipped or included and whether artifacts are
uploaded. For the separate manual canary smoke test, see the
[release guide](workflow-release.md#canary-smoke-test).

## Git hooks

```bash
make install-hooks
```

This enables local branch-name and commit-message checks. Before committing,
review your changes with `git status` and `git diff --staged`.
