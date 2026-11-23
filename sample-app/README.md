# Sample App

This directory is a placeholder application demonstrating the centralised
pipeline workflow. Its application-specific settings live in
`.github/pipeline-settings.yml` and are passed to the reusable workflow by
`.github/workflows/sample-app-pipeline.yml` in the repository root.

Its settings use a structured `test` block with two suites, `unit`
(`tests/unit/`) and `integration` (`tests/integration/`), which run as parallel
jobs. Both are placeholders: the app has no code yet, so they check the files
the build packages. The settings must pass the settings checker with
`--strict`.

The release smoke test (`.github/smoke-test-settings.yml`) covers the whole
Test stage on hosted runners. Its `test` block has a cached `setup` (it creates
`.test-cache/`, keyed on `.python-version`), the same two suites, each writing a
`.smoke-<suite>.done` file that `collect` gathers, and a `verify` final step
that checks both files arrived. The app-template keeps the `test_command`
shorthand with a placeholder test in `tests/test_placeholder.py`; replace it
with real tests when adopting the template.

The minimal `Dockerfile` allows the shared pipeline's build step to exercise
container image creation without publishing the image to a registry.

See the [consumer guide](../docs/consumer-guide.md) to adopt the pipeline, or
the [local development guide](../docs/local-development.md) to run this example.
