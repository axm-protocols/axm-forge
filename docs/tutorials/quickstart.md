# Getting Started

This tutorial walks you through installing `axm-init` and creating your first project.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-init
```

Or with pip:

```bash
pip install axm-init
```

Verify the installation:

```bash
axm-init version
```

## Step 1: Create a Project

Scaffold a production-ready Python project:

```bash
axm-init init my-project
cd my-project/my-project
```

This creates a complete project with:

- `pyproject.toml` — PEP 621 build config with uv/hatch
- `src/` layout — Industry-standard package structure
- `tests/` — Pre-configured Pytest setup
- Git repository initialized with an initial commit

## Step 2: Explore the Project

```
my-project/
├── pyproject.toml
├── README.md
├── src/
│   └── my_project/
│       └── __init__.py
├── tests/
│   └── __init__.py
└── uv.lock
```

## Step 3: Reserve a Name on PyPI

Optionally, claim your package name before publishing:

```bash
axm-init reserve my-project --dry-run
```

!!! tip "Dry run"
    Use `--dry-run` to verify availability without publishing.

## Next Steps

- [Initialize a Project](../howto/init.md) — Templates, options, PyPI check
- [Reserve a Package](../howto/reserve.md) — Token setup, automation
- [CLI Reference](../reference/cli.md) — Full command documentation
