# Releasing the workflow package

This guide is for release operators. The workflow package comprises the
GitHub-discovered entrypoints under `.github/workflows/` and
`packages/shared-workflows/`; they are released together.

## Release flow

1. Change `packages/shared-workflows/VERSION` in a PR. The release workflow
   validates it in a [dry run](#release-dry-run).
2. When that change reaches `main`, the release creates a child commit that
   pins each shared composite action reference to the source commit, without
   updating `main`. It force-moves `v<MAJOR>-canary` to the pinned commit.
3. The [smoke test](#canary-smoke-test) runs the release commit's pipeline
   against the sample app.
4. If it passes, promotion asserts the canary still points at the pinned
   commit, creates `vX.Y.Z` there and force-moves `v<MAJOR>` to it. Promotion
   is automatic; there is no manual approval step.

From version `1.0.0` the aliases are `v1` and `v1-canary`. `v0` and
`v0-canary` stay on the last 0.x release and are no longer moved.
Consumers use a floating major tag or an exact version tag. See the
[consumer guide](consumer-guide.md) for action access and caller setup.

## Version checks and concurrency

The version must be strict SemVer (`MAJOR.MINOR.PATCH`), without build
metadata or a pre-release suffix, and `vMAJOR.MINOR.PATCH` must not already
exist. Other checks in `prepare`:

- **Downgrade guard:** the version must be higher than every existing
  `vX.Y.Z` tag with the same major. The duplicate-tag check runs first, so an
  equal version fails as a duplicate; a lower version (for example `0.0.0`)
  shows the downgrade error.
- **Unchanged version:** a `VERSION` edit counts as unchanged if the value is
  the same once trailing newlines are ignored. Other whitespace changes make
  the value fail strict SemVer.
- **Concurrency:** pushes to `main` share one `release-platform` queue and
  never cancel a running release. GitHub keeps only the latest queued run, so
  intermediate versions may be skipped. Dry runs use a separate group per ref
  (`release-platform-dry-run-<ref>`) and cannot displace a pending release.

## Promotion and recovery

- **Idempotent promotion:** if `vX.Y.Z` already points at the pinned commit,
  it is not recreated and `v<MAJOR>` is still moved. If the version tag points
  elsewhere, promotion fails.
- **Partial promotion:** use “Re-run failed jobs” to retry `promote` if, for
  example, the version tag was pushed but moving the major alias failed. Do
  not use “Re-run all jobs”: `prepare` rejects the existing version tag.
  Re-run only the most recent release; if a later release moved the canary,
  the assertion fails.
- **Smoke test failure:** no version tag is created and the major alias does
  not move. The canary remains on the failing commit until the next
  release. Releases trigger only when `VERSION` changes, so ship the fix under
  a new version.
- **Dry run:** promotion never runs.

TODO: decide whether promotion should also create a GitHub Release.

## Tag protection

The [ruleset definitions and application guide](../scripts/rulesets/README.md)
explain how to protect immutable release tags and restrict floating-tag
creation, updates and deletion. The floating-tag bypass actor must include the
release token's owner. These files are definitions; they are not applied
automatically.

## Release token

`RELEASE_TOKEN` is the permanent release identity: a classic personal access
token with `repo` and `workflow` scopes, authorised for SSO and stored only in
the `release` environment. That environment is restricted to `main`.

The pinned release commit changes a workflow file, which `GITHUB_TOKEN` cannot
push. The `canary` and `promote` jobs therefore push with `RELEASE_TOKEN` and
fail early if it is empty. No other job or dry run uses the environment or
token.

The token is owned by chrisp-burendo on behalf of the Platform Team. The team
must rotate it before expiry and replace it if the owner leaves: create a
classic token with the same scopes, authorise it for SSO and replace the
environment secret.

## Reading the release summary

The `Release summary` job runs when a push to `main` has passed `prepare` with
a changed version. It still runs if `canary`, `smoke-test` or `promote` fails
or is skipped, but not during dry runs, unchanged-version runs or failed
preparation. It reports the version, source and pinned commits, job results,
and whether each canary, version and major tag points at the pinned commit,
exists elsewhere or does not exist. A failed tag lookup fails the job.

## Canary smoke test

The release's `smoke-test` job calls the local `standard-pipeline.yml` with
`sample-app/.github/pipeline-settings.yml` after `canary` succeeds. The canary
points at a child commit whose action references are pinned to the source
commit. Promotion asserts that the canary points at that pinned commit. The
smoke test passes only if every pipeline stage passes.

For a manual check, run `smoke-test-pipeline.yml` using `workflow_dispatch`
in the Actions tab or with `gh workflow run smoke-test-pipeline.yml`. Unlike
the release smoke test, this calls `standard-pipeline.yml@v1-canary` and tests
the published canary. It has no other trigger. It runs inside the platform
repository and cannot catch every cross-repository problem, such as a
consumer's own token or permissions.

Dry runs skip the smoke test because they skip `canary`. The PR's own workflow
and action code is instead tested by `pre-gate.yml` and
`sample-app-pipeline.yml`, which use relative references from that checkout.

## Release dry run

`release-cicd-platform.yml` runs on PRs changing
`packages/shared-workflows/VERSION`, the release workflow or the manual smoke
test workflow. Any event other than a push to `main` is a read-only dry run:

- It compares the PR head's version with its base and reports “no release
  would run” if unchanged.
- It applies the normal version, duplicate-tag, downgrade and pre-1.0 checks.
- It derives aliases and writes planned tag commands, smoke test and promotion
  to the job summary.
- It never creates or moves tags, runs the smoke test or promotes. It does not
  test the PR's pipeline code; the pre-gate covers that.
