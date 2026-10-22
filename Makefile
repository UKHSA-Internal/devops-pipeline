.PHONY: help check-settings test-pregate-local test-standard-pipeline-local install-hooks

ACT_RUNNER_IMAGE ?= catthehacker/ubuntu:full-latest

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-settings: ## Check a settings file is readable (SETTINGS=path/to/pipeline-settings.yml; schema validation pending)
	@python3 standards-check-tool/checker.py --config "$(or $(SETTINGS),.github/pipeline-settings.yml)" --mode pr --strict

test-pregate-local: ## Run the platform pull-request pre-gate with act
	@./act-run.sh pull_request -W .github/workflows/pre-gate.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)

test-standard-pipeline-local: ## Run the reusable standard pipeline and local action with act
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=.github/pipeline-settings.yml --input use_local_action=true -P ubuntu-latest=$(ACT_RUNNER_IMAGE)

install-hooks: ## Configure this repository to use the local Git hooks
	@git config core.hooksPath .githooks
	@echo "Git hooks enabled from .githooks/"
