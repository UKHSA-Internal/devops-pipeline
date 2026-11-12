# Using the shared pipeline

This guide is for service teams adopting the pipeline. For the settings
contract, rules and checker options, see the
[settings checker reference](../packages/settings-checker/README.md).

## Prerequisites

The platform repository's Actions access must be set to organisation level
(Settings, Actions, General, Access). GitHub can then fetch the release's
pinned composite actions for consumers without a separate checkout token.

Use the floating major tag (`@v1`) for automatic updates, or an exact version
tag (for example `@v1.0.0`) for a fixed release. `@v0` stays on the last 0.x
release and no longer receives updates; callers on `@v0` should move to `@v1`.

## Add a caller

Create `.github/workflows/pipeline.yml` in the service repository. See the
[tested example caller](examples/caller-workflow.yml) for a complete file,
including the `contents: read` and `id-token: write` permissions Deploy needs
for OIDC and the optional `settings_path` input.

The [app-template caller](../packages/app-template/.github/workflows/pipeline.yml)
uses the same `uses:` reference. The workflow reference must be literal.

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
command and placeholder scan. Pushes to `main` additionally build, deploy and
verify the service; pull requests stop after Scan, so they never build an
image or deploy. It records a run report and passes the full-commit-SHA image
tag to each deployment. Deployments within each category run one at a time in
settings order. Pushes to `main` deploy to Development; Pre-production and
Production also run only on pushes to `main`.

<!-- TODO: Pull requests may deploy to an ephemeral environment in future. -->

`deploy.production.approval_mode` is required: `all-approvers`,
`single-approver` or `unattended`. The last requires
`deploy.production.exception_id`. The approval gate is managed separately
from this workflow.

For local development and limitations of the sample pipeline, see
[local development](local-development.md).
