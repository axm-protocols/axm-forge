# Initialize a Project

## Prerequisites

- Python ≥ 3.12
- [uv](https://github.com/astral-sh/uv) installed

## Steps

### 1. Create a new project

```bash
axm-init init my-project
```

This scaffolds a production-grade Python project with:

- `pyproject.toml` (PEP 621)
- `src/` layout
- Pre-configured linting (Ruff), typing (MyPy), and testing (Pytest)

### 2. Choose a template

```bash
axm-init init my-project --template python
```

Available templates:

| Template | Description |
|---|---|
| `minimal` | Bare-bones Python package |
| `python` | Full-featured Python project |

### 3. Check PyPI availability

```bash
axm-init init my-project --check-pypi
```

The `--check-pypi` flag verifies the package name is available before scaffolding.

### 4. JSON output

```bash
axm-init init my-project --json
```

Outputs structured JSON for CI/automation use.
