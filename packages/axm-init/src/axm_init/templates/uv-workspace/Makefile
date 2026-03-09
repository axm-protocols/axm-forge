.PHONY: test-all lint-all docs-serve clean

## Run tests for all packages
test-all:
	uv run pytest packages/ -q

## Lint all packages
lint-all:
	uv run ruff check src/ packages/
	uv run ruff format --check src/ packages/

## Format all packages
format:
	uv run ruff format src/ packages/

## Serve documentation locally
docs-serve:
	uv run mkdocs serve

## Build documentation
docs-build:
	uv run mkdocs build

## Run type checks
type-check:
	uv run mypy packages/

## Full quality check
check:
	$(MAKE) lint-all
	$(MAKE) type-check
	$(MAKE) test-all

## Clean build artifacts
clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	rm -rf dist/ build/ *.egg-info
