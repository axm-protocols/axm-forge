# Contributing to axm-mcp

This package is part of the **axm** workspace.

## Development Setup

```bash
# Clone the workspace repository
git clone https://github.com/axm-protocols/axm.git
cd axm

# Install all dependencies
uv sync

# Run tests
uv run pytest --package axm-mcp
```

## Guidelines

- Follow the coding conventions defined in the workspace root
- Run `make check` from the workspace root before submitting
- Use conventional commits: `feat(axm-mcp): description`
