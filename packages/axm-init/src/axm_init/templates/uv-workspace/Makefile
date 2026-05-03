.PHONY: install check lint format test audit clean docs-serve docs-build type-check help

# 🚀 Workspace Management

install:  ## Install all dependencies
	uv sync --all-groups

# 🛡️ Quality Gates

lint:  ## Linter + format check
	uv run ruff check .
	uv run ruff format --check .

format:  ## Auto-format code
	uv run ruff format .

type-check:  ## Run mypy across packages
	uv run mypy packages/

audit:  ## Security audit
	uv run pip-audit

# 🧪 Testing

test:  ## Run all workspace tests
	uv run pytest packages/ -q

# 📚 Documentation

docs-serve:  ## Serve documentation locally
	uv run mkdocs serve

docs-build:  ## Build documentation
	uv run mkdocs build

# ✅ Aggregate

check:  ## Full quality gate (lint + type-check + test)
	$(MAKE) lint
	$(MAKE) type-check
	$(MAKE) test

# 🧹 Housekeeping

clean:  ## Remove build artifacts
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .ruff_cache -exec rm -rf {} +
	rm -rf dist/ build/ *.egg-info site/

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
