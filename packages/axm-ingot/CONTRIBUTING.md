# Contributing to axm-ingot

Thanks for your interest in contributing!

## Development setup

`axm-ingot` is part of the [**axm-forge**](https://github.com/axm-protocols/axm-forge)
workspace and has **no package-local `Makefile`** — all commands run from the
workspace root:

```bash
git clone https://github.com/axm-protocols/axm-forge.git
cd axm-forge
uv sync --all-groups

# Run this package's suite
uv run --package axm-ingot --directory packages/axm-ingot pytest -x -q
```

To lint and type-check every workspace package at once, use the root `Makefile`
target from the workspace root:

```bash
make check  # lint + type-check + tests, across every package
```

## Pull requests

- Follow Conventional Commits for commit messages.
- Run `make check` (from the workspace root) before opening a PR.
- Add tests for new features and bug fixes.
