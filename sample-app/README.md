# Sample App

This directory is a placeholder application demonstrating the centralised
pipeline workflow. Its application-specific settings live in
`.github/pipeline-settings.yml` and are passed to the reusable workflow by
`.github/workflows/sample-app-pipeline.yml` in the repository root.

Its settings run the sample app's unit tests with
`python3 -m unittest discover -s tests -v`, and must pass the settings checker
with `--strict`. The app-template uses the same command with a placeholder test
in `tests/test_placeholder.py`; replace it with real tests when adopting the
template.

The minimal `Dockerfile` allows the shared pipeline's build step to exercise
container image creation without publishing the image to a registry.
