# Sample App

This directory is a placeholder application demonstrating the centralised
pipeline workflow. Its application-specific settings live in
`.github/pipeline-settings.yml` and are passed to the reusable workflow by
`.github/workflows/sample-app-pipeline.yml` in the repository root.

The minimal `Dockerfile` allows the shared pipeline's build stage to exercise
container image creation without publishing the image to a registry.
