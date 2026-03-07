# Contributing

## Development Setup

```bash
git clone https://github.com/axm-protocols/axm-mcp.git
cd axm-mcp
uv sync --all-groups
pre-commit install
```

## Commit Conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <summary>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`, `perf`

## Running Tests

```bash
uv run pytest
```

## Linting & Type Checking

```bash
uv run ruff check src/ tests/
uv run mypy src/
```
