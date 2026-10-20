# 1. Monorepo Workspace Scaffold

* **Status:** Accepted
* **Date:** 2026-10-20

## Context
A central monorepo is required to house shared pipeline workflows, governance validation tools, reference starter templates, and test fixtures.

## Decision
Structure the workspace as a single monorepo separating `./central-pipeline-workflows`, `./standards-check-tool`, `./starter-template`, and `./sample-microservice` while providing root workflow proxy entrypoints under `.github/workflows/`.

## Consequences
Enables isolated component development and component-prefixed tagging (e.g., `checker/v1.0.0`) without third-party monorepo tools.
