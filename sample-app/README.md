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

The release smoke test (`.github/smoke-test-settings.yml`) keeps the
`test_command` shorthand, `python3 -m unittest discover -s tests -v`, which
finds both suites as one. The app-template uses the same command with a
placeholder test in `tests/test_placeholder.py`; replace it with real tests
when adopting the template.

The minimal `Dockerfile` allows the shared pipeline's build step to exercise
container image creation without publishing the image to a registry.

See the [consumer guide](../docs/consumer-guide.md) to adopt the pipeline, or
the [local development guide](../docs/local-development.md) to run this example.
