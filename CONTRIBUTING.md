# Contributing to axm-forge

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups
uv run pre-commit install
```

## Making Changes

1. Create a branch: `git checkout -b feat/my-change`
2. Make changes in the relevant package under `packages/`
3. Run tests: `make test-all`
4. Run lint: `make lint`
5. Run AXM quality gate: `make quality`
6. Commit with conventional commits: `feat(pkg): description`
7. Open a pull request

> **💡 Tip:** `make quality` runs the same `axm-audit` + `axm-init check` that CI enforces via `axm-quality.yml`. Running it locally before pushing avoids CI failures.

## Available Commands

| Command | Description |
|---|---|
| `make test-all` | Run tests for all packages |
| `make test-{pkg}` | Run tests for a specific package (e.g. `make test-ast`) |
| `make lint` | Ruff + mypy for all packages |
| `make check` | Lint + tests |
| `make axm-audit` | Run axm-audit on each package |
| `make axm-init` | Run axm-init check on each package |
| `make quality` | Full AXM quality gate (pre-push) |

## Adding a Package

1. Create `packages/my-pkg/` with `pyproject.toml`, `src/`, `tests/`
2. UV auto-discovers members via `packages/*` glob
3. Run `uv sync` to update the lockfile
