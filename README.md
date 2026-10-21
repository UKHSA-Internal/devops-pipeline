# DevOps Pipeline (`devops-pipeline`)

Centralised pipeline standards, shared GitHub Actions workflows, compliance checking tools, and onboarding starter templates for UKHSA service teams.

## Local development

Run `make help` to see the available local commands.

### Validate pipeline settings

Check `.github/pipeline-settings.yml` against the settings contract before committing:

```bash
make check-settings
```

### Run GitHub Actions locally

Install [act](https://nektosact.com/) and Docker, and make sure the Docker daemon is running. Then list detected workflows and jobs:

```bash
make test-workflow-local ARGS=-l
```

Run the pre-gate workflow locally with a full runner image:

```bash
make test-workflow-local ARGS='pull_request -W .github/workflows/pre-gate.yml -P ubuntu-latest=catthehacker/ubuntu:full-latest'
```

The default `.actrc` image is lightweight. The full image is used above because actions such as `actions/setup-python` require Node.js for their post-step, which is not present in the lightweight image. The full runner image is large and may use substantial disk space.

### Git hooks

Enable the repository's local branch-name and commit-message checks once per clone:

```bash
make install-hooks
```

The hooks validate branch names and Conventional Commit messages before committing. To check the staged changes before committing:

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
