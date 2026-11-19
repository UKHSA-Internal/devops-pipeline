# 7. Deploy to Externally Managed Infrastructure on AWS

* **Status:** Proposed
* **Date:** 2026-11-18

## Context
The Deploy and Verify stages are placeholders. The run record flags them as
simulated stages. That flag comes with the Production approval gate (DP-189,
PRs #28 to #30), which this work builds on.

The first consumer service builds one ARM64 image. It runs as six ECS Fargate
services in each environment. They share one database, and every service runs
migrations when it starts. The Development environment (`uhd-dev`) scales to
zero tasks overnight and at weekends.

Its infrastructure repository manages the cluster, network and database. That
repository also deploys the services today. On every merge to the service, it
picks the newest image from a shared tools ECR repository, applies Terraform
and restarts the services in every environment, Production included. The ECR
tags are immutable. The environment repositories keep 5 images, and the tools
repositories keep 30.

The tools account is managed in its own infrastructure repository, which
applies automatically on merge. Its existing push role trusts every branch of
the service repository.

These standing decisions still apply:

- Consumers pass no secrets.
- There is no GitHub App.
- Shared code holds nothing specific to one service.
- Existing settings files must keep working.
- Recovery is always a redeployment of a previously verified artifact.

## Decision
**Scope.** This is a proof of concept. It deploys one image to one ECS
service in the sandbox, and is done when build, deploy, verify and rollback are
proven there. The first real service, `private-api` in `uhd-dev`, follows once
the proof of concept passes. The data dashboard details below describe that
step.

**Ownership.** The pipeline owns the application deploy only. A deploy changes
only the image. Every other task definition setting stays as the
infrastructure repository set it.

**Access.** GitHub OIDC only, using AWS's official actions, pinned.

| Role | Account | Trusts |
|---|---|---|
| Registry push | Tools | The service repository, on `main` only |
| Deploy | Development | The service's Development GitHub environment |

The deploy role is scoped to one cluster, one service, its task roles and one
repository.

- The push role and the tools pipeline-only repository live in the tools
  infrastructure repository, using the account's existing OIDC provider.
- The repository's policy lets only the new main-only push role write.
- The repository's policy also lets the Development deploy role pull, so
  Deploy can copy the image into the Development account.
- In the Development account, an existing OIDC provider is looked up before
  one is created. The Terraform modules do not create a provider where one
  exists.

**Main-only.** This is enforced four ways:

- The workflow deploys only on a push to `main`. Today any run that is not a
  pull request deploys Development. Build publishes to a registry only on a
  push to `main`.
- The default OIDC subjects.
- The environment's branch policy, set to `main` only.
- A guard job before the Development deploy checks that the GitHub environment
  `Development` allows `main` only. It fails closed, like the Production
  approval guard. Existence alone means nothing, because GitHub creates
  missing environments automatically. A repository admin creates `Development`
  first.

**Build once, promote by digest, in pipeline-only repositories.**

- On `main`, Build builds for `build.platform` and pushes `dp-<commit-sha>` to
  a pipeline-only repository in the tools account.
- Deploy copies that image by digest into a pipeline-only repository in the
  Development account.
- Both repositories use immutable tags and keep the last 10 images.
- The infrastructure repository's scripts and Terraform never read these
  repositories, so a pipeline image cannot reach another service or
  environment.
- The digest replaces the tar `.sha256` file.
- Pull requests and feature branches never build to a registry or deploy.

**Deploy engine.** A new Python package, `packages/deploy-engine/`, with
`publish`, `deploy`, `verify` and `rollback` commands. It uses a provider
model: `aws` is the first provider and `aws.ecs` the first target type.
Composite actions are thin wrappers around it.

**Verify.** Verify checks independently that:

- every running task uses the expected digest;
- the live task definition is the one this run registered;
- `GET /health/` returns the deployed commit, in the field set by
  `verification.version_field` (default `commit_sha`).

Verify sends no auth headers. The infrastructure repository adds an exact
`GET /health/` route without the API key, at load balancer rule priority 2,
only where the environment is `dev`. It does not use `is_dev`, which also
covers dpd, personal and CI environments. So no application secret reaches the
runner.

**Out of hours.** The engine fails fast with "environment asleep" when the
service is scaled to zero.

**Rollback.** Before each deploy, the engine saves the live task definition's
ARN and full JSON, with its image digest, in SSM. On a failed check, it
confirms that image still exists and restores that task definition. If the
infrastructure repository has since deregistered that revision, rollback
re-registers it from the JSON. The pipeline records where the task definition
came from, and still fails the stage. If another deploy has replaced this one,
the pipeline reports it as superseded and does not roll back. The database is
never rolled back.

**Staleness.** Each deploy job refuses an image older than the version
recorded in SSM. This lets an approved older run wait up to 24 hours without
overwriting a newer deploy. Concurrency is keyed on service and environment.

**Running alongside the existing pipeline.**

| Item | Label |
|---|---|
| Images | `dp-<commit-sha>`, in the pipeline-only repositories |
| Task definitions | Tagged `deployed-by=devops-pipeline`, with the commit and run ID |
| Version record | SSM `/devops-pipeline/<service>/<env>/version` |
| Rollback point | The previous task definition's ARN and full JSON, with its image digest, in SSM before each deploy |

The infrastructure repository stops deploying the one service in `uhd-dev`
only:

- In dev only, `ignore_task_definition_changes = true` and
  `track_latest = false` on the service's module.
- No `moved` block. It cannot be limited to dev, and would recreate the service
  in every other workspace, Production included.
- Instead, a one-off `terraform state mv` in the dev workspace. It is done with
  the merge, while dev applies are paused, with plans checked in dev and
  staging.
- The restart script skips the service when the cluster is `uhd-dev-cluster`,
  and drops it from the wait-for-stable list.
- The engine prunes only the task definition revisions it registered.

**Build argument.** `COMMIT_SHA` reaches the image as a build argument from
both build paths: the pipeline, and the service's existing publish-image
action. The service's caller needs a push trigger on `main`. Without one, the
two pipelines do not deploy the same merge.

**Permissions.** Build and the deploy jobs ask for `id-token: write`. GitHub
refuses to start a run whose called jobs ask for more than the caller grants.
So the platform's own callers (the sample app, the app template, the examples
and the sandbox) are updated in the same release or before. The known
consumers are checked and told before release.

