.PHONY: install check test test-all test-anvil test-ast test-audit test-edit test-init test-git test-smelt lint format security axm-audit axm-init quality ci docs-serve docs-build clean help

# 🚀 Workspace Management

install:  ## Install all dependencies
	uv sync --all-packages --all-groups

# 🧪 Testing

test-all:  ## Run ALL workspace tests (per package)
	@echo "🧪 Running ALL workspace tests (per package)..."
	@for pkg in axm-anvil axm-ast axm-audit axm-edit axm-init axm-git axm-smelt; do \
		echo "\n📦 Testing $$pkg..."; \
		uv run --package $$pkg --directory packages/$$pkg pytest || exit 1; \
	done

test-anvil:  ## Run axm-anvil tests
	@echo "🧪 Running axm-anvil tests..."
	uv run --package axm-anvil --directory packages/axm-anvil pytest

test-ast:  ## Run axm-ast tests
	@echo "🧪 Running axm-ast tests..."
	uv run --package axm-ast --directory packages/axm-ast pytest

test-audit:  ## Run axm-audit tests
	@echo "🧪 Running axm-audit tests..."
	uv run --package axm-audit --directory packages/axm-audit pytest

test-edit:  ## Run axm-edit tests
	@echo "🧪 Running axm-edit tests..."
	uv run --package axm-edit --directory packages/axm-edit pytest

test-init:  ## Run axm-init tests
	@echo "🧪 Running axm-init tests..."
	uv run --package axm-init --directory packages/axm-init pytest

test-git:  ## Run axm-git tests
	@echo "🧪 Running axm-git tests..."
	uv run --package axm-git --directory packages/axm-git pytest

test-smelt:  ## Run axm-smelt tests
	@echo "🧪 Running axm-smelt tests..."
	uv run --package axm-smelt --directory packages/axm-smelt pytest

# 🛡️ Quality Gates

# Le répertoire de tests est DÉRIVÉ du nom du package (tests_axm_<pkg>, cf. 9688417b0) :
# un renommage ou un nouveau package ne laisse pas de chemin littéral orphelin.
MYPY_PACKAGES := axm axm-mcp axm-anvil axm-ast axm-audit axm-edit axm-init axm-git \
                 axm-smelt axm-ingot axm-echo axm-config axm-vault axm-doctor

lint:  ## Linter + type checker
	uv run ruff check .
	uv run ruff format --check .
	@echo "🔍 Running mypy per package..."
	@for pkg in $(MYPY_PACKAGES); do \
		tests="packages/$$pkg/tests_$$(echo $$pkg | tr - _)"; \
		[ -d "$$tests" ] || { echo "❌ $$pkg: $$tests introuvable"; exit 1; }; \
		uv run --package $$pkg mypy --config-file packages/$$pkg/pyproject.toml \
			packages/$$pkg/src "$$tests" || exit 1; \
	done

format:  ## Auto-format code
	uv run ruff format .
	uv run ruff check --fix .

security:  ## Security audit (pip-audit)
	uv run pip-audit

check: lint test-all  ## Lint + type-check + tests

test: test-all  ## Run all workspace tests (alias)

# 🏅 AXM Quality Gates (mirrors CI axm-quality.yml)

axm-audit:  ## Run axm-audit on each package
	@for pkg in axm-anvil axm-ast axm-audit axm-edit axm-init axm-git axm-smelt; do \
		echo "\n🔍 Auditing $$pkg..."; \
		uv run --package axm-audit axm-audit audit packages/$$pkg --json || exit 1; \
	done

axm-init:  ## Run axm-init check on each package
	@for pkg in axm-anvil axm-ast axm-audit axm-edit axm-init axm-git axm-smelt; do \
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

## Test axm-ingot
test-axm-ingot:
	uv run pytest --package axm-ingot -q

## Lint axm-ingot
lint-axm-ingot:
	uv run ruff check packages/axm-ingot/src/axm_ingot/

## Test axm-echo
test-axm-echo:
	uv run pytest --package axm-echo -q

## Lint axm-echo
lint-axm-echo:
	uv run ruff check packages/axm-echo/src/axm_echo/
