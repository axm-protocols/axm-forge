.PHONY: install check test test-all test-ast test-audit test-init test-git lint format security axm-audit axm-init quality ci docs-serve docs-build clean help

# 🚀 Workspace Management

install:  ## Install all dependencies
	uv sync --all-groups

# 🧪 Testing

test-all:  ## Run ALL workspace tests (per package)
	@echo "🧪 Running ALL workspace tests (per package)..."
	@for pkg in axm-ast axm-audit axm-init axm-git; do \
		echo "\n📦 Testing $$pkg..."; \
		uv run --package $$pkg --directory packages/$$pkg pytest || exit 1; \
	done

test-ast:  ## Run axm-ast tests
	@echo "🧪 Running axm-ast tests..."
	uv run --package axm-ast --directory packages/axm-ast pytest

test-audit:  ## Run axm-audit tests
	@echo "🧪 Running axm-audit tests..."
	uv run --package axm-audit --directory packages/axm-audit pytest

test-init:  ## Run axm-init tests
	@echo "🧪 Running axm-init tests..."
	uv run --package axm-init --directory packages/axm-init pytest

test-git:  ## Run axm-git tests
	@echo "🧪 Running axm-git tests..."
	uv run --package axm-git --directory packages/axm-git pytest

# 🛡️ Quality Gates

lint:  ## Linter + type checker
	uv run ruff check .
	uv run ruff format --check .
	@echo "🔍 Running mypy per package..."
	uv run --package axm-ast mypy --config-file packages/axm-ast/pyproject.toml packages/axm-ast/src packages/axm-ast/tests
	uv run --package axm-audit mypy --config-file packages/axm-audit/pyproject.toml packages/axm-audit/src packages/axm-audit/tests
	uv run --package axm-init mypy --config-file packages/axm-init/pyproject.toml packages/axm-init/src packages/axm-init/tests
	uv run --package axm-git mypy --config-file packages/axm-git/pyproject.toml packages/axm-git/src packages/axm-git/tests

format:  ## Auto-format code
	uv run ruff format .
	uv run ruff check --fix .

security:  ## Security audit (pip-audit)
	uv run pip-audit

check: lint test-all  ## Lint + type-check + tests

test: test-all  ## Run all workspace tests (alias)

# 🏅 AXM Quality Gates (mirrors CI axm-quality.yml)

axm-audit:  ## Run axm-audit on each package
	@for pkg in axm-ast axm-audit axm-init axm-git; do \
		echo "\n🔍 Auditing $$pkg..."; \
		uv run --package axm-audit axm-audit audit packages/$$pkg --json || exit 1; \
	done

axm-init:  ## Run axm-init check on each package
	@for pkg in axm-ast axm-audit axm-init axm-git; do \
		echo "\n🏗️ Checking $$pkg..."; \
		uv run --package axm-init axm-init check packages/$$pkg --json || exit 1; \
	done

quality: axm-audit axm-init  ## Full AXM quality gate (pre-push)

ci: install check quality  ## Full CI pipeline

# 📚 Documentation

docs-serve:  ## Preview docs locally
	uv run mkdocs serve

docs-build:  ## Build docs site
	uv run mkdocs build --strict

# 🧹 Cleanup

clean:  ## Clean artifacts
	rm -rf .venv
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true

help:  ## Show help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

.DEFAULT_GOAL := help
