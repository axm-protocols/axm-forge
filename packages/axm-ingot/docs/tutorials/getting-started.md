# Getting Started

This tutorial walks you through installing `axm-ingot` and verifying your setup.

## Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

```bash
uv add axm-ingot
```

Or with pip:

```bash
pip install axm-ingot
```

## Step 1: Resolve a workspace

```python
from pathlib import Path

from axm_ingot import resolve_workspace

workspace = resolve_workspace(Path("/path/to/your/uv-workspace"))
if workspace is None:
    print("not a uv workspace")
else:
    print("root:", workspace.root)
    for member in workspace.members:
        print(member.name, member.path)
```

`resolve_workspace` returns `None` (never raises) when the directory has no
`[tool.uv.workspace]` table or an unreadable `pyproject.toml`.

## Step 2: Find the workspace root from anywhere

```python
from pathlib import Path

from axm_ingot import find_workspace_root

root = find_workspace_root(Path.cwd())  # walks up to the workspace root
```

## Step 3: Run the Tests

`axm-ingot` has no package-local `Makefile` — run its test suite directly
through `uv` from the workspace root:

```bash
uv run --package axm-ingot --directory packages/axm-ingot pytest -x -q
```

To lint and type-check the whole workspace at once, use the root `Makefile`
target (run it from the workspace root, not from inside the package):

```bash
make check  # lint + type-check + tests, across every workspace package
```

## Next Steps

- [API Reference](../reference/api.md) — Full public API documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
