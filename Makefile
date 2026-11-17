.PHONY: help check-settings test-pregate-local test-standard-pipeline-local test-pipeline-failing-test test-pipeline-failing-check test-pipeline-settings-errors test-pipeline-settings-warnings test-pipeline-approval-modes test-pipeline-node test-pipeline-missing-version-file test-pipeline-unsupported-language test-pipeline-pinned-python-version install-hooks

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

test-pipeline-approval-modes: ## Run the pipeline on a simulated push to main in each approval mode; asserts which approval jobs run (act cannot approve)
	@mkdir -p .act-artifacts
	@printf '{"ref":"refs/heads/main"}' > .act-artifacts/push-main-event.json
	@set -eu; \
	run_mode() { \
		mode=$$1; log=".act-artifacts/approval-$$mode.log"; \
		./act-run.sh push -W tests/fixtures/approval-modes/caller.yml -e .act-artifacts/push-main-event.json \
			--var SETTINGS_PATH=tests/fixtures/approval-modes/.github/$$mode.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE) > "$$log" 2>&1 \
			|| { cat "$$log"; echo "FAIL: $$mode run failed"; exit 1; }; \
	}; \
	expect() { grep -q -- "$$2" ".act-artifacts/approval-$$1.log" || { echo "FAIL: $$1: expected '$$2'"; exit 1; }; }; \
	expect_not() { ! grep -q -- "$$2" ".act-artifacts/approval-$$1.log" || { echo "FAIL: $$1: unexpected '$$2'"; exit 1; }; }; \
	run_mode all-approvers; \
	expect all-approvers 'Approve Production (production-approval-platform-leads).*Job succeeded'; \
	expect all-approvers 'Approve Production (production-approval-security-leads).*Job succeeded'; \
	expect all-approvers 'STEP: APPROVAL\] production-approval-platform-leads approved for group(s): platform-leads'; \
	expect all-approvers 'STEP: APPROVAL\] production-approval-security-leads approved for group(s): security-leads'; \
	expect all-approvers 'Deploy Production (prod).*Job succeeded'; \
	echo "OK: all-approvers: one approval job per group, then Production"; \
	run_mode single-approver; \
	expect single-approver 'Approve Production (production-approval).*Job succeeded'; \
	expect single-approver 'STEP: APPROVAL\] production-approval approved for group(s): platform-leads, security-leads'; \
	expect_not single-approver 'production-approval-platform-leads'; \
	expect single-approver 'Deploy Production (prod).*Job succeeded'; \
	echo "OK: single-approver: one approval job, then Production"; \
	run_mode unattended; \
	expect unattended 'unattended Production deployment under exception EXC-0001'; \
	expect_not unattended 'Approve Production'; \
	expect unattended 'Deploy Production (prod).*Job succeeded'; \
	echo "OK: unattended: no approval jobs, Production runs"

test-pipeline-node: ## Run the pipeline against a Node service; expects Node set up from .nvmrc and every stage to pass
	@rm -f .act-artifacts/run-record.json
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/node-service/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"test": "PASSED"' .act-artifacts/run-record.json && echo "OK: Node runtime set up, test PASSED"

test-pipeline-missing-version-file: ## Run the pipeline for a python service with no .python-version; expects test FAILED and downstream skipped
	@rm -f .act-artifacts/run-record.json
	@! ./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/missing-version-file/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"test": "FAILED"' .act-artifacts/run-record.json && grep -q '"scan": "SKIPPED"' .act-artifacts/run-record.json && echo "OK: missing version file FAILED test, downstream SKIPPED"

test-pipeline-unsupported-language: ## Run the pipeline for an unsupported language; expects no runtime set up and every stage to pass
	@rm -f .act-artifacts/run-record.json
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/unsupported-language/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"test": "PASSED"' .act-artifacts/run-record.json && echo "OK: no runtime set up, test PASSED"

test-pipeline-pinned-python-version: ## Run the pipeline for a python service pinned to 3.12 via .python-version; expects test PASSED
	@rm -f .act-artifacts/run-record.json
	@./act-run.sh workflow_call -W .github/workflows/standard-pipeline.yml --input settings_path=tests/fixtures/pinned-python-version/.github/pipeline-settings.yml -P ubuntu-latest=$(ACT_RUNNER_IMAGE)
	@grep -q '"test": "PASSED"' .act-artifacts/run-record.json && echo "OK: pinned python version set up from .python-version, test PASSED"

install-hooks: ## Configure this repository to use the local Git hooks
	@git config core.hooksPath .githooks
	@echo "Git hooks enabled from .githooks/"
