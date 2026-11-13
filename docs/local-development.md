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

### Test runtime scenarios

The Test stage sets up a runtime from `service.language` before running the
test command. These targets cover the supported languages and the two
fallbacks:

```bash
make test-pipeline-node                    # node: set up from .nvmrc, every stage passes
make test-pipeline-missing-version-file    # python with no .python-version: test FAILED, downstream SKIPPED
make test-pipeline-unsupported-language    # unsupported language: no runtime, warning, test still runs
make test-pipeline-pinned-python-version   # python pinned to a specific minor version via .python-version: test PASSED
```

The python path is already covered by `make test-standard-pipeline-local`,
which runs the sample app with its `.python-version`. The
[consumer guide](consumer-guide.md#test-runtime) lists the accepted languages
and version files.

`test-pipeline-pinned-python-version` covers a service pinned to a specific
minor version (3.12) that isn't just whatever `python3` happens to resolve to
on the runner image, using `tests/fixtures/pinned-python-version/`. This
proves `actions/setup-python` installs the exact requested version from
`.python-version` and that the test command then runs successfully against
it, rather than failing because only a different python version was
preinstalled on the bare runner.

#### Apple Silicon

`.actrc` forces `--container-architecture linux/amd64` to match GitHub's x86
runners. On Apple Silicon this breaks every target that sets up a python
runtime, because `act` rewrites `PATH` to an `arm64` toolcache directory that
the amd64 image doesn't have, and `setup-python`'s post step then fails with
`node: executable file not found in $PATH`. Override the architecture to run
those targets, changing `settings_path` for each one:

```bash
./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml \
  --input settings_path=sample-app/.github/pipeline-settings.yml \
  -P ubuntu-latest=catthehacker/ubuntu:act-latest \
  --container-architecture linux/arm64
```

This affects `make test-standard-pipeline-local`,
`make test-pipeline-failing-test`, `make test-pipeline-settings-warnings` and
`make test-pipeline-pinned-python-version`. Hosted runs are unaffected.

### Pre-gate checks

The pre-gate validates the repository; the sample-app pipeline exercises the
workflow end to end. In addition to contribution rules for commits, branches,
PR titles and the ADR gate, the pre-gate:

- runs the unit tests;
- checks the sample app's settings with `checker.py --strict`, expecting no
  problems;
- checks the app-template's settings with `checker.py --strict`, expecting
  exactly the CHK-03 (malformed `account_id`) and CHK-13 (unreplaced
  placeholder text) problems the unedited template is meant to report — the
  template keeps its placeholders on purpose, so it must never silently pass;
- checks every fixture in `tests/fixtures/settings/`: the compliant file passes
  with `--strict`, each file in `errors/` fails by default,
  `warnings-only.yml` passes by default and fails with `--strict`,
  `unparseable.yml` fails unless `--report-only` is used, and every file
  passes with `--report-only`.

Only hosted GitHub Actions runs can confirm pull-request and `main` behaviour,
including whether Production is skipped or included and whether artifacts are
uploaded. For the separate manual canary smoke test, see the
[release guide](workflow-release.md#canary-smoke-test).

## Testing as a consumer

Tests in this repository run the pipeline from inside the platform repository.
The canary smoke test goes furthest: `smoke-test-pipeline.yml` calls the
published `v<MAJOR>-canary` by full reference, so it does validate a release
the way a consumer resolves it, through pinned action references. It still
runs inside this repository, so it can't prove that a separate repository,
using only its own default `GITHUB_TOKEN`, can call `standard-pipeline.yml`.

The [devops-pipeline-sandbox](https://github.com/UKHSA-Internal/devops-pipeline-sandbox)
repository covers that gap. It calls the published workflow across a range of
settings scenarios using only the default `GITHUB_TOKEN`.

Run it:

- after every release, against the new tag, to confirm consumers get the
  released version;
- when changing anything a consumer depends on: the workflow interface, the
  settings contract, or how actions are referenced.

Use the sandbox's Actions tab and choose a scenario workflow. Unreleased
changes can't be tested by pointing the sandbox at a normal branch; the
sandbox README explains how to test them.

## Git hooks

```bash
make install-hooks
```

This enables local branch-name and commit-message checks. Before committing,
review your changes with `git status` and `git diff --staged`.
