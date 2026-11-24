# 7. Structured test settings with parallel suites

* **Status:** Approved
* **Date:** 2026-11-19

## Context
`service.test_command` is one string, so the Test stage is one step that runs
one command. The first consuming service's review asked for:

- its own CLI for tests;
- separate suites that are visible at a glance;
- suites that run in parallel;
- coverage without running the tests again.

That service is the only real consumer so far. The shape of the test settings
is set now, before other services copy it.

## Decision
Add a `service.test` block. It is part of settings file version 1.1 and is
additive: existing 1.0 files keep working.

- `suites` (required): 1 to 10 named suites, each with a single-line `command`.
  Names are lowercase letters, digits and hyphens, unique, at most 32
  characters.
- `setup` (optional): one single-line command that prepares the environment. It
  runs at the start of each suite job and of the final step.
- `collect` (optional): files each suite keeps for the final step.
- `final` (optional): a named command that runs only if every suite passed.

`test_command` stays valid, permanently. It is shorthand for one suite named
`test` with no setup or final step. Setting both `test` and
`test_command`, or neither, is an error.

The pipeline turns either form into one test plan, then runs:

- a "Test (suite)" job per suite, in parallel, with fail-fast off. Each sets up
  the language runtime, runs `setup` if set, runs the command and uploads its `collect` files and `test-results/*.xml`;
- a "Test (final step)" job that downloads those files and runs the final command.

A `Test` job gives the stage one result for Scan and the run record: PASSED only
if every suite and the final step passed. The run record keeps `steps.test` and
adds a `test_suites` list with each suite and the final step: its result, tests,
failures, errors, duration and coverage (null where not reported). Completed
suites stay listed when a run is cancelled.

Other decisions:

- Suites always run in parallel. A service that needs an order chains commands
  in one suite.
- At most 10 suites, to cap runner minutes.
- Results come from JUnit XML in `test-results/`, a convention, not a setting;
  they appear in the job summary (with up to 10 failed tests) and in
  `test_suites[]`.
- The pipeline times each suite and the final step itself.
- Failed tests are listed in the job summary (up to 10) from JUnit.
- Coverage is read from Cobertura XML at `test-results/coverage.xml`. Like
  JUnit, it's a convention, not a setting, and applies to any step.
- The pipeline never treats a step differently because of its name.
- Each settings file version lists the fields it introduced, and a test fails
  if a new field isn't added under a new version.
- Within a major pipeline version, settings changes are additive and optional.
  Existing files keep passing, enforced by the compatibility fixtures
  (`tests/fixtures/settings/compatibility/`). A breaking settings change needs
  a new major version (v2).
- New rules CHK-14 to CHK-18 are Errors. CHK-11 now applies only when
  `test_command` is set.
- CHK-14 rejects a settings version newer than the pipeline supports; 1.1 is
  the first version that needs it. Versions are compared as numbers by part, so
  1.10 is newer than 1.9.
- The release smoke test uses the structured settings, so every release
  exercises parallel suites, collected files and the final step on hosted
  runners.
- The sample app runs as two suites, `unit` and `integration`.

## Alternatives considered
- **Keep one string and add per-suite reports only.** Suites would be visible,
  but nothing would run in parallel or share a setup.
- **A `test_commands` list run in one job.** GitHub Actions can't create steps
  dynamically, so the suites still wouldn't be separate steps or jobs.
- **Caching the setup between jobs.** Deferred until run times show it's
  needed; it can be added later as an optional field without breaking existing
  settings.
- **Deprecating `test_command`.** It breaks small services for no gain.

## Consequences
- Faster wall-clock time and clear failures: each suite shows as its own job.
- More runner minutes: one job per suite, each running `setup` itself.
- A more complex shared workflow.
- The low-level design changes in sections 3.1 (Test), 4.1 (test settings and
  rules), 4.2 (optional test reports) and 4.4 (run record).
- Services that use `test` need the pipeline release that adds settings file
  version 1.1. From then on, CHK-14 stops a pipeline from running settings
  written for a newer settings file version than it understands.
- Services with `test_command` behave as before, as one suite. The app
  template stays on `test_command`. The sample app and the release smoke test
  use `test`, so the platform's own pipeline exercises parallel suites.
