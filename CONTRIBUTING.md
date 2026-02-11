# Contributing to axm-init

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm-init.git
cd axm-init
uv sync --all-groups
```

## Commands

| Command | Description |
|---------|-------------|
| `make check` | Lint + type-check + tests |
| `make lint` | Ruff + MyPy |
| `make format` | Auto-format with Ruff |
| `make docs-serve` | Local docs preview |

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — new feature
- `fix:` — bug fix
- `docs:` — documentation only
- `chore:` — maintenance (deps, CI, config)
- `test:` — adding or updating tests
- `refactor:` — code change that neither fixes a bug nor adds a feature

**Breaking changes:** add `!` after the type, e.g. `feat!: remove --template flag`.

## Pull Request Checklist

1. Write tests first (TDD)
2. Run `make check` — all tests pass, no lint errors
3. Keep commits atomic and conventional
4. Update docs if user-facing