**Settings contract 1.1.** All additions are optional.

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

The Settings Check tool gets these changes:

- CHK-14 to CHK-20 are new and all Errors. CHK-19 limits environment names and
  `service.name` to lowercase letters, digits and hyphens, within a length
  limit. It applies only when `deploy` is set.
- CHK-20 fails a settings version newer than the pipeline supports, comparing
  versions as numbers. CHK-01 stays a Warning.

Existing 1.0 settings files behave exactly as today.

**Terraform modules.** Reusable modules under `terraform/aws/`, which
consumers apply in their own infrastructure repositories: the registry push
role, the deploy role and the pipeline-only ECR repositories. The OIDC
provider is looked up, and created only where none exists.

**Simulated stages.** Deploy and Verify become real only for services with
`deploy.targets`, and stop flagging themselves as simulated. Services without
`deploy.targets`, including the sample app and the release smoke test, stay
simulated.

**Run record.** It gains the digest, the target's previous and new task
definitions, the verification results, the rollback outcome, the run attempt
and the shared pipeline's own commit (`job.workflow_sha`, passed in as an
input). A run replaced by a newer one is recorded as SKIPPED, with the reason
superseded.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Hand over to the infrastructure repository's own workflow | Needs a cross-repository token, so a GitHub App or a personal token. Both conflict with standing decisions. Kept for later |
| Put pipeline images in the shared repositories, and have infrastructure filter out `dp-*` | Terraform's "most recent" image lookup cannot filter by tag, and an image copied into the shared Development repository would move all six services. A missed filter would ship a pipeline build to Production |
| Moving rollback tags (`dp-<env>-current` and `dp-<env>-previous`) | ECR tags are immutable in these repositories |
| The deploy role reads the API key to call `/health/` | Puts an application secret on the runner, and mixes deployment access with application access |
| Custom OIDC subject claims for main-only | Not needed for Development. Revisit when trust is pinned to the shared workflow before Production. The existing trusts use a `repo:…:*` wildcard, so they would probably still match |
| A `moved` block for the Terraform hand-over | It cannot be limited to one workspace |
| Rebuild the image per environment | What is tested would no longer be what is deployed |
| The pipeline manages the infrastructure too | Too much ownership and risk for a first step |

