# Project instructions

Shared guidance for AI assistants in this repository. The Low Level Design
(LLD) on Confluence is the design reference. When a plan and a specification
disagree, the specification wins.

## Working in this repo

- Use the LLD's terms (for example stage, artifact, Settings Check tool). Don't introduce synonyms or rename established concepts. If a term seems wrong, raise it as an LLD change.
- Documentation and tests are part of every change.
- Follow CONTRIBUTING.md for branch names (`<type>/<jira-key>/<description>`),
  commits and pull requests.
- Settings changes must be backward compatible: existing settings files keep
  working.
- Keep shared code free of anything specific to one service. A guard test
  enforces this.
- Keep the toolchain minimal: local work needs only Python and Docker (`act`).
  Use no monorepo build tools and no global installs.

## Standing decisions: don't change these without asking

### Consumers

- A service's whole interface is one caller workflow and one settings file.
  `settings_path` is the only input, and consumers pass no secrets.
- The caller's tag is the only version selector. Settings files carry no
  pipeline version.
- Consumers use the floating major tag (`@v1`), and may pin an exact version.
  They never use `-canary` tags.
- The platform repository is public, with Actions access set to organisation
  level, so any repository can call it.
- The environment categories are `Development`, `Pre-production` and
  `Production`. Services name their own environments within a category, and a
  category can hold several.
- A consuming service provides:
  - the settings file;
  - a multi-stage `Dockerfile` and a `.dockerignore`, building from source;
  - a health endpoint;
  - a language version file (`.python-version`, `.nvmrc` or `.node-version`).

### Pipeline behaviour

- The central workflow fixes the order of stages. Services configure what runs,
  never the sequence.
- Pull requests run Check, Test and Scan only. Only `main` builds and deploys.
- Every stage writes a `[STEP: <NAME>]` log marker.
- A run record is written on every outcome. Stage values are `PASSED`, `FAILED`
  or `SKIPPED`, and timestamps are ISO 8601 in UTC.
- Recovery is always a redeployment of a previously verified artifact. Never
  write destructive rollback, undeploy or database-reversal steps.
- Production approval follows `deploy.production.approval_mode`
  (`all-approvers`, `single-approver` or `unattended`), as LLD section 5.2
  describes.

### Settings checker

- Rules live in `packages/settings-checker/rules.py`. Each has an ID (CHK-nn),
  a severity and a message.
- Severities:
  - an Error stops the run at Check;
  - a Warning is reported but never blocks.
- The current rules are CHK-01 to CHK-13, with the severities set out in LLD section 4.1.
- Modes:
  - default: used in pipelines; fails on errors;
  - `--strict`: used by the pre-gate and local runs; fails on warnings too;
  - `--report-only`: never fails.
- Errors have no waivers. The `unattended` Architecture Exception is the only
  exception route. A warning becomes an error only by ADR.

### Releases

- Each component is versioned independently with SemVer.
  - The workflow package version lives in `packages/shared-workflows/VERSION`.
  - A release happens only when a version file changes.
- Releases go canary first:
  1. create the pinned release commit and move the canary to it;
  2. run the smoke test;
  3. on success, promote automatically to `vX.Y.Z` and the floating major tag;
  4. delete the canary.
- Release pushes use `RELEASE_TOKEN`. It's a classic token with the `repo` and
  `workflow` scopes, held in the `main`-only `release` environment. There is
  no GitHub App.
- Release tags are immutable, and only the release moves floating tags. Both
  rulesets are in `scripts/rulesets/`.
- The workflow package creates no GitHub Releases; tags are the record of its
  versions. (The Settings Check tool is distributed on a GitHub Release.)
- New composite actions live under `packages/shared-workflows/actions/`, so the
  release pinning covers them.

### Decisions and documentation

- A breaking change needs an ADR; the pre-gate's ADR gate enforces this. Write
  one ADR per significant change, not one per decision.
- Smaller decisions go in the project's decision log on Confluence, not in this
  repo.
- Keep the README, CONTRIBUTING.md and `docs/` in step with every change. The
  examples in `docs/examples/` are checked by the pre-gate.
