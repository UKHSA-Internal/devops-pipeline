# DevOps Pipeline (`devops-pipeline`)

Centralised pipeline standards, shared GitHub Actions workflows, compliance checking tools, and onboarding starter templates for UKHSA service teams.

## Local development

Run `make help` to see the available local commands.

### Check settings and test the standard pipeline

Confirm that the platform repository's settings file is present and readable:

```bash
make check-settings
```

The same command can check either fixture file:

```bash
make check-settings SETTINGS=tests/fixtures/valid-settings.yml
make check-settings SETTINGS=tests/fixtures/invalid-settings.yml
```

These commands currently perform only a file readability smoke check. Both
fixtures can pass this check because YAML parsing and schema validation have
not been implemented yet. A missing or unreadable file returns a non-zero exit
code. Paths are relative to the repository root.

Test the **reusable standard pipeline** against the local composite action and
the root settings file:

```bash
make test-standard-pipeline-local
```

This invokes `.github/workflows/standard-pipeline.yml` directly with `act`'s
`workflow_call` event and passes the root settings path plus
`use_local_action=true`. Edits to the reusable workflow, composite action, and
checker in this checkout are tested without fetching the published platform
action. No local test-caller workflow is added to the workflows shown in GitHub.

### Run the platform pre-gate locally

The pre-gate is a separate workflow; run it with:

```bash
make test-pregate-local
```

Both workflow targets require [act](https://nektosact.com/) and Docker, with the
Docker daemon running. They use the full runner image by default because
`actions/setup-python` needs Node.js during cleanup. The full image is large;
override it if you have a compatible image:

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

Allowed scopes: `workflows`, `checker`, `starter-template`, `sample-app`, `fixtures`, `docs`, `repo`, `deps`.

Include the Jira key in the PR title. For a branch without a Jira ID, include a Jira key in the PR title or a commit message.

Mark breaking changes with `!` after the scope or a `BREAKING CHANGE:` footer. Breaking PRs require a new ADR under `docs/adr/` or a reference to an ADR that exists on `main`.