## Consequences
**Positive**

- No consumer secrets.
- The exact tested image is deployed.
- Deploys are checked independently and rolled back automatically.
- Pipeline images cannot reach other services or environments.
- The existing pipeline keeps working.

**Accepted for Development only**

- The handed-over service can run a different version from the five that share
  its image and database. Both pipelines deploy the same merge, usually within
  minutes. A failure or rollback leaves a longer gap.
- Migrations run on start in every service, and rollback cannot undo them. So
  migrations must be backward compatible. About six migrations a year are
  ones that old code cannot handle, for example new NOT NULL columns. We
  recommend that the service team adds a CI check for NOT NULL changes.
- Shared Redis values can be written by an older worker.
- The hydrate job runs the infrastructure repository's image.
- Until trust is pinned to the shared workflow before Production, another
  workflow in the same repository that uses the Development environment on
  `main` could reach the deploy role.

**Before the first `data-dashboard-api` deploy**, the infrastructure side must:

- add the pipeline-only repository and push role in the tools infrastructure
  repository, and the Development repository and deploy role;
- set the dev-only Terraform ignore and `track_latest = false`;
- do the state move;
- add the cluster-keyed restart skip;
- add the dev-only health route.

The service must return its commit from `/health/`.

We recommend narrowing the existing push role, which trusts every branch. This
does not block this work.

**Design sections that change when this lands:** Build, Deploy, Verify and
rollback; concurrency; the settings rules; consumer requirements (`base_url`
replaces the `DEPLOYMENT_BASE_URL_<NAME>` variables for deployed
environments); the run record; and identity and access.

## Later steps
Out of scope here. Each is proven in the sandbox first.

1. Every service that shares the image, deployed together.
2. Several Development environments.
3. One Pre-production environment, with migrations moved to a separate one-off
   task.
4. Several Pre-production environments.
5. Production, with the approval gate and trust pinned to the shared workflow.

Other arrangements are added as services need them.

## Open decisions
| ID | Question | Recommendation | Needed by |
|---|---|---|---|
| D5 | How consumers get the Terraform modules | A git source pinned by commit, with version tags | Proof of concept |
| D7 | How infrastructure stops Terraform resetting the service | Dev-only flags plus `track_latest = false`, with a state move and no `moved` block | First service |
| D10 | Which service and environment go first | `private-api` in `uhd-dev` | First service |
| D14 | Deploy timeout | 15 minutes by default, 30 at most; job timeout 70 minutes | Proof of concept |
| D15 | Who is told about failures, and who responds | The service team's channel; the Platform Team as backup | First service |
| D16 | How many images the pipeline-only repositories keep | The last 10 | Proof of concept |
| D17 | Whether an older image can replace a newer one | No, checked against SSM | First service |
| D18 | Can one service run ahead of the five sharing its image in `uhd-dev`? | Yes, for Development only, with the tech lead's sign-off. This includes migrations, the cache and the hydrate job | First service |
| D19 | Where the tools account's repository and push role live | **Decided:** the tools infrastructure repository | — |
| D20 | How Verify reaches a health endpoint behind an API key | An unauthenticated `/health/` route on the load balancer | First service |
| D21 | What happens when a deploy runs while Development is scaled to zero | Fail fast with "environment asleep" | First service |
| D22 | How a superseded run is recorded | SKIPPED, with the reason | First service |
