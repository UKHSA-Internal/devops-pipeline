# DevOps Pipeline (`devops-pipeline`)

Centralised pipeline standards, shared GitHub Actions workflows, compliance checking tools, and onboarding starter templates for UKHSA service teams.

## Repository structure

| Path | Purpose |
| --- | --- |
| `.github/` | Repository settings, GitHub workflow entrypoints, and pull request template |
| `packages/shared-workflows/` | Reusable workflow sources and composite actions, released together with root `.github/workflows/` as one workflow package |
| `packages/settings-checker/` | Source for the publishable `settings-checker` package |
| `packages/app-template/` | Starter configuration and workflow for adopting service repositories |
| `sample-app/` | Example microservice demonstrating the shared pipeline |
| `scripts/` | Repository-maintenance scripts, including contribution-rule validation used by hooks and CI |
| `tests/` | Automated tests and settings fixtures under `tests/fixtures/` |
| `docs/` | Architecture Decision Records and other repository documentation |

The shared workflow sources in `packages/shared-workflows/` are not an
independently published component. They are packaged and released with the
GitHub-discovered workflow entrypoints under `.github/workflows/`.

## Releasing the workflow package

The workflow package (root `.github/workflows/` and
`packages/shared-workflows/`) is released when a change to
`packages/shared-workflows/VERSION` reaches `main`. The version must be strict
SemVer (`MAJOR.MINOR.PATCH`): build metadata and pre-release suffixes are not
allowed, and an existing `vMAJOR.MINOR.PATCH` tag cannot be reused.

The workflow first publishes the canary alias by force-updating
`v<MAJOR>-canary` to the triggering commit. Before the deliberate 1.0.0
cut-over, the floating aliases are `v0` and `v0-canary`; `v1` and
`v1-canary` are not created before version `1.0.0`. The smoke-test, approval,
and stable-tag stages are deferred to a follow-up release-process change.

## Local development

Run `make help` to see the available local commands.

### Check settings

Check that the sample app's settings file is present and readable:

```bash
make check-settings
```

You can check either fixture as well:

```bash
make check-settings SETTINGS=tests/fixtures/valid-settings.yml
make check-settings SETTINGS=tests/fixtures/invalid-settings.yml
```

> **Current limitation:** this command checks file readability only. YAML
> parsing and schema validation are not implemented yet, so both fixtures can
> pass. Missing or unreadable files return a non-zero exit code. Paths are
> relative to the repository root.

### Run the standard pipeline locally

Run the reusable standard pipeline against the sample app's settings:

```bash
make test-standard-pipeline-local
```

The command runs `.github/workflows/standard-pipeline.yml` with `act`'s
`workflow_call` event and the sample app settings path. Under `act`, it uses
the actions in this checkout. Hosted runs load actions from the same commit as
the called workflow.

The sample caller, `.github/workflows/sample-app-pipeline.yml`, runs on pushes
to `main` and pull requests. Its pipeline:

- Runs the service test command from `service.test_command` in the settings
  file, from the service directory.
- Runs the placeholder scan and deploy steps.
- Builds a local image and records a run report. The full-commit-SHA image tag
  is passed unchanged to each deployment.
- Reads deployments from the settings file's `environments` list. Each
  category (Development, Pre-production, Production) can have multiple named
  deployments, run one at a time in settings order. Every deployment is
  followed by `verify-app` against `verification.health_endpoint`.

Check fails if a category has no deployments. Pull requests deploy to
Development only; Pre-production and Production deploy only on pushes to
`main`. To smoke-test the published workflow-package alias, manually run
`.github/workflows/smoke-test-pipeline.yml`.

Approval modes are `all-approvers` (default; every listed approval group must
approve), `single-approver` (any one listed group), and `unattended` (no
approver). The approval gate is managed separately from this workflow.

For `act` runs, generated build files and `run-record.json` are saved under the
ignored `.act-artifacts/` directory.

Two failure scenarios can be exercised locally; each asserts a non-zero run and
that the run record marks downstream steps `SKIPPED`:

```bash
make test-pipeline-failing-test   # injected unit-test failure: test FAILED
make test-pipeline-failing-check  # missing settings file: check FAILED
```

The run-record structure is covered by:

```bash
python3 -m unittest discover -s tests
```

Only hosted GitHub Actions runs can confirm pull-request and `main` behavior,
including whether Production is skipped or included and whether artifacts are
uploaded.

### Run the platform pre-gate locally

The pre-gate is a separate workflow; run it with:

```bash
make test-pregate-local
```

Both workflow targets require [act](https://nektosact.com/) and Docker with the
Docker daemon running. They use the smaller
`catthehacker/ubuntu:act-latest` image by default. To choose another compatible
runner:

```bash
make test-standard-pipeline-local ACT_RUNNER_IMAGE=catthehacker/ubuntu:act-latest
```

The pre-gate target generates pull-request metadata automatically. To use a
specific `act`-compatible event JSON file:

```bash
make test-pregate-local ACT_EVENT_FILE=/path/to/pull-request-event.json
```

To list detected workflows and jobs, run `act -l`. Verify remote GitHub
workflow behavior and permissions in a GitHub Actions run.

#### Platform checkout credential

The optional `platform_token` secret defaults to `GITHUB_TOKEN`. Consumers
should not need to set it and should not provide a long-lived token. The
orchestrator checks out this repository at the called workflow's own commit
SHA, so the workflow and its central composite actions are loaded atomically
from the same revision.

#### Pre-gate limitation: existence-only Check

The pre-gate validates the repository; the sample-app pipeline exercises the
workflow end to end. The pre-gate's settings self-test runs
`checker.py --strict` against `sample-app/.github/pipeline-settings.yml`.
Currently, Check only confirms that the settings file exists and is readable.
As a result:

- The self-test fails only if that file is missing or unreadable; it does not
  detect non-compliant settings. `tests/fixtures/invalid-settings.yml` passes
  the checker and is not checked by the pre-gate.
- `--strict` remains for compatibility but has no effect.
- The pre-gate still enforces contribution rules for commits, branches, PR
  titles, and the ADR gate.

Settings enforcement will return when schema validation is implemented in the
settings checker story.

### Git hooks

```bash
make install-hooks
```

This enables local branch-name and commit-message checks. Before committing,
review your changes:

```bash
git status
git diff --staged
```

## Branch and commit conventions

Create a branch with `<type>/<JIRA-ticket>/<short-description>`, for example:

```text
feature/DP-146/initial-monorepo-scaffold
```

Use Conventional Commit messages in the form
`<type>(<scope>): <short description>`, for example:

```text
feat(checker): validate pipeline settings
```

Allowed commit types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.

Allowed scopes: `workflows`, `checker`, `app-template`, `sample-app`,
`fixtures`, `docs`, `repo`, `deps`.

Include the Jira key in the PR title. If the branch has no Jira ID, include
the key in either the PR title or a commit message.

Mark breaking changes with `!` after the scope or a `BREAKING CHANGE:` footer.
Breaking PRs require either a new ADR under `docs/adr/` or a reference to an
ADR already on `main`.
