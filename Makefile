.PHONY: help check-settings test-pregate-local test-standard-pipeline-local test-pipeline-failing-test test-pipeline-failing-check test-pipeline-settings-errors test-pipeline-settings-warnings install-hooks

ACT_RUNNER_IMAGE ?= catthehacker/ubuntu:act-latest
ACT_EVENT_FILE ?=
PYTHON ?= python3

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-settings: ## Validate a settings file with --strict (SETTINGS=path/to/pipeline-settings.yml)
	@$(PYTHON) packages/settings-checker/checker.py --settings "$(or $(SETTINGS),sample-app/.github/pipeline-settings.yml)" --strict

test-pregate-local: ## Run the platform pull-request pre-gate with act
	@if [ -n "$(ACT_EVENT_FILE)" ]; then \
		./act-run.sh pull_request -e "$(ACT_EVENT_FILE)" -W .github/workflows/pre-gate.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE); \
	else \
		event_file=$$(mktemp); \
		trap 'rm -f "$$event_file"' EXIT; \
		python3 scripts/contribution_rules.py local-event > "$$event_file"; \
		./act-run.sh pull_request -e "$$event_file" -W .github/workflows/pre-gate.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE); \
	fi

test-standard-pipeline-local: ## Run the reusable standard pipeline and local action with act
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=sample-app/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)

test-pipeline-failing-test: ## Run the pipeline against a failing unit test; expects a non-zero exit and downstream stages skipped
	@rm -f .act-artifacts/run-record.json
	@! ./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/failing-test/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"test": "FAILED"' .act-artifacts/run-record.json && grep -q '"scan": "SKIPPED"' .act-artifacts/run-record.json && echo "OK: test FAILED, downstream SKIPPED"

test-pipeline-failing-check: ## Run the pipeline with a missing settings file; expects check FAILED and downstream skipped
	@rm -f .act-artifacts/run-record.json
	@! ./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/does-not-exist.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"check": "FAILED"' .act-artifacts/run-record.json && grep -q '"test": "SKIPPED"' .act-artifacts/run-record.json && echo "OK: check FAILED, downstream SKIPPED"

test-pipeline-settings-errors: ## Run the pipeline with settings that have an error; expects check FAILED and downstream skipped
	@rm -f .act-artifacts/run-record.json
	@! ./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/settings/errors/missing-test-command.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"check": "FAILED"' .act-artifacts/run-record.json && grep -q '"test": "SKIPPED"' .act-artifacts/run-record.json && echo "OK: check FAILED on a settings error, downstream SKIPPED"

test-pipeline-settings-warnings: ## Run the pipeline with settings that have only warnings; expects every stage to pass
	@rm -f .act-artifacts/run-record.json
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/warnings-only-service/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"check": "PASSED"' .act-artifacts/run-record.json && grep -q '"test": "PASSED"' .act-artifacts/run-record.json && grep -q '"deploy": "PASSED"' .act-artifacts/run-record.json && echo "OK: check PASSED with warnings, later stages PASSED"

install-hooks: ## Configure this repository to use the local Git hooks
	@git config core.hooksPath .githooks
	@echo "Git hooks enabled from .githooks/"
