# DevOps Pipeline (`devops-pipeline`)

Centralised pipeline standards, shared GitHub Actions workflows, settings
checking tools and starter templates for UKHSA service teams.

## Open source

This repository is open source and developed in the open by the UKHSA Platform
Team.

It is a new project in active development, so behaviour may change as features
and standards evolve.

This repository is supported for UKHSA teams only.

- For contributions, see [CONTRIBUTING.md](CONTRIBUTING.md).
- Security issues must not be raised as public GitHub issues; see
  [SECURITY.md](SECURITY.md).
- Licence information is in [LICENSE](LICENSE).

## Get started

- **Use the pipeline:** follow the [consumer guide](docs/consumer-guide.md).
- **Develop and test locally:** see the [local development guide](docs/local-development.md).
- **Release the workflow package:** use the [release guide](docs/workflow-release.md).
- **Check service settings:** see the [settings checker reference](packages/settings-checker/README.md).
- **Contribute:** read [CONTRIBUTING.md](CONTRIBUTING.md) for branch, commit,
  review and ADR requirements.

For a quick local check from the repository root:

```bash
pip install -r packages/settings-checker/requirements.txt
make check-settings
python3 -m unittest discover -s tests
```

Running the shared pipeline and pre-gate locally also requires `act` and Docker;
see the [local development guide](docs/local-development.md).

## Simulated stages

Deploy and Verify are placeholders. They touch no infrastructure. Each run
record lists them under `simulated_stages`, and the job summary names them.
The placeholder actions are:

- Deploy: `packages/shared-workflows/actions/deploy`
- Verify: `packages/shared-workflows/actions/verify-app`

A real implementation removes its action's `simulated` output, and the stage
drops off the list.

## Repository structure

| Path | Purpose |
| --- | --- |
| `.github/` | Repository settings, GitHub workflow entrypoints and pull request template |
| `packages/shared-workflows/` | Composite actions and shared workflow sources |
| `packages/settings-checker/` | Settings checker package |
| `packages/app-template/` | Starter configuration and workflow for service repositories |
| `sample-app/` | Example service demonstrating the shared pipeline |
| `scripts/` | Repository-maintenance scripts and release tag rulesets |
| `tests/` | Automated tests and fixtures |
| `docs/` | Guides, architecture decision records and diagrams |

The GitHub-discovered workflow entrypoints in `.github/workflows/` and
`packages/shared-workflows/` are released together as one workflow package.
