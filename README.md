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

## Local development

Run `make help` to see the available local commands.

### Check settings and test the standard pipeline

Confirm that the sample app's application-specific settings file is present
and readable:

```bash
make check-settings
```

The same command can check either fixture file:

```bash
make check-settings SETTINGS=tests/fixtures/valid-settings.yml
make check-settings SETTINGS=tests/fixtures/invalid-settings.yml
```

The local settings command currently performs only a file readability smoke
check. Both fixtures can pass because YAML parsing and schema validation have
not been implemented yet. A missing or unreadable file returns a non-zero exit
code. Paths are relative to the repository root.

Test the **reusable standard pipeline** against the local composite action and
the sample app's settings file:

```bash
make test-standard-pipeline-local
```

This invokes `.github/workflows/standard-pipeline.yml` directly with `act`'s
`workflow_call` event and passes the sample app settings path. Under `act`, the
reusable workflow automatically uses the actions in this checkout; hosted runs
load the actions from the same commit as the called workflow. The
`.github/workflows/sample-app-pipeline.yml` caller also uses the reusable
workflow and action from this checkout, running on pushes to `main` and pull
requests. The full flow runs the service's real test command (`service.test_command`
in the settings file, run from the service directory), placeholder scan and deploy
steps, a local image build, and a run report. The build's full-commit-SHA image tag is
passed unchanged to each deployment. Deployments come from the `environments`
list in the settings file: each category (Development, Pre-production, Production) can
contain several named deployments, which run one at a time in settings order.
Each deployment is followed immediately by the `verify-app` action against its
health endpoint (`verification.health_endpoint`). Check fails if a category has
no deployments. Pull request runs deploy to Dev only; Pre-production and
Production deploy only on pushes to `main`. To smoke-test the published `v1`
release instead, manually run `.github/workflows/smoke-test-pipeline.yml`.
Approval mode identifiers are `all-approvers` (standard) and `single-approver`
(fast-track). The approval gate is managed separately from this workflow.
For `act` runs, generated build files and `run-record.json` are persisted under
the ignored `.act-artifacts/` directory.

Two failure scenarios can be exercised locally; each asserts a non-zero run and
that the run record marks downstream steps `SKIPPED`:

```bash
make test-pipeline-failing-test   # injected unit-test failure: test FAILED
make test-pipeline-failing-check  # missing settings file: check FAILED
```

The run-record structure is covered by `python3 -m unittest discover -s tests`.
Pull-request and `main` behaviour (Production skipped or included, artifact
upload) can only be confirmed in hosted GitHub Actions runs.

### Run the platform pre-gate locally

The pre-gate is a separate workflow; run it with:

```bash
make test-pregate-local
```

Both workflow targets require [act](https://nektosact.com/) and Docker, with the
Docker daemon running. They default to the smaller `catthehacker/ubuntu:act-latest`
image. Override it if you need a different compatible runner:

```bash
make test-standard-pipeline-local ACT_RUNNER_IMAGE=catthehacker/ubuntu:act-latest
```

The pre-gate target generates local pull-request metadata automatically. To use
a specific `act`-compatible pull-request event JSON instead, pass:

```bash
make test-pregate-local ACT_EVENT_FILE=/path/to/pull-request-event.json
```

To list detected workflows and jobs, run `act -l`. For GitHub's remote workflow
behavior and permissions, also verify the workflow in a GitHub Actions run.

#### Platform checkout credential

When a service repository calls the orchestrator, its job checks out this
repository to load the central composite actions. The caller's default
`GITHUB_TOKEN` cannot read another internal repository, so callers must supply a
least-privilege, read-only (contents) credential for this repository as the
optional `platform_token` secret. `secrets: inherit` passes it through if the
caller defines a secret with that name; otherwise pass it explicitly with
`secrets: { platform_token: ${{ secrets.PLATFORM_READ_TOKEN }} }`. Every central
checkout uses `secrets.platform_token`, falling back to `github.token`.

#### Pre-gate limitation: existence-only Check

The pre-gate validates the repository itself, while the sample-app pipeline
validates the workflow end to end. The pre-gate's settings self-test runs `checker.py --strict` against
`sample-app/.github/pipeline-settings.yml`. Check (in both the pre-gate and the
standard pipeline) only confirms the settings file exists and is readable, so:

- The self-test fails only when that file is missing or unreadable; it no longer
  fails non-compliant settings. `tests/fixtures/invalid-settings.yml` passes the
  checker, and the pre-gate does not check it anyway.
- `--strict` is retained for compatibility but has no effect.
- The pre-gate still enforces the contribution rules (commit, branch and PR title
  conventions, ADR gate).

Real settings enforcement returns when schema validation lands in the settings
checker story.

### Git hooks

```bash
make install-hooks
```

This enables the local branch-name and commit-message checks. Review staged
changes before committing:

```bash
git status
git diff --staged
```

## Branch and commit conventions

Create branches using `<type>/<JIRA-ticket>/<short-description>`, for example:

```text
feature/DP-146/initial-monorepo-scaffold
```

Use Conventional Commit messages in the form `<type>(<scope>): <short description>`, for example:

```text
feat(checker): validate pipeline settings
```

Allowed commit types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.

Allowed scopes: `workflows`, `checker`, `app-template`, `sample-app`, `fixtures`, `docs`, `repo`, `deps`.

Include the Jira key in the PR title. For a branch without a Jira ID, include a Jira key in the PR title or a commit message.

Mark breaking changes with `!` after the scope or a `BREAKING CHANGE:` footer. Breaking PRs require a new ADR under `docs/adr/` or a reference to an ADR that exists on `main`.
