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

```bash
cd packages/axm-ingot
make check
```

This runs lint + type check + security audit + tests.

## Next Steps

- [API Reference](../reference/cli.md) — Full public API documentation
- [Architecture](../explanation/architecture.md) — How the project is structured
