# 7. Deploy to Externally Managed Infrastructure on AWS

* **Status:** Proposed
* **Date:** 2026-11-18

## Context
The Deploy and Verify stages are placeholders. The run record flags them as
simulated stages.

The first consumer service builds one ARM64 image. It runs as six ECS Fargate
services in each environment. They share one database, and every service runs
migrations when it starts.

Its infrastructure repository manages the cluster, network and database. That
repository also deploys the services today. On every merge to the service, it
picks the newest image from a shared tools ECR repository, applies Terraform
and restarts the services in every environment, Production included. The ECR
tags are immutable, and only 5 images are kept.

These standing decisions still apply:

- Consumers pass no secrets.
- There is no GitHub App.
- Shared code holds nothing specific to one service.
- Existing settings files must keep working.
- Recovery is always a redeployment of a previously verified artifact.

## Decision
**Scope.** The first step is one image, deployed to one ECS service
(`private-api`) in one Development environment (`uhd-dev`). It is proven in the
sandbox first.

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

**Main-only.** This is enforced four ways:

- The workflow deploys only on a push to `main`. Today any run that is not a
  pull request deploys Development.
- The default OIDC subjects.
- The environment's branch policy, set to `main` only.
- The engine refuses to deploy unless the run is a push to `main` and the
  environment exists with that branch policy.

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

The infrastructure repository lets `/health/` through its load balancer
without the API key, so no application secret reaches the runner.

**Rollback.** Before each deploy, the pipeline records the current task
definition and its image digest in SSM. On a failed check, it confirms that
image still exists, restores that task definition, records where it came from,
and still fails the stage. If another deploy has replaced this one, the
pipeline reports it as superseded and does not roll back. The database is
never rolled back.

**Running alongside the existing pipeline.**

| Item | Label |
|---|---|
| Images | `dp-<commit-sha>`, in the pipeline-only repositories |
| Task definitions | Tagged `deployed-by=devops-pipeline`, with the commit and run ID |
| Version record | SSM `/devops-pipeline/<service>/<env>/version` |

The infrastructure repository stops deploying the one service in `uhd-dev`
only. Terraform ignores that service's task definition, and the restart script
skips it when the environment is dev.

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

- CHK-14 to CHK-19 are new and all Errors. CHK-19 limits environment names and
  `service.name` to lowercase letters, digits and hyphens, within a length
  limit.
- CHK-01 now fails a settings version newer than the pipeline supports.

Existing 1.0 settings files behave exactly as today.

**Terraform modules.** Reusable modules under `terraform/aws/`, which consumers
apply themselves: the OIDC provider, the registry push role, the deploy role
and the pipeline-only ECR repositories.

**Simulated stages.** Deploy and Verify become real only for services with
`deploy.targets`, and stop flagging themselves as simulated. Services without
`deploy.targets`, including the sample app and the release smoke test, stay
simulated.

**Run record.** It gains the digest, the target's previous and new task
definitions, the verification results, the rollback outcome, the run attempt
and the shared pipeline's own commit (`job_workflow_sha`). Concurrency is keyed
on service and environment.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Hand over to the infrastructure repository's own workflow | Needs a cross-repository token, so a GitHub App or a personal token. Both conflict with standing decisions. Kept for later |
| Put pipeline images in the shared repositories, and have infrastructure filter out `dp-*` | Terraform's "most recent" image lookup cannot filter by tag, and an image copied into the shared Development repository would move all six services. A missed filter would ship a pipeline build to Production |
| Moving rollback tags (`dp-<env>-current` and `dp-<env>-previous`) | ECR tags are immutable in these repositories |
| The deploy role reads the API key to call `/health/` | Puts an application secret on the runner, and mixes deployment access with application access |
| Custom OIDC subject claims for main-only | They apply to the whole repository, and would break the existing pipeline's AWS trust |
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
  migrations must be backward compatible.
- Until trust is pinned to the shared workflow before Production, another
  workflow in the same repository that uses the Development environment on
  `main` could reach the deploy role.

**Before the first deploy**, the infrastructure repository must:

- create the pipeline-only repositories and roles;
- add the Terraform ignore;
- add the dev-only restart skip;
- add the health route.

The service must return its commit from `/health/`.

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
| ID | Question | Recommendation |
|---|---|---|
| D5 | How consumers get the Terraform modules | A git source pinned by commit, with version tags |
| D7 | How infrastructure stops Terraform resetting the service | `ignore_task_definition_changes` on that service's module only, with a `moved` block, planned in `uhd-dev` first |
| D10 | Which service and environment go first | `private-api` in `uhd-dev` |
| D14 | Deploy timeout | 15 minutes by default, 30 at most; job timeout 70 minutes |
| D15 | Who is told about failures, and who responds | The service team's channel; the Platform Team as backup |
| D16 | How many images the pipeline-only repositories keep | The last 10 |
| D17 | Whether the staleness gate stops an older queued run | Yes |
| D18 | Can one service run ahead of the five sharing its image in `uhd-dev`? | Yes, for Development only, with the tech lead's sign-off |
| D19 | Where the tools account's repository and push role live | Unknown: ask the tools account's owner |
| D20 | How Verify reaches a health endpoint behind an API key | An unauthenticated `/health/` route on the load balancer |
