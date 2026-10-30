.PHONY: help check-settings test-pregate-local test-standard-pipeline-local install-hooks

ACT_RUNNER_IMAGE ?= catthehacker/ubuntu:act-latest
ACT_EVENT_FILE ?=

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-settings: ## Check a settings file is readable (SETTINGS=path/to/pipeline-settings.yml; schema validation pending)
	@python3 packages/setting-checker/checker.py --config "$(or $(SETTINGS),sample-app/.github/pipeline-settings.yml)" --mode pr --strict

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

install-hooks: ## Configure this repository to use the local Git hooks
	@git config core.hooksPath .githooks
	@echo "Git hooks enabled from .githooks/"
