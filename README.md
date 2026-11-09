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

The workflow pins each shared composite action reference to the release
commit, creating a child commit without updating `main`. It then publishes the
canary alias by force-updating `v<MAJOR>-canary` to that pinned commit. Before
the deliberate 1.0.0 cut-over, the floating aliases are `v0` and `v0-canary`; `v1` and
`v1-canary` are not created before version `1.0.0`.

Consumers need no token to fetch the pinned actions. The platform repository's
Actions access must be set to the organisation level so GitHub can fetch the
actions on behalf of consumer workflows.

Two more checks run in `prepare`:

- **Downgrade guard:** the version must be higher than every existing
  `vX.Y.Z` tag with the same major. A lower version fails the release. The
  duplicate-tag check runs first, so a version equal to an existing tag fails
  as a duplicate; only a version below the lowest existing tag (for example
  `0.0.0`) shows the downgrade error.
- **Unchanged version:** a `VERSION` edit counts as unchanged only if the value
  is the same once trailing newlines are ignored. Any other whitespace change
  makes the value fail strict SemVer.
- **Concurrency:** pushes to `main` share one `release-platform` queue and never
  cancel a running release. GitHub keeps only the latest queued run, so if
  several releases queue behind a running one, only the newest runs. Skipped
  intermediate versions are never tagged. Dry runs use a separate group per
  ref (`release-platform-dry-run-<ref>`), so a pull request can never displace
  a pending release.

