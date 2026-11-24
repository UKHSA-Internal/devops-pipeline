# 8. Proof of concept: deploy to externally managed AWS infrastructure

* **Status:** Proposed
* **Date:** 2026-11-24

## Summary
This proof of concept proves that the pipeline can build, deploy, verify and
roll back a service whose infrastructure is managed elsewhere. It runs in the
sandbox only: one image, one ECS service, one Development environment. The
deliverable is a released pipeline version that does this using GitHub OIDC
and no secrets, while existing consumers carry on unchanged.

## Context
- Deploy and Verify are simulated today. The run record flags them as
  simulated stages. That flag comes with the Production approval gate
  (ADR 0006), which this work builds on.
- Services' infrastructure is managed in their own infrastructure
  repositories. Those repositories also deploy the services today.
- These standing constraints apply:
  - Consumers pass no secrets.
  - There is no GitHub App.
  - Shared code holds nothing specific to one service.
  - Existing settings files keep working.
  - Recovery is always a redeployment of a previously verified artifact.

## Decision: what the proof of concept builds

### Scope

| In | Out |
|---|---|
| One image, one ECS service, one Development environment, in the sandbox | Other environments, including Pre-production |
| Build, Deploy, Verify and rollback | Production |
| GitHub OIDC only | Lambda |
| Reusable pipeline code and Terraform modules | Any real service |
| | Any change to another team's repository |

### Access
GitHub OIDC only, using AWS's official actions, pinned.

| Role | Account | Trusts | Can |
|---|---|---|---|
| Registry push | Tools | The service repository, on `main` only | Write to the tools pipeline-only repository |
| Deploy | Development | The service's `Development` GitHub environment | Deploy one cluster, one service, its task roles and one repository; pull from the tools pipeline-only repository |

The tools repository's policy lets only the push role write, and lets the
deploy role pull.

Main-only is enforced three ways:

- **Workflow.** Build publishes to a registry, and Deploy runs, only on a push
  to `main`. Today any run that is not a pull request deploys Development.
- **OIDC subjects.** The default subjects limit the roles as above.
- **Branch policy.** The `Development` environment's branch policy is set to
  `main` only, by hand.

Build and the deploy jobs ask for `id-token: write`. GitHub refuses to start a
run whose called jobs ask for more than the caller grants. So the platform's
own callers (the sample app, the app template, the examples and the sandbox)
are updated in the same release or before. The known consumers are checked
and told before release.

### Build once, promote by digest
- On `main`, Build builds for `build.platform`, passes `COMMIT_SHA` as a build
  argument, and pushes `dp-<commit-sha>` to a pipeline-only repository in the
  tools account.
- Deploy copies that image by digest into a pipeline-only repository in the
  Development account.
- Both repositories use immutable tags and keep the last 10 images.
- Infrastructure Terraform and scripts never read these repositories, so a
  pipeline image cannot reach another service or environment.
- The digest replaces the tar `.sha256` file.
- Pull requests and feature branches never build to a registry or deploy.

### Deploy engine
A new Python package, `packages/deploy-engine/`, with `publish`, `deploy`,
`verify` and `rollback` commands. It uses a provider model: `aws` is the first
provider and `aws.ecs` the first target type. Composite actions are thin
wrappers around it.

The pipeline owns the application deploy only. A deploy changes only the
image. Every other task definition setting stays as the infrastructure
repository set it. Concurrency is keyed on service and environment. The engine
labels what it creates.

| Item | Label |
|---|---|
| Images | `dp-<commit-sha>`, in the pipeline-only repositories |
| Task definitions | Tagged `deployed-by=devops-pipeline`, with the commit and run ID |
| Version record | SSM `/devops-pipeline/<service>/<env>/version` |
| Rollback point | The previous task definition's ARN, with its image digest, in SSM before each deploy |

### Verify
Verify checks independently that:

- every running task uses the expected digest;
- the live task definition is the one this run registered;
- `GET /health/` returns the deployed commit, in the field set by
  `verification.version_field` (default `commit_sha`).

Verify sends no auth headers, so no application secret reaches the runner.

### Rollback
Before each deploy, the engine saves the live task definition and its image
digest in SSM. When a check fails, it confirms that image still exists,
restores the saved task definition, and still fails the stage. The database is
never rolled back.

