# Release tag rulesets

Moving a tag changes the workflows and actions that consumers run, so tags are
protected by two repository rulesets. These files are definitions only; nothing
applies them automatically.

| File | Protects | Rules | Bypass actor |
| --- | --- | --- | --- |
| `release-tags.json` | `v*.*.*` (including `0.x`) | Block updates and deletion. | None |
| `floating-tags.json` | `v0`, `v0-canary`, `v1`, `v1-canary` | Block creation, updates and deletion. | A small team or role (must be set) |

The two rulesets must stay separate. A bypass actor skips every rule in its
ruleset, so adding one to the release-tags ruleset would let it move or delete
version tags too.

## Release tags

Consumers that pin to an exact version (for example `@v0.1.1`) must always get
the same workflows and actions, so release tags are immutable. The ruleset has
no creation rule and no bypass actors:

- Once created, a version tag can't be moved or deleted, by anyone.
- Anyone with write access, including the release, can create a new version
  tag. The ruleset can therefore be applied now without blocking releases.
- If a version tag is created outside a release, the release's duplicate-tag
  check will fail; a repository admin must disable the ruleset temporarily to
  remove the tag.

## Floating tags

Consumers use the floating major tag (for example `@v0`, later `@v1`) for
automatic updates, so only the release may create, move or delete floating
tags. Every release force-moves `v<MAJOR>-canary` and `v<MAJOR>`, so the
ruleset needs a bypass actor that the release can act as:

- The bypass actor is a small team or role, for example a platform maintainers
  team or the Repository admin role. Never use an individual user account.
- The release pushes with `RELEASE_TOKEN`, so the token's owner must be a
  member of that team or role. Otherwise releases cannot move the floating
  tags.
- Members of that team or role can also move floating tags manually, so keep
  it small.

## Apply

1. **Floating tags only, must set:** `actor_id` is `0` in
   `floating-tags.json`, which will not work. Set `actor_type` and `actor_id`
   to the bypass team or role (`Team` with the team's numeric ID, or
   `RepositoryRole` with the role's ID), and remove the "MUST SET" text from
   the ruleset's `name`. Confirm the release token's owner is a member first.
2. A repository admin applies each file, using either:
   - Settings, Rules, Rulesets, New ruleset, Import a ruleset; or
   - `gh api --method POST repos/UKHSA-Internal/devops-pipeline/rulesets --input scripts/rulesets/release-tags.json`
     (and the same for `floating-tags.json`).
3. If your plan supports it, first set `enforcement` to `evaluate` and check the
   ruleset insights after a release, then change it to `active`.
4. Do a release (or a test in a sandbox repository) and confirm that the
   `canary` and `promote` jobs can still push their tags.