After the canary moves, the smoke test runs (see
[Canary smoke test](#canary-smoke-test)). If it passes, the release is promoted
automatically (see [Promotion](#promotion)).

### Promotion

There is no manual approval step. When the smoke test passes, the `promote` job
first asserts that `v<MAJOR>-canary` points at the pinned commit, and fails if
it does not (for example, if a newer release moved it). It then creates
`vX.Y.Z` on the pinned commit, then force-moves `v<MAJOR>` to the same commit.

- **Idempotent:** if `vX.Y.Z` already exists and points at the pinned commit,
  it is not recreated and `v<MAJOR>` is still moved. If it exists and points at
  a different commit, the job fails.
- **Recovering a partial promotion** (for example `vX.Y.Z` was pushed but
  moving `v<MAJOR>` failed): use "Re-run failed jobs" on the run, which re-runs
  only `promote`. Do not use "Re-run all jobs": `prepare` would reject the
  already existing `vX.Y.Z`. Only re-run the most recent release run: if a
  later release has moved `v<MAJOR>-canary`, the canary assertion fails by
  design.
- **Smoke test fails:** nothing is promoted. No `vX.Y.Z` is created and
  `v<MAJOR>` does not move. `v<MAJOR>-canary` has already moved to the commit
  and stays on that failing commit until the next successful release.
  Releases trigger only when `VERSION` changes, so ship the fix under a new
  version.
- **Dry run:** `promote` never runs.
- **Tag protection:** see [Tag protection](#tag-protection).

TODO: whether promotion should also create a GitHub Release is undecided.

### Tag protection

Tags are protected by two repository rulesets. Definitions and apply
instructions are in [scripts/rulesets/](scripts/rulesets/README.md).

- **Release tags (`v*.*.*`):** immutable. Once created, a version tag can't be
  moved or deleted; anyone with write access can create one. If a version tag is
  created outside a release, the release's duplicate-tag check will fail; a
  repository admin must disable the ruleset temporarily to remove the tag. This
  ruleset can be applied now without blocking releases.
- **Floating tags (`v0`, `v0-canary`, `v1`, `v1-canary`):** protected by a
  second ruleset. Only the release, and the small team set as that ruleset's
  bypass actor, can create, move or delete them. The release token's owner must
  be a member of that team, or releases cannot move the floating tags.

Consumers use the floating major tag (for example `@v0`, later `@v1`) for
automatic updates. They may pin to an exact version (for example `@v0.1.1`) if
they need to.

### Release token

`RELEASE_TOKEN` is the permanent release identity. It is a classic personal
access token with the `repo` and `workflow` scopes, authorised for SSO, and
stored only in the `release` environment. That environment is restricted to
`main`, so only a push to `main` can read it.

The pinned release commit changes a workflow file, and `GITHUB_TOKEN` can never
push such a commit. The `canary` and `promote` jobs therefore push with
`RELEASE_TOKEN`. Both jobs fail early with a clear error if the token is empty.
No other job, and no dry run, uses the environment or the token.

- **Owner:** owned by chrisp-burendo on behalf of the Platform Team. The
  Platform Team is responsible for rotating it before expiry and replacing it
  if the owner leaves.
- **Rotation:** rotate the token before it expires, or releases will fail at
  the first push.
- **Owner leaves or token expires:** create a new classic token with the same
  scopes, authorise it for SSO, and replace the `RELEASE_TOKEN` secret in the
  `release` environment with it.

### Reading the release summary

The `Release summary` job runs only once a release was attempted: on a push to
`main` where `prepare` succeeded and found a changed `VERSION`. It still runs
if `canary`, `smoke-test` or `promote` fails or is skipped. It does not run in
a dry run, when `VERSION` is unchanged, or when `prepare` fails (the failed
`prepare` job is then the report). It lists:

- the version and commit;
- the source commit and the pinned commit;
- the canary, smoke test and promotion results;
- for `v<MAJOR>-canary`, `vX.Y.Z` and `v<MAJOR>`, whether each tag points at the
  pinned commit, exists elsewhere, or does not exist. A failed tag lookup fails
  the job rather than being reported as a tag state.

### Canary smoke test

The release's `smoke-test` job calls the local `standard-pipeline.yml` with the
sample app's settings (`sample-app/.github/pipeline-settings.yml`). The canary
tag points at a child commit whose action references are pinned to the source
commit. Promotion asserts that `v<MAJOR>-canary` points at that pinned commit.
The smoke test passes only if every pipeline stage passes.

- **In a release:** the `smoke-test` job runs after `canary` succeeds.
- **Manually:** run `smoke-test-pipeline.yml` with `workflow_dispatch` (Actions
  tab, or `gh workflow run smoke-test-pipeline.yml`). Unlike the release's
  smoke test, this calls `standard-pipeline.yml@v0-canary`, so it tests the
  published canary at any time. It has no other trigger.
- **Limitation:** it runs inside the platform repository, so it cannot catch
  every cross-repository problem, such as a consumer's own token or
  permissions.
- **Dry run:** it is skipped, because it needs `canary`, which runs only on a
  push to `main`. The dry-run summary says what would run. `pre-gate.yml`
  and `sample-app-pipeline.yml` use relative references on the PR's own
  checkout, so they test that PR's workflow and action code.

### Release dry run

`release-cicd-platform.yml` also runs on pull requests that change
`packages/shared-workflows/VERSION`, `release-cicd-platform.yml` or
`smoke-test-pipeline.yml`. Any event other than a push to `main` is a dry run,
so you can test the release logic before merging.

A dry run, with read-only (`contents: read`) permissions:

- Validates the version with the same rules as a real release.
- Compares the PR head's `VERSION` with the base branch's. If it is unchanged,
  it reports "no release would run" and passes.
- Checks that the `vX.Y.Z` tag does not already exist, and that the version is
  not lower than an existing release of the same major (read-only).
- Derives the aliases and applies the pre-1.0 safety check.
- Writes the exact tag commands it would run, that the smoke test would run the
  release commit's pipeline, and the planned promotion (`vX.Y.Z` and
  `v<MAJOR>` on the commit, if the smoke test passes), to the job summary.

A dry run does not:

- Create or move any tag. Only a push to `main` runs the tag-moving `canary`
  and `promote` jobs.
- Smoke-test the canary or promote. Both `smoke-test` and `promote` are skipped
  whenever `canary` is skipped.
- Test the PR's own pipeline code. `pre-gate.yml` covers that.

## Local development

Run `make help` to see the available local commands.

### Check settings

The settings checker reports whether a repository's settings are ready to
onboard to the shared pipeline. Install its pinned dependencies, then check the
sample app's settings with `--strict` (any error or warning fails):

```bash
pip install -r packages/settings-checker/requirements.txt
make check-settings
```

To check another file, such as a fixture:

```bash
make check-settings SETTINGS=tests/fixtures/settings/compliant.yml
make check-settings SETTINGS=tests/fixtures/settings/warnings-only.yml  # fails: --strict
```

To check another repository on your machine, point the checker at its folder:

```bash
python3 packages/settings-checker/checker.py ../my-service
```

Set `PYTHON=/path/to/python` to use a virtual environment. Paths are relative
to the repository root. The settings contract, rules, modes and output formats
are described in
[`packages/settings-checker/README.md`](packages/settings-checker/README.md).

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

- Checks the settings file in the Check stage with the settings checker in its
  default mode. Errors fail Check; every error and warning is listed in the
  job summary.
- Runs the service test command from `service.test_command` in the settings
  file, from the service directory. The sample app and the app-template both
  use `python3 -m unittest discover -s tests -v`; the template's
  `tests/test_placeholder.py` should be replaced with the service's real tests.
- Runs the placeholder scan and deploy steps.
- Builds a local image and records a run report. The full-commit-SHA image tag
  is passed unchanged to each deployment.
- Reads deployments from the settings file's `environments` list. Each
  category (Development, Pre-production, Production) can have multiple named
  deployments, run one at a time in settings order. Every deployment is
  followed by `verify-app` against `verification.health_endpoint`.

Check fails if a category has no deployments. Pull requests deploy to
Development only; Pre-production and Production deploy only on pushes to
`main`. To smoke-test the published canary alias, manually run
`.github/workflows/smoke-test-pipeline.yml`.

`deploy.production.approval_mode` is required: `all-approvers` (every listed
approval group must approve), `single-approver` (any one listed group), or
`unattended` (no approver; requires `deploy.production.exception_id`). The
approval gate is managed separately from this workflow.

For `act` runs, generated build files and `run-record.json` are saved under the
ignored `.act-artifacts/` directory.

Two failure scenarios can be exercised locally; each asserts a non-zero run and
that the run record marks downstream steps `SKIPPED`:

```bash
make test-pipeline-failing-test   # injected unit-test failure: test FAILED
make test-pipeline-failing-check  # missing settings file: check FAILED
```

The settings checker, deployment resolver and run-record structure are
covered by (with the settings checker's requirements installed):

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

#### Platform action access

Consumers do not need a token to fetch the pinned shared actions. Set this
repository's Actions access to the organisation level (Settings, Actions,
General, Access) so GitHub can fetch actions for consumer workflows. Each
release pins the action references in `standard-pipeline.yml` to the release
commit, keeping the workflow and its composite actions on the same revision.

#### Pre-gate settings checks

The pre-gate validates the repository; the sample-app pipeline exercises the
workflow end to end. Besides the contribution rules for commits, branches, PR
titles and the ADR gate, the pre-gate:

- runs `checker.py --strict` against the sample app and app-template, which
  must have no errors or warnings;
- runs the checker against every fixture in `tests/fixtures/settings/` and
  asserts the exit codes: the compliant file passes with `--strict`, each file
  in `errors/` fails by default, `warnings-only.yml` passes by default and fails
  with `--strict`, `unparseable.yml` fails unless `--report-only` is used, and
  every file passes with `--report-only`.

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
