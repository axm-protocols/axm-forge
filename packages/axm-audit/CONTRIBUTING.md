# Contributing to axm-audit

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm-audit.git
cd axm-audit
uv sync --all-groups
```

## Running Tests

```bash
uv run pytest              # full suite (~336 tests)
uv run pytest -x -q        # stop on first failure
uv run pytest --cov        # with coverage report
```

## Code Quality

All contributions must pass the quality gate:

```bash
uv run ruff check src/ tests/   # lint
uv run ruff format src/ tests/  # format
uv run mypy src/ tests/         # type check
uv run axm-audit audit .        # full audit (score ≥ 90 to pass)
```

## Code Conventions

- `from __future__ import annotations` in every module
- Explicit `__all__` in public modules
- Google-style docstrings on all public functions and classes
- Type annotations on all function signatures
- `Annotated` types for CLI parameters (cyclopts)

## Commit Convention

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation
- `test:` Tests
- `chore:` Maintenance
- `refactor:` Code refactoring

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

## Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/my-feature`
3. Commit changes following convention
4. Ensure `uv run axm-audit audit .` passes (Grade A or B)
5. Push and create a PR

## Reporting Issues

- **Code bugs** — open a GitHub issue with reproduction steps
- **Doc issues** — open a GitHub issue with the label `documentation`
- **Security vulnerabilities** — email the maintainer directly (do not open a public issue)

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 license.
