# 7. Deploy to Externally Managed Infrastructure on AWS

* **Status:** Proposed
* **Date:** 2026-11-18

## Context
The Deploy and Verify stages are placeholders. The run record flags them as
simulated stages.

The first consumer service runs on AWS ECS Fargate. Its cluster, network and
database are managed in a separate infrastructure repository, which also
deploys the service today. That deploy picks the newest image and sends it to
every environment. It has no link to the commit that triggered the run.

These standing decisions still apply:

- Consumers pass no secrets.
- There is no GitHub App.
- Shared code holds nothing specific to one service.
- Existing settings files must keep working.
- Recovery is always a redeployment of a previously verified artifact.

## Decision
**Scope.** The first step is one image, deployed to one Development environment
on AWS ECS. It is proven in the sandbox before any real service uses it.

**Ownership.** The pipeline owns the application deploy only. The cluster,
network, database and task definition settings stay in the service's
infrastructure repository. A deploy changes only the image. Every other task
definition setting stays as the infrastructure repository set it.

**Access.** GitHub OIDC only, using AWS's official actions, pinned.

| Role | Account | Trusts |
|---|---|---|
| Registry push | Tools | The service repository, on `main` only |
| Deploy | Development | That repository's Development GitHub environment |

Main-only is enforced three ways: the default OIDC subjects, the environment's
branch policy (`main` only), and the engine refusing anything that is not
`main` and the shared workflow.

**Build once, promote by digest.**

- On `main`, Build pushes `dp-<commit-sha>` to the tools ECR and records the
  digest.
- Deploy copies that exact image into the environment's ECR.
- The digest replaces the `.sha256` checksum gate.
- Pull requests and feature branches never build to a registry or deploy.

**Deploy engine.** A new Python package, `packages/deploy-engine/`. It has
`publish`, `deploy`, `verify` and `rollback` commands and a provider model.
`aws` is the first provider and `aws.ecs` the first target type. Composite
actions stay thin wrappers around it.

**Verify.** Verify checks independently that:

- every running task uses the expected digest;
- the service's live task definition is the one this run registered;
- the health endpoint returns the deployed commit, in the field set by
  `verification.version_field` (default `commit_sha`).

**Rollback.** On a failed check, the pipeline restores the previous task
definition, whatever created it, and records where it came from. The stage
still fails, so later environments do not run. If another deploy has replaced
this one, the pipeline reports it as superseded and does not roll back. The
database is never rolled back, so migrations must be backward compatible.

**Running alongside the existing pipeline.** Everything the pipeline creates is
labelled as its own.

| Item | Label |
|---|---|
| Images | `dp-<commit-sha>` |
| Rollback images | `dp-<env>-current` and `dp-<env>-previous` |
| Task definitions | Tagged `deployed-by=devops-pipeline`, with the commit and run ID |
| Version record | SSM `/devops-pipeline/<service>/<env>/version` |

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

New rules CHK-14 to CHK-19 are all Errors. Existing 1.0 settings files behave
exactly as today.

**Terraform modules.** Reusable modules under `terraform/aws/`, which consumers
apply themselves: the OIDC provider, the registry push role, the deploy role
and the ECR protection rules.

**Simulated flag.** When Deploy and Verify become real, their actions drop the
simulated flag. The run record and the README's list of simulated stages stop
listing them.

## Alternatives considered
| Option | Why not chosen |
|---|---|
| Hand over to the infrastructure repository's own workflow | Needs a cross-repository token, which means a GitHub App or a personal token. Both conflict with standing decisions. Kept as a later option for services that need it |
| The pipeline manages the infrastructure too | Too much ownership and risk for a first step. Infrastructure stays where it is |
| A separate tools ECR repository for pipeline images | Workable, but more set-up. The `dp-` labelling keeps the two apart. Kept as the fallback |
| Custom OIDC subject claims to enforce main-only | They apply to the whole repository, and would break the existing pipeline's AWS trust |
| Rebuild the image for each environment | What is tested would no longer be what is deployed |

## Consequences
**Positive**

- No consumer secrets.
- The exact tested image is deployed.
- Deploys are checked independently and rolled back automatically.
- The existing pipeline keeps working during the transition.

**Negative or accepted**

- The infrastructure team must change its scripts first. It excludes `dp-*`
  images from its "newest image" selection, stops deploying the handed-over
  service, and applies the roles.
- Until trust is pinned to the shared workflow (before Production), another
  workflow in the same repository that uses the Development environment on
  `main` could reach the deploy role. This is accepted for Development only. The
  branch policy, CODEOWNERS and a narrowly scoped role reduce the risk.
- Health endpoints that GitHub runners cannot reach get only the running-image
  check.

**Design sections that change when this lands:** Build, Deploy, Verify and
rollback; the settings rules; consumer requirements (`base_url` replaces the
`DEPLOYMENT_BASE_URL_<NAME>` variables for deployed environments); the run
record; and identity and access.

## Later steps
Out of scope here. Each is proven in the sandbox first.

1. Several Development environments.
2. One Pre-production environment.
3. Several Pre-production environments.
4. Production, with the approval gate and trust pinned to the shared workflow.

Other arrangements are added as services need them: Lambda and more images,
handover, infrastructure kept in the service repository, other clouds, and
ephemeral environments for pull requests.

## Open decisions
| ID | Question | Recommendation |
|---|---|---|
| D5 | How consumers get the Terraform modules | A git source pinned by commit, with version tags |
| D7 | How infrastructure stops Terraform resetting the service | Terraform ignores that service's image |
| D10 | Which service goes first | `private-api`, whose Development endpoint is public |
| D14 | Deploy timeout | 15 minutes by default, 30 at most; job timeout 70 minutes |
| D15 | Who is told about failures, and who responds | The service team's channel; the Platform Team as backup |
| D16 | How many `dp-` images the tools ECR keeps | About the last 30; rollback images protected separately |
| D17 | Whether the staleness gate stops an older queued run | Yes: only the latest main commit deploys |
