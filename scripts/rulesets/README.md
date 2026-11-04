# Release tag rulesets

Moving a release tag changes both the workflows and the actions that consumers
run, so release tags are protected with repository rulesets. These files are
definitions only; nothing applies them automatically.

| File | Protects | Rules |
| --- | --- | --- |
| `release-tags.json` | `v*.*.*` (including `0.x`) | Block updates and deletion. Creation is limited to the bypass actor. |
| `floating-tags.json` | `v0`, `v0-canary`, `v1`, `v1-canary` | Creation, updates and deletion are limited to the bypass actor. |

The bypass actor must be the identity the release workflow pushes tags with.
Nobody else can create release tags or create, move or delete floating tags.

The bypass actor is needed to **create** `v0` and `v0-canary` on the first
release, and `v1` and `v1-canary` at the 1.0.0 cut-over. Without it, those
first pushes are rejected. Until the cut-over, nobody else can create `v1` or
`v1-canary`.

Apply both rulesets **before the 1.0.0 cut-over**, and preferably before the
first release.

## Apply

1. **Must replace:** `actor_id` is `0` in both files, which is a placeholder
   and will not work. Set it to the numeric ID of the bypass actor (see
   [Bypass actor](#bypass-actor)) before applying.
2. Apply each file as an admin, using either:
   - Settings, Rules, Rulesets, New ruleset, Import a ruleset; or
   - `gh api --method POST repos/UKHSA-Internal/devops-pipeline/rulesets --input scripts/rulesets/release-tags.json`
     (and the same for `floating-tags.json`).
3. If your plan supports it, first set `enforcement` to `evaluate` and check the
   ruleset insights after a release, then change it to `active`.
4. Do a release (or a test in a sandbox repository) and confirm that the
   `canary` and `promote` jobs can still push their tags.

A manual bootstrap or repair of a floating tag needs an admin who can bypass the
ruleset.

## Bypass actor

TODO: confirm whether the default `GITHUB_TOKEN` can be a ruleset bypass actor,
or whether a GitHub App token is needed. The bypass list only offers repository
roles, teams, deploy keys and GitHub Apps, and the built-in `GITHUB_TOKEN`
identity may not be selectable. Until this is confirmed, the definitions use
`Integration` (GitHub App) with a placeholder ID.

If a GitHub App is needed, the release workflow would need these changes:

- Install the App on this repository with `Contents: Read and write`, and add
  it as the bypass actor in both rulesets.
- Store the App ID and private key as an Actions variable and secret.
- In the `canary` and `promote` jobs, create an installation token (for
  example with `actions/create-github-app-token`) and use it for checkout and
  the tag pushes instead of `GITHUB_TOKEN`. Pinning third-party actions is a
  separate piece of work.
- Keep `prepare` and `summary` read-only.

Do not use a long-lived personal access token.
