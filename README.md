# DevOps Pipeline (`devops-pipeline`)

Centralised pipeline standards, shared GitHub Actions workflows, compliance checking tools, and onboarding starter templates for UKHSA service teams.

## Local development

Run `make help` to see the available local commands.

### Validate settings and test the standard pipeline

Validate the platform repository's settings:

```bash
make check-settings
```

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

Use Conventional Commit messages in the form `<type>(<scope>): <short description>` and include the Jira ticket, for example:

```text
feat(checker): validate pipeline settings (DP-146)
```

Allowed commit types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`.

Allowed scopes: `workflows`, `checker`, `starter-template`, `sample-app`, `fixtures`, `docs`.
