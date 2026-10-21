.PHONY: help check-settings

help: ## Show available targets
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z_-]+:.*## / {printf "  %-18s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

check-settings: ## Validate .github/pipeline-settings.yml locally
	@python3 standards-check-tool/checker.py --config .github/pipeline-settings.yml --mode pr
