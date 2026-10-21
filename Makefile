.PHONY: help check-settings test-workflow-local install-hooks

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-settings: ## Validate .github/pipeline-settings.yml locally
	@python3 standards-check-tool/checker.py --config .github/pipeline-settings.yml --mode pr

test-workflow-local: ## Run GitHub Actions locally with act (ARGS="pull_request -W .github/workflows/pre-gate.yml")
	@./act-run.sh $(ARGS)

install-hooks: ## Configure this repository to use the local Git hooks
	@git config core.hooksPath .githooks
	@echo "Git hooks enabled from .githooks/"
