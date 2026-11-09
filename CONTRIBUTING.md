# Contributing to devops-pipeline

This guide applies to everyone changing `UKHSA-Internal/devops-pipeline`. Rules marked as applying to adopting service repositories apply there too.

The rules are enforced by required PR status checks: `pre-gate.yml`, the commit linter and the branch name validator. A PR that breaks them cannot merge.

## Branching

- **Trunk-based.** `main` is the single source of truth for pipeline logic, shared actions, governance tools and starter templates. Direct commits to `main` are blocked.
- **Branch names:** `<type>/<jira-id>/<description>`, for example:
  - `task/DP-123/add-pregate-check`
  - `feature/DP-456/oidc-auth`
  - `fix/DP-789/yaml-parser-error`
- **Allowed types:** `task`, `feature`, `fix`, `chore`, `refactor`, `docs`.
- The Jira ID lets the GitHub–Jira integration app link branches to tickets automatically.
- **Fallback Jira linkage.** A branch without a Jira ID is allowed only if the PR title or commit messages reference the issue key, for example `[DP-123] feat(checker): enforce schema validation`.
- **Legacy service repositories.** Trunk-based development is enforced for platform repositories. Some adopting service repositories use GitFlow or other models; a migration path will be defined following discovery with L2/L3 leads.

## Commits

Commits follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>
```

This gives auditability across shared platform assets, automated changelog generation and two-way traceability with Jira.

### Types

| Type | Use for |
| --- | --- |
| `feat` | New capability (minor version change) |
| `fix` | Bug fix (patch version change) |
| `chore` | Maintenance with no behaviour change |
| `docs` | Documentation only |
| `refactor` | Code change with no behaviour change |
| `test` | Tests only |

### Scopes

| Scope | Covers |
| --- | --- |
| `workflows` | `.github/workflows/` and the composite actions in `packages/shared-workflows/actions/`, released together as one workflow package |
| `checker` | `packages/settings-checker/` |
| `app-template` | `packages/app-template/` |
| `sample-app` | `sample-app/` |
| `fixtures` | `tests/fixtures/` |
| `docs` | `docs/`, including ADRs |
| `repo` | Repository-level config and tooling: commitlint, CODEOWNERS, root files, non-workflow `.github/` files |
| `deps` | Dependency updates |

The commitlint `scope-enum` rule must list exactly these scopes.

### Choosing a scope

1. **Change spans several components:** use the scope where the behaviour change lives, and list the other affected components in the PR description.
   Example: renaming a settings field touches the checker, fixtures, template and sample app, so use `feat(checker): rename approvers field (DP-123)`.
2. **Repository-level or tooling change:** use `repo`, for example `chore(repo): add CODEOWNERS for settings files (DP-124)`.
3. **Dependency update:** use `deps`, for example `chore(deps): bump pyyaml to 6.0.2`.
4. **Nothing fits exactly:** use the closest scope. Reviewers may correct it before merge.

### Jira key

Include the Jira key in the PR title or commit footer:

```
fix(checker): correct schema path parsing (DP-123)
```

or

```
fix(checker): correct schema path parsing

Ref: DP-123
```

## Pull requests

- **Squash and merge only.** The PR title becomes the single commit on `main`, so it must follow the commit format above, including scope and Jira key.
- **Required checks:** `pre-gate.yml`, commit linter and branch name validator. This applies in this repository and in adopting service repositories.
- **Branch name validation** is a regex check. Branches without a valid Jira reference fail where Jira integration is required.
- **Commit linting** uses `commitlint`, following `ukhsa-collaboration/standards-org/.github/workflows/lint-commit-msg.yml`.
- **Review:** at least one approval from the Platform Team.
- **Description:** state what changed, why, how it was tested, and any ADR reference.

## Breaking changes and ADRs

Architecture Decision Records live in `docs/adr/` as numbered Markdown files, for example `0001-centralised-settings-parsing.md`. Write one for schema updates, central parsing patterns, breaking API revisions and pipeline policy changes.

- **Marking a breaking change:** use `!` in the title or commit (`feat(workflows)!: ...`) or a `BREAKING CHANGE:` footer, or label the PR `breaking-change`.
- **ADR gate:** a breaking PR must either:
  - add a new ADR file under `docs/adr/` in its diff, or
  - reference an ADR already merged on `main`, in the PR description or a commit header, for example `ADR: docs/adr/0004-short-title.md`. The gate checks that the file exists on `main`.
- **Order:** for major or breaking shifts, merge the ADR first in its own PR, then raise the implementation PR. For minor breaking changes, the ADR may be bundled with the implementation.
- **Permanence:** accepted ADRs are never edited. A new ADR explicitly supersedes the old one.

## Versions and releases

Each component releases automatically when its version file changes on `main`:

| Component | Version file |
| --- | --- |
| Workflows and actions | `packages/shared-workflows/VERSION` |
| `settings-checker` package | `packages/settings-checker/pyproject.toml` |
| `app-template` package | `packages/app-template/VERSION` |

Only change a version file when you intend to release.

## Testing before opening a PR

For local workflow setup and failure scenarios, see the
[local development guide](docs/local-development.md).

- Install the settings checker's requirements and run the unit tests (the pre-gate also runs them):
  ```
  pip install -r packages/settings-checker/requirements.txt
  python3 -m unittest discover -s tests
  ```
- Run `checker.py` against the relevant fixtures:
  ```
  python3 packages/settings-checker/checker.py --settings tests/fixtures/settings/<file>.yml --strict
  ```
- Exercise workflow changes locally with [`act`](https://github.com/nektos/act).
- When you add or change a settings rule, edit it in `packages/settings-checker/rules.py`, update
  its cases in `tests/test_settings_checker.py` and the rules table in
  `packages/settings-checker/README.md`. For a new error rule, add a fixture in
  `tests/fixtures/settings/errors/`, named after the problem, and its expected rule ID in the test.