The run record gains the digest, the previous and new task definitions, the
verification results, the rollback outcome and the run attempt.

### Settings format version 1.2
A service opts in by setting `version: "1.2"` in its settings file. This is the
settings format version. It's separate from pipeline releases (for example
`v1.3.0`) and from the LLD's document version. Format versions so far:

- 1.0: the original fields;
- 1.1: adds `service.test` (ADR 0007);
- 1.2: adds the deploy settings below (this ADR).

All additions are optional. Existing 1.0 and 1.1 settings files behave
exactly as today.

| Field | Purpose |
|---|---|
| `build.platform`, `build.build_args` | Image build options |
| `registry` | `type` (`aws.ecr`), `account_id`, `role_name`, `region`, `repository`, `promote_to` |
| `deploy.infrastructure` | External only, for now |
| `deploy.timeout_minutes` | Deploy timeout |
| `deploy.targets` | One `aws.ecs` target: `cluster`, `service`, optional `container` |
| `environments[].template_values` | Per-environment values |
| `environments[].verification.base_url` | Health endpoint base URL |
| `verification.version_field` | Field that holds the deployed commit |

The Settings Check tool gets six new rules. All are Errors.

| Rule | Checks |
|---|---|
| CHK-19 | `build.platform` is `linux/amd64` or `linux/arm64`. `build.build_args` are single lines and don't override `COMMIT_SHA`. |
| CHK-20 | `registry` is a known type. For AWS, the account, role and region are present, and repository names are valid ECR names. |
| CHK-21 | `deploy.infrastructure` is external. `deploy.timeout_minutes` is a whole number within the limits. There is exactly one `aws.ecs` target, with valid names. `registry` is set. Only allowed template values are used. |
| CHK-22 | `deploy` applies to one Development environment only, for now. |
| CHK-23 | Each deployed environment has an `https` `verification.base_url` with no path. `verification.version_field` is a simple key. |
| CHK-24 | When `deploy` is set, environment names and `service.name` use lowercase letters, digits and hyphens, are unique ignoring case, and stay within a length limit. |

A settings version newer than the pipeline supports already fails Check
(CHK-14, ADR 0007).

Deploy and Verify become real only for services with `deploy.targets`, and
then stop flagging themselves as simulated. Services without deploy settings,
including the sample app and the release smoke test, stay simulated.

### Terraform modules
Reusable modules under `terraform/aws/`, which consumers apply in their own
infrastructure repositories: the registry push role, the deploy role and the
pipeline-only ECR repositories. The modules look up an existing OIDC provider,
and create one only where none exists.

## Deliverable and done when
A released pipeline version that, in the sandbox:

- deploys a merge to `main` and verifies it;
- rolls back a deliberately broken change and fails the run;
- refuses to publish or deploy from a feature branch or pull request;
- leaves existing consumers unchanged and simulated;
- uses no secrets.

**Evidence:** the run records from those runs.

## Needs
- The sandbox AWS accounts (tools and Development), with OIDC providers.
- A small test service whose `/health/` returns its commit.
- Decisions D5, D14 and D16 (see Open decisions).

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Hand over to the infrastructure repository's own workflow | Needs a cross-repository token, so a GitHub App or a personal token. Both conflict with standing decisions. Kept for later |
| Put pipeline images in the shared repositories, and have infrastructure filter out `dp-*` | Terraform's "most recent" image lookup cannot filter by tag, and an image copied into a shared repository would move every service that uses it. A missed filter would ship a pipeline build to Production |
| Moving rollback tags (`dp-<env>-current` and `dp-<env>-previous`) | The repositories use immutable tags |
| Custom OIDC subject claims for main-only | Not needed for Development. Revisit when trust is pinned to the shared workflow before Production |
| Rebuild the image per environment | What is tested would no longer be what is deployed |
| The pipeline manages the infrastructure too | Too much ownership and risk for a first step |

## Consequences
These apply to the proof of concept only.

**What we gain**

- Real deploys with no consumer secrets.
- The exact tested image is deployed.
- Deploys are checked independently and rolled back automatically.
- Pipeline images cannot reach other services or environments.
- Existing consumers carry on unchanged.

**What it costs**

