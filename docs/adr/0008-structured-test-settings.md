# 8. Structured test settings with parallel suites

* **Status:** Approved
* **Date:** 2026-11-19

## Context
`service.test_command` is one string, so the Test stage is one step that runs
one command. The first consuming service's review asked for:

- its own CLI for tests;
- separate suites that are visible at a glance;
- suites that run in parallel;
- no repeated environment setup in every run;
- coverage without running the tests again.

That service is the only real consumer so far. The shape of the test settings
is set now, before other services copy it.

## Decision
Add a `service.test` block. It is part of settings contract version 1.1 and is
additive: existing 1.0 files keep working.

- `suites` (required): 1 to 10 named suites, each with a single-line `command`.
  Names are lowercase letters, digits and hyphens, unique, at most 32
  characters.
- `setup` (optional): one single-line command that prepares the environment.
- `cache` (optional): `paths` and `key_files`, both required. The service
  names them, so caching works for any language.
- `collect` (optional): files each suite keeps for the final step.
- `final` (optional): a named command that runs only if every suite passed.

`test_command` stays valid, permanently. It is shorthand for one suite named
`test` with no setup, cache or final step. Setting both `test` and
`test_command`, or neither, is an error.

The pipeline turns either form into one test plan, then runs:

- a "Test setup" job, only when `cache` is set. It sets up the language
  runtime, restores the cache and, on a miss, runs `setup` and saves the cache.
  The key is the OS, architecture, language version, a hash of the setup
  command and a hash of the `key_files`;
- a "Test (suite)" job per suite, in parallel, with fail-fast off. Each runs the
  command and uploads its `collect` files and `test-results/*.xml`;
- a "Test (final)" job that downloads those files and runs the final command.

A `Test` job gives the stage one result for Scan and the run record: PASSED only
if every suite and the final step passed. The run record keeps `steps.test` and
adds a `test_suites` list with each suite's and the final step's result, test
counts and duration.

Other decisions:

- Suites always run in parallel. A service that needs an order chains commands
  in one suite.
- At most 10 suites, to cap runner minutes.
- JUnit XML in `test-results/` is a convention, not a setting.
- New rules CHK-20 to CHK-24 are Errors. CHK-20 fails Check when `version` is
  newer than the pipeline supports (1.1), for every settings file; versions are
  compared as numbers by part, so 1.10 is newer than 1.9. CHK-11 now applies
  only when `test_command` is set.

## Alternatives considered
- **Keep one string and add per-suite reports only.** Suites would be visible,
  but nothing would run in parallel or share a setup.
- **A `test_commands` list run in one job.** GitHub Actions can't create steps
  dynamically, so the suites still wouldn't be separate steps or jobs.
- **Python-specific caching.** It ties the pipeline to one language.
- **Deprecating `test_command`.** It breaks small services for no gain.

## Consequences
- Faster wall-clock time and clear failures: each suite shows as its own job.
- More runner minutes: a setup job plus one job per suite.
- A more complex shared workflow.
- The low-level design changes in section 3.1 (Test) and section 4.1 (rules).
- Services that use `test` need the pipeline release that adds contract 1.1.
  From then on, CHK-20 stops a pipeline from running settings written for a
  newer contract than it understands.
- Services with `test_command` behave as before, as one suite. The app
  template and the smoke test stay on `test_command`. The sample app uses
  `test` with `unit` and `integration` suites, so the platform's own pipeline
  exercises parallel suites.
