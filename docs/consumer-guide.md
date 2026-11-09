# Using the shared pipeline

This guide is for service teams adopting the pipeline. For the settings
contract, rules and checker options, see the
[settings checker reference](../packages/settings-checker/README.md).

## Prerequisites

The platform repository's Actions access must be set to organisation level
(Settings, Actions, General, Access). GitHub can then fetch the release's
pinned composite actions for consumers without a separate checkout token.

Use the floating major tag for automatic updates, or an exact version tag for a
fixed release. Before the deliberate 1.0.0 cut-over, use `@v0` or an existing
`@v0.x.y` release; `@v1` is not available until that cut-over.

## Add a caller

Create `.github/workflows/pipeline.yml` in the service repository. For example:

```yaml
name: Service Pipeline

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  pipeline:
    uses: UKHSA-Internal/devops-pipeline/.github/workflows/standard-pipeline.yml@v0
```

The [app-template caller](../packages/app-template/.github/workflows/pipeline.yml)
currently uses `@v1`; change it to `@v0` or an existing exact release until
the 1.0.0 cut-over. The workflow reference must be literal.

## Configure the service

Start with the [app-template settings](../packages/app-template/.github/pipeline-settings.yml)
at `.github/pipeline-settings.yml`. Replace placeholder service information,
accounts, roles and approvers with the service's values. Provide at least one
environment in each of Development, Pre-production and Production.

`service.test_command` must be a non-empty, single-line command. The template's
`python3 -m unittest discover -s tests -v` runs a placeholder test: replace the
placeholder with the service's real tests. The
[sample app](../sample-app/README.md) shows a working example.

The workflow uses `.github/pipeline-settings.yml` by default. For a service in a
subdirectory, set the reusable workflow's `settings_path` input to its settings
file. If no input or root settings file is present, the workflow accepts exactly
one `*/.github/pipeline-settings.yml` file. The test command runs from the
service directory.

Check settings locally before onboarding:

```bash
pip install -r packages/settings-checker/requirements.txt
python3 packages/settings-checker/checker.py ../my-service
```

Run these commands from a checkout of this platform repository. The checker
reports errors and warnings; its default mode fails on errors. Use `--strict`
to fail on warnings too. See the [checker reference](../packages/settings-checker/README.md)
for the complete contract and options.

## What the pipeline does

The Check stage validates settings, then the pipeline runs the configured test
command, placeholder scan, build, deployments and verification. It records a
run report and passes the full-commit-SHA image tag to each deployment.
Deployments within each category run one at a time in settings order. Pull
requests deploy to Development only; Pre-production and Production run only
on pushes to `main`.

`deploy.production.approval_mode` is required: `all-approvers`,
`single-approver` or `unattended`. The last requires
`deploy.production.exception_id`. The approval gate is managed separately
from this workflow.

For local development and limitations of the sample pipeline, see
[local development](local-development.md).