- A new package, composite actions and Terraform modules to maintain.
- The platform's own callers must grant `id-token: write`.
- Until trust is pinned to the shared workflow before Production, another
  workflow in the same repository that uses the `Development` environment on
  `main` could reach the deploy role.

**The LLD changes only after the proof of concept succeeds.** Then these
sections change: Build, Deploy, Verify and rollback; concurrency; the settings
rules; consumer requirements (`base_url` replaces the
`DEPLOYMENT_BASE_URL_<NAME>` variables for deployed environments); the run
record; identity and access; and the settings format version list in section
4.1.

## After the proof of concept (not decided here)
The first real service is `private-api`, one of six ECS Fargate services that
`data-dashboard-api` runs from one ARM64 image, in `uhd-dev`. The six share one
database and run migrations when they start. `uhd-dev` scales to zero
overnight and at weekends. Today the service's infrastructure repository
deploys on every merge: it picks the newest image from a shared tools ECR
repository (immutable tags; environments keep 5 images, tools 30), applies
Terraform and restarts every environment, Production included. The tools
account is managed in its own infrastructure repository, which applies on
merge, and its existing push role trusts every branch.

That step needs the infrastructure team's changes, Terraform plans checked in
dev and staging, their sign-off, and a separate decision. We recommend a
separate ADR or decision log entry when it is taken.

| Item | Detail or recommendation | Needed by |
|---|---|---|
| D7: how infrastructure stops Terraform resetting the service | Dev-only `ignore_task_definition_changes = true` and `track_latest = false`. No `moved` block, because it cannot be limited to dev and would recreate the service in every other workspace. Instead, a one-off `terraform state mv` in the dev workspace, done with the merge while dev applies are paused | First service |
| D10: which service and environment go first | `private-api` in `uhd-dev` | First service |
| D15: who is told about failures, and who responds | The service team's channel; the Platform Team as backup | First service |
| D17: whether an older image can replace a newer one | No. Each deploy job refuses an image older than the version in SSM, so an approved older run can wait up to 24 hours without overwriting a newer deploy | First service |
| D18: can one service run ahead of the five sharing its image in `uhd-dev`? | Yes, for Development only, with the tech lead's sign-off. Migrations, which rollback cannot undo, must be backward compatible (about six a year are not, for example new NOT NULL columns; we recommend a CI check). Shared Redis values can be written by an older worker. The hydrate job runs the infrastructure repository's image | First service |
| D20: how Verify reaches a health endpoint behind an API key | An exact `GET /health/` route without the API key, at load balancer rule priority 2, only where the environment is `dev` (not `is_dev`, which also covers dpd, personal and CI environments) | First service |
| D21: a deploy while Development is scaled to zero | Fail fast with "environment asleep" | First service |
| D22: how a superseded run is recorded | SKIPPED, with the reason superseded, and no rollback | First service |
| Tools account resources | The push role and the tools pipeline-only repository live in the tools infrastructure repository, using its existing OIDC provider. **Decided** (D19) | First service |
| Guard job | Before the Development deploy, checks that the `Development` environment allows `main` only, and fails closed like the Production approval guard. Existence alone means nothing, because GitHub creates missing environments. A repository admin creates `Development` first | First service |
| Rollback from saved JSON | Save the full task definition JSON too, and re-register from it if infrastructure Terraform has deregistered the revision. Record where the task definition came from | First service |
| Build argument | `COMMIT_SHA` also reaches the image from the service's existing publish-image action. The service's caller needs a push trigger on `main`, so both pipelines deploy the same merge | First service |
| Restart script | Skips the service when the cluster is `uhd-dev-cluster`, and drops it from the wait-for-stable list | First service |
| Existing push role | We recommend narrowing it from every branch to `main`. Not blocking | First service |
| Pruning | The engine prunes only the task definition revisions it registered | First service |
| Pipeline commit in the run record | Record `job.workflow_sha`, so the record shows which release deployed | First service |

Later stages (every service sharing the image, more Development and
Pre-production environments, then Production) are each proven in the sandbox
first.

## Open decisions (proof of concept)
| ID | Question | Recommendation |
|---|---|---|
| D5 | How consumers get the Terraform modules | A git source pinned by commit, with version tags |
| D14 | Deploy timeout | 15 minutes by default, 30 at most; job timeout 70 minutes |
| D16 | How many images the pipeline-only repositories keep | The last 10 |
