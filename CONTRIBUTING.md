# Contributing to axm-init

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm-init.git
cd axm-init
uv sync --all-groups
```

## Running Tests

```bash
uv run pytest              # full suite
uv run pytest -x -q        # stop on first failure
uv run pytest --cov        # with coverage report
uv run pytest -m slow      # real Copier scaffold tests (~15s)
```

## Code Quality

All contributions must pass the quality gate:

```bash
uv run ruff check src/ tests/   # lint
uv run ruff format src/ tests/  # format
uv run mypy src/ tests/         # type check
uv run axm-init check .         # governance (score ≥ 90 to pass)
```

Or use the Makefile shortcuts:

| Command | Description |
|---------|-------------|
| `make check` | Lint + type-check + tests |
| `make lint` | Ruff + MyPy |
| `make format` | Auto-format with Ruff |
| `make docs-serve` | Local docs preview |

## Code Conventions

- `from __future__ import annotations` in every module
- Explicit `__all__` in public modules
- Google-style docstrings on all public functions and classes
- Type annotations on all function signatures
- `Annotated` types for CLI parameters (cyclopts)

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance (deps, CI, config)
- `test:` — adding or updating tests
- `refactor:` — code change that neither fixes a bug nor adds a feature

**Breaking changes:** add `!` after the type, e.g. `feat!: remove --template flag`.

## Documentation

Documentation lives in `docs/` and follows the [Diátaxis](https://diataxis.fr) framework:

| Quadrant | Path | Purpose |
|---|---|---|
| Tutorials | `docs/tutorials/` | Learning-oriented, guided lessons |
| How-to | `docs/howto/` | Task-oriented, solve a specific problem |
| Reference | `docs/reference/` | Auto-generated API reference (mkdocstrings) |
| Explanation | `docs/explanation/` | Understanding-oriented, concepts and design |

- **API reference** — auto-generated from docstrings. Edit source code, not `docs/reference/` files
- **Other pages** — edit markdown files in `docs/`, update `mkdocs.yml` nav when adding pages

## Pull Request Checklist

1. Write tests first (TDD)
2. Run `make check` — all tests pass, no lint errors
3. Ensure `uv run axm-init check .` passes (Grade A or B)
4. Keep commits atomic and conventional
5. Update docs if user-facing

## Reporting Issues

- **Code bugs** — open a GitHub issue with reproduction steps
- **Doc issues** — open a GitHub issue with the label `documentation`
- **Security vulnerabilities** — email the maintainer directly (do not open a public issue)

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 license.
